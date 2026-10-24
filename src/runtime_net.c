/* SacredFire: online play through a private server (docs/sacredfire/15-online.md).
 *
 * Off unless BB_ONLINE_SERVER names a server: runtime_net_resolve then answers nothing and
 * runtime_services.c's offline contracts stay (cable unplugged, signed out of PSN).
 *
 * On, with these guarantees:
 *   - every host name the game resolves answers the private server's address: the game's own
 *     servers (Activision's, Sony's) are never looked up and never reached;
 *   - sockets connect and send only to the private server, loopback and the addresses in
 *     BB_ONLINE_ALLOW; anything else is refused and logged;
 *   - HTTP and HTTPS requests go as plain HTTP to the private server's BB_ONLINE_HTTP_PORT
 *     (8080), with the original Host header and X-SacredFire-Scheme (no TLS, no certificates);
 *   - PSN: local user 1 is signed in under BB_ONLINE_ID (else BB_USER_NAME), with an account
 *     id made from the name and PS Plus granted. Authorization codes and ID tokens are made up
 *     here: they mean something only to the private server, never to Sony.
 * Every resolution, connection, first packet and HTTP request is logged ("Net:" lines) so the
 * game's protocol can be studied with a local server (tools/online/discovery_server.py).
 *
 * Sockets, epoll and resolvers follow the PS4 libnet contracts as shadPS4 documents them
 * (GPL-2.0, core/libraries/network): BSD sockaddr layout, errors 0x80410100 | errno with BSD
 * errno numbers, epoll timeouts in microseconds. */
#define _GNU_SOURCE
#include "runtime.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <strings.h>
#include <pthread.h>
#include <time.h>
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h> /* VirtualQuery for the dev-only task dump (winsock first) */
typedef SOCKET NativeSocket;
#define NATIVE_INVALID INVALID_SOCKET
#define native_close closesocket
typedef WSAPOLLFD NativePollFd;
#define native_poll WSAPoll
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <poll.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
typedef int NativeSocket;
#define NATIVE_INVALID (-1)
#define native_close close
typedef struct pollfd NativePollFd;
#define native_poll poll
#endif

/* ---- PS4 constants ---- */
#define NET_ERROR(e) ((int32_t)(0x80410100u | (uint32_t)(e)))
enum { E_INTR=4, E_BADF=9, E_ACCES=13, E_FAULT=14, E_INVAL=22, E_PIPE=32, E_AGAIN=35,
       E_INPROGRESS=36, E_ALREADY=37, E_NOTSOCK=38, E_MSGSIZE=40, E_PROTONOSUPPORT=43,
       E_AFNOSUPPORT=47, E_ADDRINUSE=48, E_ADDRNOTAVAIL=49, E_NETDOWN=50, E_NETUNREACH=51,
       E_CONNABORTED=53, E_CONNRESET=54, E_NOBUFS=55, E_ISCONN=56, E_NOTCONN=57,
       E_TIMEDOUT=60, E_CONNREFUSED=61, E_HOSTUNREACH=65, E_EXIST=17, E_NOSPC=28,
       E_RESOLVER_BUSY=221 };
#define PS_AF_INET 2
#define PS_SOCK_STREAM 1
#define PS_SOCK_DGRAM 2
#define PS_SOCK_RAW 3
#define PS_SOCK_DGRAM_P2P 6
#define PS_SOCK_STREAM_P2P 10
#define PS_SOL_SOCKET 0xffff
#define PS_MSG_PEEK 0x2
#define PS_MSG_WAITALL 0x40
#define PS_MSG_DONTWAIT 0x80
#define PS_EPOLLIN 0x1
#define PS_EPOLLOUT 0x2
#define PS_EPOLLERR 0x8
#define PS_EPOLLHUP 0x10
#define NET_CTL_INVALID_ADDR ((int32_t)0x80412107)
#define NP_SIGNED_OUT ((int32_t)0x80550006)
#define NP_INVALID_ARGUMENT ((int32_t)0x80550003)
#define NP_REQUEST_NOT_FOUND ((int32_t)0x80550017)
#define NP_AUTH_INVALID_ARGUMENT ((int32_t)0x80550303)
#define HTTP_INVALID_ID ((int32_t)0x80431100)
#define HTTP_INVALID_VALUE ((int32_t)0x804311fe)
#define HTTP_OUT_OF_MEMORY ((int32_t)0x80431022)
#define HTTP_INVALID_URL ((int32_t)0x80433060)
#define HTTP_NETWORK ((int32_t)0x80431063)
#define HTTP_BEFORE_SEND ((int32_t)0x80431065)
#define HTTP_TIMEOUT ((int32_t)0x80431068)
#define HTTP_PARSE_NOT_FOUND ((int32_t)0x80432025)

typedef struct { uint8_t len, family; uint16_t port; uint32_t addr; uint16_t vport; char zero[6]; } PsSockaddrIn;
typedef struct { uint32_t events, pad; uint64_t ident; uint64_t data; } PsEpollEvent;

/* ---- Configuration ---- */
static struct {
    int on;
    uint32_t server;            /* network order */
    char server_text[64];
    uint16_t http_port;
    uint32_t allow[16];
    int allow_count;
    int trace;                  /* BB_ONLINE_TRACE: hex dump of every packet, not only the first */
    char online_id[17];
    uint64_t account_id;
    uint32_t local_ip;          /* network order: the address that reaches the server */
} cfg;
static pthread_once_t cfg_once=PTHREAD_ONCE_INIT;
static pthread_mutex_t net_lock=PTHREAD_MUTEX_INITIALIZER;

#ifdef LEGACY_GAME_HOOKS
/* ---- Demonware test key (development only, private server) ----
 * The client checks the auth reply signature with Demonware's embedded RSA-2048
 * public key before reading any ticket, so a private server cannot complete the
 * login with the official key. With BB_DW_TEST_KEY pointing at a 294-byte test
 * SPKI (tools/online/dw_keygen.py), the embedded key is swapped in guest memory,
 * in place, and the private server signs with the matching test key. Without
 * BB_DW_TEST_KEY (and always offline) nothing here runs. */
#define DW_SPKI_LEN 294
#define DW_KEY_IMAGE_OFF ((uintptr_t)0x1becf80) /* eboot VA; verified at runtime, scanned if moved */
/* Demonware's RSA-2048 SPKI (public key only): the pattern searched in guest memory. */
static const unsigned char dw_official_spki[DW_SPKI_LEN] = {
    0x30, 0x82, 0x01, 0x22, 0x30, 0x0d, 0x06, 0x09, 0x2a, 0x86, 0x48, 0x86,
    0xf7, 0x0d, 0x01, 0x01, 0x01, 0x05, 0x00, 0x03, 0x82, 0x01, 0x0f, 0x00,
    0x30, 0x82, 0x01, 0x0a, 0x02, 0x82, 0x01, 0x01, 0x00, 0xc0, 0xa2, 0x0b,
    0x1f, 0x6c, 0xb8, 0x1b, 0x12, 0x70, 0xed, 0x1a, 0xef, 0x30, 0x6c, 0x75,
    0x9d, 0xc1, 0x08, 0x89, 0x99, 0xf0, 0x2a, 0xc8, 0xac, 0x2f, 0xc7, 0xd5,
    0xd0, 0x3b, 0x61, 0x29, 0x39, 0xf3, 0x8f, 0x62, 0x39, 0xda, 0xf1, 0x20,
    0x11, 0xe7, 0x92, 0xe9, 0x16, 0x24, 0x22, 0x96, 0x09, 0x9e, 0xac, 0x19,
    0xcd, 0x24, 0x3e, 0x58, 0xc6, 0x40, 0x86, 0x78, 0xd7, 0xdf, 0x70, 0x77,
    0xcb, 0xde, 0x80, 0x42, 0xb1, 0x38, 0xf3, 0x1d, 0x6a, 0x3c, 0x98, 0xe4,
    0x85, 0xdb, 0xfb, 0x53, 0x3a, 0x86, 0x47, 0xce, 0x58, 0xb1, 0xd3, 0xd7,
    0x0b, 0x83, 0x3d, 0x14, 0x6b, 0xda, 0x40, 0x24, 0x1f, 0x16, 0x2b, 0x0e,
    0x49, 0x22, 0xe4, 0xb7, 0x63, 0xff, 0xaa, 0x40, 0xc2, 0x44, 0xdf, 0xdc,
    0x3f, 0x8c, 0x1e, 0x60, 0xb4, 0x6f, 0x3e, 0xda, 0xb2, 0x4e, 0x50, 0xca,
    0xfc, 0x62, 0x4b, 0x62, 0xc7, 0xe1, 0x77, 0x5e, 0x83, 0xcd, 0xe0, 0xb5,
    0xfc, 0xc6, 0xaa, 0xa0, 0xc2, 0x6b, 0x28, 0xcc, 0x8a, 0xa7, 0x95, 0x7b,
    0x1e, 0x67, 0xe0, 0x5b, 0xaf, 0xc6, 0x54, 0x49, 0xe6, 0xac, 0x7a, 0x8d,
    0x1d, 0xe6, 0x7d, 0x12, 0x04, 0x94, 0xc3, 0x23, 0x4a, 0x00, 0x60, 0x58,
    0x33, 0x6f, 0xe7, 0x94, 0x19, 0xff, 0xf6, 0xe0, 0xc6, 0x40, 0x50, 0xb7,
    0x9d, 0x0e, 0xcd, 0xdf, 0xe7, 0x92, 0x5d, 0x84, 0x94, 0x13, 0x06, 0x61,
    0xbc, 0x44, 0x75, 0x54, 0x70, 0x54, 0x77, 0x4c, 0xc0, 0x28, 0x7d, 0xfc,
    0xc9, 0x9a, 0x92, 0x38, 0xd4, 0xd5, 0xee, 0xf3, 0x27, 0x44, 0x66, 0x13,
    0x2c, 0x06, 0xf0, 0x64, 0xe7, 0xec, 0xf8, 0x75, 0xfd, 0x15, 0xd4, 0x1b,
    0x91, 0x45, 0x9d, 0x4a, 0x3f, 0x40, 0xe9, 0x35, 0x53, 0x7f, 0xfc, 0x96,
    0x61, 0xe1, 0x48, 0x74, 0x21, 0xf0, 0x04, 0x20, 0x41, 0x30, 0x02, 0xd2,
    0xf9, 0x02, 0x03, 0x01, 0x00, 0x01,
};
static unsigned char dw_test_spki[DW_SPKI_LEN];
static int dw_test_key_ready;   /* test SPKI loaded from BB_DW_TEST_KEY */
static int dw_test_key_logged;  /* one log line per run about test-key mode */
static int dw_key_swapped;      /* swap completed (guest address in dw_key_addr) */
static int dw_scan_done;        /* bounded scan attempted at most once */
static uintptr_t dw_key_addr;
#define DW_SIGFN_IMAGE_OFF ((uintptr_t)0x14300) /* FUN_00014300: X-Signature check, only caller 0x13eb9 */
static const unsigned char dw_sigfn_bypass[6] = {0xb8, 0x01, 0x00, 0x00, 0x00, 0xc3}; /* mov eax,1; ret */
#define DW_VALIDATE_IMAGE_OFF ((uintptr_t)0x1410e) /* call [rax+0x50]: reply-JSON validator virtual */
static const unsigned char dw_validate_orig[3] = {0xff, 0x50, 0x50};
static const unsigned char dw_validate_bypass[3] = {0xb0, 0x01, 0x90}; /* mov al,1; nop */
#define DW_HANDLER_IMAGE_OFF ((uintptr_t)0x13d30) /* FUN_00013d30: whole auth reply handler */
static const unsigned char dw_handler_force700[6] = {0xb8, 0xbc, 0x02, 0x00, 0x00, 0xc3}; /* mov eax,700; ret */
#define DW_CHECK40_IMAGE_OFF ((uintptr_t)0x13e73) /* call [rax+0x40]: reply task-id check virtual */
static const unsigned char dw_check40_orig[3] = {0xff, 0x50, 0x40};
static const unsigned char dw_check40_bypass[3] = {0xb0, 0x01, 0x90}; /* mov al,1; nop */
#define DW_MODE600_IMAGE_OFF ((uintptr_t)0x1c5ef) /* jne past +0x600=1 when +0xe4 != 2 */
static const unsigned char dw_mode600_orig[2] = {0x75, 0x20};
static const unsigned char dw_mode600_bypass[2] = {0x90, 0x90}; /* nop;nop: always set dispatch mode 1 */
#define DW_DISPATCH_MODE_IMAGE_OFF ((uintptr_t)0x1a1cd) /* jne 0x1a2a8: reject if mode != 1 at dispatch */
static const unsigned char dw_dispatch_mode_orig[6] = {0x0f, 0x85, 0xd5, 0x00, 0x00, 0x00}; /* jne 0x1a2a8 */
static const unsigned char dw_dispatch_mode_bypass[6] = {0x90, 0x90, 0x90, 0x90, 0x90, 0x90}; /* nop*6: accept mode 0 for 0x81 */
#define DW_HANDLER_81_CRYPTO_IMAGE_OFF ((uintptr_t)0x1b97f) /* je 0x1b9fa: skip pre-check in 0x81 handler */
static const unsigned char dw_handler_81_crypto_orig[2] = {0x74, 0x79}; /* je 0x1b9fa */
static const unsigned char dw_handler_81_crypto_bypass[2] = {0x90, 0x90}; /* nop;nop: always proceed to crypto core */
#define DW_HANDLER_81_CRYPTO2_IMAGE_OFF ((uintptr_t)0x1b9ca) /* je 0x1b9fa: crypto core (0x1b060) fail in 0x81 handler */
static const unsigned char dw_handler_81_crypto2_orig[2] = {0x74, 0x2e}; /* je 0x1b9fa */
static const unsigned char dw_handler_81_crypto2_bypass[2] = {0x90, 0x90}; /* nop;nop: always proceed past crypto result */
#define DW_HANDLER_81_TYPE_IMAGE_OFF ((uintptr_t)0x1b98b) /* ja 0x1b9fa: reject type not in 210-220 */
static const unsigned char dw_handler_81_type_orig[2] = {0x77, 0x6d}; /* ja 0x1b9fa */
static const unsigned char dw_handler_81_type_bypass[2] = {0x90, 0x90}; /* nop;nop: accept 0x81 type */
#define DW_HANDLER_81_CRYPTO_CALL_OFF ((uintptr_t)0x1b9c3) /* call 0x1b060: crypto core in 0x81 handler */
static const unsigned char dw_handler_81_crypto_call_orig[5] = {0xe8, 0x98, 0xf6, 0xff, 0xff}; /* call 0x1b060 */
static const unsigned char dw_handler_81_crypto_call_bypass[5] = {0xb0, 0x01, 0x90, 0x90, 0x90}; /* mov al,1; nop*3: force crypto success */
static int dw_nosig_applied, dw_novalidate_applied, dw_force700_applied, dw_no40check_applied,
           dw_mode600_applied, dw_dispatch_mode_applied, dw_handler_81_crypto_applied,
           dw_handler_81_crypto2_applied, dw_handler_81_type_applied, dw_handler_81_crypto_call_applied;
static void dw_test_key_load(void) {
    const char *path=getenv("BB_DW_TEST_KEY");
    if (!path || !*path || dw_test_key_ready) return;
    FILE *f=fopen(path,"rb");
    unsigned char buf[DW_SPKI_LEN];
    const size_t n=f ? fread(buf,1,sizeof buf,f) : 0;
    const int extra=f && fgetc(f)!=EOF;
    if (f) fclose(f);
    if (n!=sizeof buf || extra) {
        printf("Net: online: test key '%s' unreadable (need exactly %d DER bytes): auth signatures will fail\n",
               path,DW_SPKI_LEN);
        return;
    }
    if (!memcmp(buf,dw_official_spki,sizeof buf)) {
        printf("Net: online: test key '%s' is the official key: refusing to swap a key for itself\n",path);
        return;
    }
    memcpy(dw_test_spki,buf,sizeof buf);
    dw_test_key_ready=1;
}
static int dw_swap_at(uintptr_t addr) {
    unsigned char cur[DW_SPKI_LEN];
    runtime_probe_read_image(addr,cur,sizeof cur);
    if (!memcmp(cur,dw_test_spki,sizeof cur)) { dw_key_addr=addr; return 1; } /* already swapped */
    if (memcmp(cur,dw_official_spki,sizeof cur)) return 0;
    if (!runtime_probe_write_image(addr,dw_test_spki,sizeof dw_test_spki)) {
        printf("Net: online: test key swap failed at image offset 0x%llx\n",
               (unsigned long long)(addr - runtime_probe_image(NULL)));
        return 0;
    }
    dw_key_addr=addr;
    printf("Net: online: Demonware test key installed at image offset 0x%llx (private server only)\n",
           (unsigned long long)(addr - runtime_probe_image(NULL)));
    return 1;
}
/* ---- Lobby task state dump (development only) ----
 * The 28-byte lobby hello carries 8 fresh nonce bytes that also sit at
 * task+0x264. With BB_DW_DUMPTASK=1, the first SSocket hello triggers one
 * bounded scan of mapped guest memory for those bytes; each hit verified by
 * task+0x9c==0x10000 and task+0xe4==2 dumps the crypto-relevant task state
 * (+0x100/+0x252/+0x264/+0x26c/+0x288../+0x360/+0x600/+0x700), ending all
 * speculation about what the lobby crypto needs. Slow (one full scan), once. */
static void dw_dump_field(const char *name, const unsigned char *base, uint64_t off, uint64_t len) {
    unsigned char buf[64];
    if (len > sizeof buf) len = sizeof buf;
    memcpy(buf, base + off, (size_t)len);
    char hex[129];
    for (uint64_t i = 0; i < len; ++i) snprintf(hex + i * 2, 3, "%02x", buf[i]);
    hex[len * 2] = 0;
    printf("Net: online: task+0x%llx %s = %s\n", (unsigned long long)off, name, hex);
}
#ifdef _WIN32
/* Whole-process scan (dev only): every committed readable region is searched for
 * the 8-byte hello nonce; each hit verified as a lobby task (+0x9c==0x10000 and
 * +0xe4==2) before dumping crypto-relevant state. Faults resume below. */
static void dw_dump_task(const unsigned char *nonce) {
    const char *env = getenv("BB_DW_DUMPTASK");
    if (!env || strcmp(env, "1")) return;
    /* Re-dump on each new hello (new connection/task), up to 3: shows whether the
     * +0x750 child and +0x600/+0x700 modes appear later in the task lifecycle. */
    static int dw_dump_count;
    static unsigned char dw_dump_last_nonce[8];
    static const unsigned char *dw_dump_prev_task;
    if (dw_dump_count > 0 && !memcmp(nonce, dw_dump_last_nonce, 8)) return;
    if (dw_dump_count >= 3) return;
    memcpy(dw_dump_last_nonce, nonce, 8);
    ++dw_dump_count;
    printf("Net: online: task dump #%d: enumerating task-shaped objects...\n",
           dw_dump_count);
    /* Re-read the previous dump's task first (same host mapping): shows whether
     * +0x600/+0x700/modes evolve after server messages arrived. */
    if (dw_dump_prev_task) {
        sigjmp_buf jb2;
        runtime_fault_recover = &jb2;
        if (!sigsetjmp(jb2, 1)) {
            uint32_t p600 = 0, p700 = 0, pa0 = 0, pmode = 0;
            memcpy(&p600, dw_dump_prev_task + 0x600, 4);
            memcpy(&p700, dw_dump_prev_task + 0x700, 4);
            memcpy(&pa0, dw_dump_prev_task + 0xa0, 4);
            memcpy(&pmode, dw_dump_prev_task + 0x258, 4);
            printf("Net: online: task redump %p: +0x258=%u +0x600=%u +0x700=%u +0xa0=%u\n",
                   dw_dump_prev_task, pmode, p600, p700, pa0);
        } else {
            printf("Net: online: task redump: previous task gone\n");
            dw_dump_prev_task = NULL;
        }
        runtime_fault_recover = NULL;
    }
    int found = 0;
    uint64_t regions = 0, scanned = 0;
    const uint64_t t0 = runtime_wait_clock();
    sigjmp_buf jb;
    for (uintptr_t at = 0; ; ) {
        MEMORY_BASIC_INFORMATION info;
        if (!VirtualQuery((void *)at, &info, sizeof info) || !info.RegionSize) break;
        const uintptr_t end = (uintptr_t)info.BaseAddress + info.RegionSize;
        /* Skip slow/irrelevant mappings: images (exe/DLLs), uncacheable GPU apertures. */
        const int slow = (info.Protect & (PAGE_NOACCESS | PAGE_GUARD | PAGE_WRITECOMBINE | PAGE_NOCACHE));
        if (info.State == MEM_COMMIT && !slow && info.Type != MEM_IMAGE) {
            ++regions;
            scanned += info.RegionSize;
            if ((scanned >> 30) != ((scanned - info.RegionSize) >> 30))
                printf("Net: online: task dump: %llu GB...\n", (unsigned long long)(scanned >> 30));
            if ((runtime_wait_clock() - t0) / 1000000000ull >= 30) {
                printf("Net: online: task dump: time budget exceeded, stopping\n");
                break;
            }
            const unsigned char *base = (const unsigned char *)info.BaseAddress;
            const uint64_t len = info.RegionSize;
            const unsigned char n0 = nonce[0];
            runtime_fault_recover = &jb;
            uint64_t pos = 0;
            int done = 0;
            if (!sigsetjmp(jb, 1)) {
                while (pos + 8 <= len && found < 3) {
                    const unsigned char *hit = memchr(base + pos, n0, (size_t)(len - 8 - pos + 1));
                    if (!hit) break;
                    pos = (uint64_t)(hit - base) + 1;
                    if (memcmp(hit, nonce, 8)) continue;
                    /* The send buffer itself holds the nonce at +20: skip it by prefix. */
                    {
                    static const unsigned char hello_prefix[20]={
                        0xc8,0,0,0, 0xc8,0,0,0, 0xd2,0,0,0, 0xdc,0,0,0, 0,0,1,0};
                    if (hit - base >= 20 && !memcmp(hit - 20, hello_prefix, sizeof hello_prefix))
                        continue;
                    }
                    const unsigned char *task = hit - 0x264;
                    uint32_t v9c = 0, ve4 = 0;
                    memcpy(&v9c, task + 0x9c, 4);
                    memcpy(&ve4, task + 0xe4, 4);
                    if (v9c != 0x10000 || ve4 != 2) continue;
                    printf("Net: online: task dump: candidate at %p (+0x9c=0x10000, +0xe4=2)\n",
                           task);
                    if (!dw_dump_prev_task) dw_dump_prev_task = task;
                    dw_dump_field("u32", task, 0x9c, 4);
                    dw_dump_field("u32", task, 0xe4, 4);
                    dw_dump_field("u32", task, 0xa0, 4);
                    dw_dump_field("mode", task, 0x258, 4);
                    dw_dump_field("u32", task, 0x600, 4);
                    dw_dump_field("u32", task, 0x700, 4);
                    dw_dump_field("sess+0", task, 0x100, 64);
                    dw_dump_field("sess+64", task, 0x140, 64);
                    dw_dump_field("sess+0x258", task, 0x358, 4);
                    dw_dump_field("byte", task, 0x252, 1);
                    dw_dump_field("nonce", task, 0x264, 8);
                    dw_dump_field("u64", task, 0x26c, 8);
                    dw_dump_field("session", task, 0x288, 36);
                    dw_dump_field("u32", task, 0x360, 4);
                    dw_dump_field("key?", task, 0x364, 32);
                    dw_dump_field("u32", task, 0x120, 4);
                    {
                        /* The message dispatch (0x1a120) runs on the CHILD task at
                         * parent+0x750 (a guest address: read it via backing). */
                        uintptr_t child = 0;
                        memcpy(&child, task + 0x750, 8);
                        printf("Net: online: child task at guest 0x%llx\n",
                               (unsigned long long)child);
                        if (child) {
                            unsigned char cf[48];
                            runtime_memory_read_backing(child, cf, sizeof cf);
                            printf("Net: online: child+0x0..0x2f = ");
                            for (int k = 0; k < 48; ++k) printf("%02x", cf[k]);
                            printf("\n");
                            uint32_t c9c = 0, ce4 = 0, ca0 = 0, c600 = 0, c700 = 0, cb0 = 0;
                            runtime_memory_read_backing(child + 0x9c, &c9c, 4);
                            runtime_memory_read_backing(child + 0xe4, &ce4, 4);
                            runtime_memory_read_backing(child + 0xa0, &ca0, 4);
                            runtime_memory_read_backing(child + 600, &c600, 4);
                            runtime_memory_read_backing(child + 0x700, &c700, 4);
                            runtime_memory_read_backing(child + 0xb0, &cb0, 4);
                            printf("Net: online: child +0x9c=%u +0xe4=%u +0xa0=%u +0x600=%u +0x700=%u +0xb0=%u\n",
                                   c9c, ce4, ca0, c600, c700, cb0);
                        }
                    }
                    ++found;
                }
                done = 1;
            }
            runtime_fault_recover = NULL;
            (void)done;
        }
        if (found >= 3) break;
        at = end;
        if (!end) break;
    }
    printf("Net: online: task dump: %d candidate(s), %llu regions, %llu MB scanned\n",
           found, (unsigned long long)regions, (unsigned long long)(scanned >> 20));
}
#else
static void dw_dump_task(const unsigned char *nonce) {
    /* Linux: vma walk (best effort, see _WIN32 branch for the full version). */
    const char *env = getenv("BB_DW_DUMPTASK");
    static int done = 0;
    if (!env || strcmp(env, "1") || done) return;
    done = 1;
    printf("Net: online: task dump: scanning mapped guest memory for the hello nonce...\n");
    static unsigned char page[1048576];
    int found = 0;
    for (uintptr_t base = 0x100000000ull; base < 0x100000000ull + ((uint64_t)16384 << 20) && found < 3;) {
        int prot = 0, type = -1;
        uintptr_t end = 0;
        if (!runtime_memory_vma_info(base, &prot, &type, &end) || end <= base) { base += 1048576; continue; }
        for (uintptr_t at = base; at < end && found < 3; at += sizeof page) {
            uint64_t chunk = end - at < sizeof page ? end - at : sizeof page;
            runtime_memory_read_backing(at, page, chunk);
            for (uint64_t i = 0; i + 8 <= chunk; ++i) {
                if (memcmp(page + i, nonce, 8)) continue;
                const uintptr_t task = at + i - 0x264;
                uint32_t v9c = 0, ve4 = 0;
                runtime_memory_read_backing(task + 0x9c, &v9c, 4);
                runtime_memory_read_backing(task + 0xe4, &ve4, 4);
                if (v9c != 0x10000 || ve4 != 2) continue;
                printf("Net: online: task dump: candidate at guest 0x%llx (+0x9c=0x10000, +0xe4=2)\n",
                       (unsigned long long)task);
                ++found;
            }
        }
        base = end;
    }
    printf("Net: online: task dump: %d candidate(s)\n", found);
}
#endif
/* Called with online on: from configure() and before each Demonware /auth/ request. */
static void dw_test_key_ensure(void) {
    pthread_mutex_lock(&net_lock);
    dw_test_key_load();
    if (dw_test_key_ready && !dw_test_key_logged) {
        dw_test_key_logged=1;
        printf("Net: online: test-key mode (BB_DW_TEST_KEY): auth replies must carry X-Signature from the test key\n");
    }
    if (dw_test_key_ready && !dw_key_swapped) {
        uint64_t image_size=0;
        const uintptr_t image=runtime_probe_image(&image_size);
        if (!image || !image_size) {
            printf("Net: online: prepared image not ready yet: will retry before auth\n");
        } else if (DW_KEY_IMAGE_OFF+DW_SPKI_LEN <= image_size &&
                   dw_swap_at(image+DW_KEY_IMAGE_OFF)) {
            dw_key_swapped=1;
        } else if (!dw_scan_done) {
            dw_scan_done=1;
            static unsigned char page[1048576];
            const uintptr_t end=image+image_size;
            for (uintptr_t base=image; base<end && !dw_key_swapped; base+=sizeof page) {
                uint64_t chunk=(uint64_t)(end-base)<sizeof page ? (uint64_t)(end-base) : sizeof page;
                runtime_probe_read_image(base,page,chunk);
                for (uint64_t i=0;i+DW_SPKI_LEN<=chunk;++i)
                    if (!memcmp(page+i,dw_official_spki,DW_SPKI_LEN) && dw_swap_at(base+i)) {
                        dw_key_swapped=1; break;
                    }
            }
            if (!dw_key_swapped)
                printf("Net: online: official Demonware key not found in image (%llu bytes): signatures will fail\n",
                       (unsigned long long)image_size);
        }
    } else if (dw_test_key_ready && dw_key_swapped && dw_key_addr) {
        dw_swap_at(dw_key_addr); /* one 294-byte check before each auth request */
    }
    /* BB_DW_NOSIG=1: bypass the reply signature check (mov eax,1; ret at FUN_00014300).
     * Isolates whether the gate is the signature or the tickets that follow. The
     * function has a single caller (0x13eb9, inside the auth reply handler). */
    {
        const char *nosig=getenv("BB_DW_NOSIG");
        if (nosig && !strcmp(nosig,"1") && !dw_nosig_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_SIGFN_IMAGE_OFF+sizeof dw_sigfn_bypass <= image_size) {
                const uintptr_t fn=image+DW_SIGFN_IMAGE_OFF;
                unsigned char cur[sizeof dw_sigfn_bypass];
                runtime_probe_read_image(fn,cur,sizeof cur);
                if (!memcmp(cur,dw_sigfn_bypass,sizeof cur)) dw_nosig_applied=1;
                else if (runtime_probe_write_image(fn,dw_sigfn_bypass,sizeof dw_sigfn_bypass)) {
                    dw_nosig_applied=1;
                    printf("Net: online: test BYPASS: auth signature check disabled "
                           "(was %02x %02x %02x %02x %02x %02x, private server dev only)\n",
                           cur[0],cur[1],cur[2],cur[3],cur[4],cur[5]);
                } else printf("Net: online: test bypass write failed\n");
            }
        }
    }
    /* BB_DW_NOVALIDATE=1: force the reply-JSON validator virtual (+0x50) to pass.
     * Isolates whether the gate is that validator or the ticket fields. Single
     * use site (0x1410e, inside the auth reply handler, after the tickets decode). */
    {
        const char *novalidate=getenv("BB_DW_NOVALIDATE");
        if (novalidate && !strcmp(novalidate,"1") && !dw_novalidate_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_VALIDATE_IMAGE_OFF+sizeof dw_validate_bypass <= image_size) {
                const uintptr_t site=image+DW_VALIDATE_IMAGE_OFF;
                unsigned char cur[sizeof dw_validate_bypass];
                runtime_probe_read_image(site,cur,sizeof cur);
                if (!memcmp(cur,dw_validate_bypass,sizeof cur)) dw_novalidate_applied=1;
                else if (!memcmp(cur,dw_validate_orig,sizeof cur) &&
                         runtime_probe_write_image(site,dw_validate_bypass,sizeof dw_validate_bypass)) {
                    dw_novalidate_applied=1;
                    printf("Net: online: test BYPASS: reply validator forced to pass (private server dev only)\n");
                } else printf("Net: online: test validator bypass not applied (bytes %02x %02x %02x)\n",
                              cur[0],cur[1],cur[2]);
            }
        }
    }
    /* BB_DW_NO40CHECK=1: force the reply task-id check virtual (+0x40) to pass.
     * Same isolation pattern as the +0x50 bypass (single use site 0x13e73). */
    {
        const char *no40=getenv("BB_DW_NO40CHECK");
        if (no40 && !strcmp(no40,"1") && !dw_no40check_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_CHECK40_IMAGE_OFF+sizeof dw_check40_bypass <= image_size) {
                const uintptr_t site=image+DW_CHECK40_IMAGE_OFF;
                unsigned char cur[sizeof dw_check40_bypass];
                runtime_probe_read_image(site,cur,sizeof cur);
                if (!memcmp(cur,dw_check40_bypass,sizeof cur)) dw_no40check_applied=1;
                else if (!memcmp(cur,dw_check40_orig,sizeof cur) &&
                         runtime_probe_write_image(site,dw_check40_bypass,sizeof dw_check40_bypass)) {
                    dw_no40check_applied=1;
                    printf("Net: online: test BYPASS: reply task-id check forced to pass (private server dev only)\n");
                } else printf("Net: online: test task-id bypass not applied (bytes %02x %02x %02x)\n",
                              cur[0],cur[1],cur[2]);
            }
        }
    }
    /* BB_DW_FORCE700=1: force the whole auth reply handler to return 700.
     * Tells whether the retry loop even depends on FUN_00013d30's result: if the
     * client still retries, another loop drives it; if it advances or faults on
     * the (uninitialized) ticket state, the handler's internals are the gate. */
    {
        const char *force=getenv("BB_DW_FORCE700");
        if (force && !strcmp(force,"1") && !dw_force700_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_HANDLER_IMAGE_OFF+sizeof dw_handler_force700 <= image_size) {
                const uintptr_t fn=image+DW_HANDLER_IMAGE_OFF;
                unsigned char cur[sizeof dw_handler_force700];
                runtime_probe_read_image(fn,cur,sizeof cur);
                if (!memcmp(cur,dw_handler_force700,sizeof cur)) dw_force700_applied=1;
                else if (runtime_probe_write_image(fn,dw_handler_force700,sizeof dw_handler_force700)) {
                    dw_force700_applied=1;
                    printf("Net: online: test BYPASS: auth handler forced to 700 "
                           "(was %02x %02x %02x %02x %02x %02x, private server dev only)\n",
                           cur[0],cur[1],cur[2],cur[3],cur[4],cur[5]);
                } else printf("Net: online: test force700 write failed\n");
            }
        }
    }
    /* BB_DW_FORCE600=1: always set dispatch mode (+0x600=1) after queueing the
     * hello, even if the connection is still establishing (+0xe4 != 2). Our
     * loopback answers differently from a real server, so the poll may never
     * revisit; without mode 1 every server message is rejected. Single site. */
    {
        const char *mode=getenv("BB_DW_FORCE600");
        if (mode && !strcmp(mode,"1") && !dw_mode600_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_MODE600_IMAGE_OFF+sizeof dw_mode600_bypass <= image_size) {
                const uintptr_t site=image+DW_MODE600_IMAGE_OFF;
                unsigned char cur[sizeof dw_mode600_bypass];
                runtime_probe_read_image(site,cur,sizeof cur);
                if (!memcmp(cur,dw_mode600_bypass,sizeof cur)) dw_mode600_applied=1;
                else if (!memcmp(cur,dw_mode600_orig,sizeof cur) &&
                         runtime_probe_write_image(site,dw_mode600_bypass,sizeof dw_mode600_bypass)) {
                    dw_mode600_applied=1;
                    printf("Net: online: test BYPASS: dispatch mode forced to 1 (private server dev only)\n");
                } else printf("Net: online: test mode600 bypass not applied (bytes %02x %02x)\n",
                              cur[0],cur[1]);
            }
        }
    }
    /* BB_DW_DISPATCH_MODE=1: force the dispatch routine to accept mode 0 for 0x81 greeting.
     * The dispatch at 0x1a120 reads mode from +0x258 and rejects if not in {1,2,3}.
     * Our loopback never sets mode 1 (server answers differently), so 0x81 is dropped.
     * Patching the jne at 0x1a1cd (6 bytes) to NOPs lets mode 0 fall through to 0x81 handling. */
    {
        const char *dmode=getenv("BB_DW_DISPATCH_MODE");
        if (dmode && !strcmp(dmode,"1") && !dw_dispatch_mode_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_DISPATCH_MODE_IMAGE_OFF+sizeof dw_dispatch_mode_bypass <= image_size) {
                const uintptr_t site=image+DW_DISPATCH_MODE_IMAGE_OFF;
                unsigned char cur[sizeof dw_dispatch_mode_bypass];
                runtime_probe_read_image(site,cur,sizeof cur);
                if (!memcmp(cur,dw_dispatch_mode_bypass,sizeof cur)) dw_dispatch_mode_applied=1;
                else if (!memcmp(cur,dw_dispatch_mode_orig,sizeof cur) &&
                         runtime_probe_write_image(site,dw_dispatch_mode_bypass,sizeof dw_dispatch_mode_bypass)) {
                    dw_dispatch_mode_applied=1;
                    printf("Net: online: test BYPASS: dispatch mode check disabled for 0x81 (private server dev only)\n");
                } else printf("Net: online: test dispatch-mode bypass not applied (bytes %02x %02x %02x %02x %02x %02x)\n",
                              cur[0],cur[1],cur[2],cur[3],cur[4],cur[5]);
            }
        }
    }
        /* BB_DW_HANDLER_81_CRYPTO=1: force the 0x81 handler (0x1b8e0) to skip the
     * crypto core call (0x1b060) and proceed to send the response.
     * The crypto core validates tickets with RSA/DH; our dummy tickets fail.
     * Patching the je at 0x1b97c (2 bytes) to NOPs lets it fall through to
     * the send-message path which sets mode=2 and replies. */
    {
        const char *h81=getenv("BB_DW_HANDLER_81_CRYPTO");
        if (h81 && !strcmp(h81,"1") && !dw_handler_81_crypto_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_HANDLER_81_CRYPTO_IMAGE_OFF+sizeof dw_handler_81_crypto_bypass <= image_size) {
                const uintptr_t site=image+DW_HANDLER_81_CRYPTO_IMAGE_OFF;
                unsigned char cur[sizeof dw_handler_81_crypto_bypass];
                runtime_probe_read_image(site,cur,sizeof cur);
                if (!memcmp(cur,dw_handler_81_crypto_bypass,sizeof cur)) dw_handler_81_crypto_applied=1;
                else if (!memcmp(cur,dw_handler_81_crypto_orig,sizeof cur) &&
                         runtime_probe_write_image(site,dw_handler_81_crypto_bypass,sizeof dw_handler_81_crypto_bypass)) {
                    dw_handler_81_crypto_applied=1;
                    printf("Net: online: test BYPASS: 0x81 handler crypto core bypassed (private server dev only)\n");
                } else printf("Net: online: test handler-81-crypto bypass not applied (bytes %02x %02x)\n",
                              cur[0],cur[1]);
            }
        }
       /* BB_DW_HANDLER_81_CRYPTO2=1: force the 0x81 handler to accept crypto core failure.
     * After call 0x1b060, a je at 0x1b9ca jumps to failure if crypto returns 0.
     * Our dummy tickets make crypto fail; NOP this je to fall through to send path.
     * This sets mode=2 at +0x258 and sends the 8-byte response. */
    {
        const char *h81=getenv("BB_DW_HANDLER_81_CRYPTO2");
        if (h81 && !strcmp(h81,"1") && !dw_handler_81_crypto2_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_HANDLER_81_CRYPTO2_IMAGE_OFF+sizeof dw_handler_81_crypto2_bypass <= image_size) {
                const uintptr_t site=image+DW_HANDLER_81_CRYPTO2_IMAGE_OFF;
                unsigned char cur[sizeof dw_handler_81_crypto2_bypass];
                runtime_probe_read_image(site,cur,sizeof cur);
                if (!memcmp(cur,dw_handler_81_crypto2_bypass,sizeof cur)) dw_handler_81_crypto2_applied=1;
                else if (!memcmp(cur,dw_handler_81_crypto2_orig,sizeof cur) &&
                         runtime_probe_write_image(site,dw_handler_81_crypto2_bypass,sizeof dw_handler_81_crypto2_bypass)) {
                    dw_handler_81_crypto2_applied=1;
                    printf("Net: online: test BYPASS: 0x81 handler crypto result check bypassed (private server dev only)\r\n");
                } else printf("Net: online: test handler-81-crypto2 bypass not applied (bytes %02x %02x)\r\n",
                              cur[0],cur[1]);
            }
        }
    }
 }

    /* BB_DW_HANDLER_81_TYPE=1: accept 0x81 message type in handler.
     * The handler at 0x1b8e0 checks message type (at msg+4) is in 210-220.
     * The 0x81 greeting has type 0x81 at msg+4, which fails this check.
     * NOP the ja at 0x1b98b to accept 0x81. */
    {
        const char *h81=getenv("BB_DW_HANDLER_81_TYPE");
        if (h81 && !strcmp(h81,"1") && !dw_handler_81_type_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_HANDLER_81_TYPE_IMAGE_OFF+sizeof dw_handler_81_type_bypass <= image_size) {
                const uintptr_t site=image+DW_HANDLER_81_TYPE_IMAGE_OFF;
                unsigned char cur[sizeof dw_handler_81_type_bypass];
                runtime_probe_read_image(site,cur,sizeof cur);
                if (!memcmp(cur,dw_handler_81_type_bypass,sizeof cur)) dw_handler_81_type_applied=1;
                else if (!memcmp(cur,dw_handler_81_type_orig,sizeof cur) &&
                         runtime_probe_write_image(site,dw_handler_81_type_bypass,sizeof dw_handler_81_type_bypass)) {
                    dw_handler_81_type_applied=1;
                    printf("Net: online: test BYPASS: 0x81 handler type check bypassed (private server dev only)\r\n");
                } else printf("Net: online: test handler-81-type bypass not applied (bytes %02x %02x)\r\n",
                              cur[0],cur[1]);
            }
        }
    }
    /* BB_DW_HANDLER_81_CRYPTO_CALL=1: force the crypto core call (0x1b060) in     * the 0x81 handler to return success (AL=1) without actually running it.     * The crypto core validates tickets with RSA/DH; our dummy tickets fail.     * Replacing the call at 0x1b9c3 (5 bytes) with mov al,1; nop*3 lets the     * handler proceed to send the 8-byte response which sets mode=2. */
    {
        const char *h81=getenv("BB_DW_HANDLER_81_CRYPTO_CALL");
        if (h81 && !strcmp(h81,"1") && !dw_handler_81_crypto_call_applied) {
            uint64_t image_size=0;
            const uintptr_t image=runtime_probe_image(&image_size);
            if (image && DW_HANDLER_81_CRYPTO_CALL_OFF+sizeof dw_handler_81_crypto_call_bypass <= image_size) {
                const uintptr_t site=image+DW_HANDLER_81_CRYPTO_CALL_OFF;
                unsigned char cur[sizeof dw_handler_81_crypto_call_bypass];
                runtime_probe_read_image(site,cur,sizeof cur);
                if (!memcmp(cur,dw_handler_81_crypto_call_bypass,sizeof cur)) dw_handler_81_crypto_call_applied=1;
                else if (!memcmp(cur,dw_handler_81_crypto_call_orig,sizeof cur) &&
                         runtime_probe_write_image(site,dw_handler_81_crypto_call_bypass,sizeof dw_handler_81_crypto_call_bypass)) {
                    dw_handler_81_crypto_call_applied=1;
                    printf("Net: online: test BYPASS: 0x81 handler crypto call forced success (private server dev only)\r\n");
                } else printf("Net: online: test handler-81-crypto-call bypass not applied (bytes %02x %02x %02x %02x %02x)\r\n",
                              cur[0],cur[1],cur[2],cur[3],cur[4]);
            }
        }
    }

pthread_mutex_unlock(&net_lock);
}
#else
static void dw_test_key_ensure(void) {}
static void dw_dump_task(const unsigned char *nonce) { (void)nonce; }
#endif

static void ip_text(uint32_t addr, char *out, size_t size) {
    const unsigned char *b=(const unsigned char *)&addr;
    snprintf(out,size,"%u.%u.%u.%u",b[0],b[1],b[2],b[3]);
}
static int parse_ipv4(const char *text, uint32_t *out) {
    struct in_addr a;
    if (!text || inet_pton(AF_INET,text,&a)!=1) return 0;
    *out=a.s_addr; return 1;
}
static uint64_t fnv1a(const char *s) {
    uint64_t h=0xcbf29ce484222325ull;
    for (; *s; ++s) { h^=(unsigned char)*s; h*=0x100000001b3ull; }
    return h;
}
/* The PSN online id: 3 to 16 letters, digits, '-' or '_'. */
static void make_online_id(void) {
    const char *source=getenv("BB_ONLINE_ID");
    if (!source || !*source) source=getenv("BB_USER_NAME");
    if (!source || !*source) source="Player1";
    size_t n=0;
    for (const char *p=source; *p && n<16; ++p) {
        const char c=*p;
        cfg.online_id[n++]=(isalnum((unsigned char)c) || c=='-' || c=='_') ? c : '_';
    }
    while (n<3) cfg.online_id[n++]='_';
    cfg.online_id[n]=0;
    const char *account=getenv("BB_ONLINE_ACCOUNT_ID");
    cfg.account_id=account && *account ? strtoull(account,NULL,0) : (fnv1a(cfg.online_id) & 0x7fffffffffffffffull);
    if (!cfg.account_id) cfg.account_id=1;
}
/* The local address the server sees: a UDP socket "connected" to the server (nothing is sent). */
static void find_local_ip(void) {
    cfg.local_ip=htonl(0x7f000001);
    if ((ntohl(cfg.server)>>24)==127) return;
    NativeSocket s=socket(AF_INET,SOCK_DGRAM,IPPROTO_UDP);
    if (s==NATIVE_INVALID) return;
    struct sockaddr_in to={0}; to.sin_family=AF_INET; to.sin_port=htons(9); to.sin_addr.s_addr=cfg.server;
    struct sockaddr_in me={0};
    socklen_t len=sizeof me;
    if (!connect(s,(struct sockaddr *)&to,sizeof to) && !getsockname(s,(struct sockaddr *)&me,&len)) cfg.local_ip=me.sin_addr.s_addr;
    native_close(s);
}
static void configure(void) {
    const char *server=getenv("BB_ONLINE_SERVER");
    if (!server || !*server) return;
#ifdef _WIN32
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2,2),&wsa)) { printf("Net: online off: Winsock did not start\n"); return; }
#endif
    /* The only real name lookup: the private server's own name, once. */
    if (!parse_ipv4(server,&cfg.server)) {
        struct addrinfo hints={0}, *found=NULL;
        hints.ai_family=AF_INET;
        if (getaddrinfo(server,NULL,&hints,&found) || !found) {
            printf("Net: online off: the private server '%s' was not found\n",server);
            return;
        }
        cfg.server=((struct sockaddr_in *)found->ai_addr)->sin_addr.s_addr;
        freeaddrinfo(found);
    }
    ip_text(cfg.server,cfg.server_text,sizeof cfg.server_text);
    const char *port=getenv("BB_ONLINE_HTTP_PORT");
    cfg.http_port=(uint16_t)(port && atoi(port)>0 ? atoi(port) : 8080);
    const char *allow=getenv("BB_ONLINE_ALLOW");
    if (allow) {
        char list[512];
        snprintf(list,sizeof list,"%s",allow);
        for (char *item=strtok(list,", ;"); item && cfg.allow_count<16; item=strtok(NULL,", ;"))
            if (parse_ipv4(item,&cfg.allow[cfg.allow_count])) ++cfg.allow_count;
    }
    cfg.trace=getenv("BB_ONLINE_TRACE") && atoi(getenv("BB_ONLINE_TRACE"))>0;
    make_online_id();
    find_local_ip();
    char local[32];
    ip_text(cfg.local_ip,local,sizeof local);
    cfg.on=1;
    printf("Net: online ON: private server %s (%s), HTTP port %u, local address %s, PSN user '%s' "
           "(account %llu); every host name answers the private server\n",
           server,cfg.server_text,cfg.http_port,local,cfg.online_id,(unsigned long long)cfg.account_id);
    dw_test_key_ensure();
}
static int online(void) { pthread_once(&cfg_once,configure); return cfg.on; }

/* Where the game may connect or send: the server, loopback, BB_ONLINE_ALLOW. */
static int allowed(uint32_t addr) {
    if (addr==cfg.server || (ntohl(addr)>>24)==127) return 1;
    for (int i=0;i<cfg.allow_count;++i) if (cfg.allow[i]==addr) return 1;
    return 0;
}

/* ---- Logging ---- */
static void hexdump(const char *what, int id, const void *data, size_t size) {
    const unsigned char *b=data;
    const size_t shown=size<(cfg.trace ? 256 : 64) ? size : (cfg.trace ? 256 : 64);
    char hex[256*3+1], text[257];
    for (size_t i=0;i<shown;++i) { snprintf(hex+i*3,4,"%02x ",b[i]); text[i]=b[i]>=32 && b[i]<127 ? (char)b[i] : '.'; }
    hex[shown*3]=0; text[shown]=0;
    printf("Net: %s %d: %zu bytes: %s|%s|%s\n",what,id,size,hex,text,size>shown ? " ..." : "");
}
static struct { char host[128]; } seen_hosts[64];
static int seen_count;
static int first_time_host(const char *host) {
    int first=1;
    pthread_mutex_lock(&net_lock);
    for (int i=0;i<seen_count;++i) if (!strcmp(seen_hosts[i].host,host)) { first=0; break; }
    if (first && seen_count<64) snprintf(seen_hosts[seen_count++].host,sizeof seen_hosts[0].host,"%s",host);
    pthread_mutex_unlock(&net_lock);
    return first;
}

/* ---- Native errors as PS4 (BSD) errno values ---- */
static int native_error(void) {
#ifdef _WIN32
    const int e=WSAGetLastError();
    return e>10000 && e<10100 ? e-10000 : E_INVAL; /* WSAExxx = 10000 + the BSD number */
#else
    switch (errno) {
    case EAGAIN: return E_AGAIN;
    case EINPROGRESS: return E_INPROGRESS;
    case EALREADY: return E_ALREADY;
    case ENOTSOCK: return E_NOTSOCK;
    case EMSGSIZE: return E_MSGSIZE;
    case EADDRINUSE: return E_ADDRINUSE;
    case EADDRNOTAVAIL: return E_ADDRNOTAVAIL;
    case ENETDOWN: return E_NETDOWN;
    case ENETUNREACH: return E_NETUNREACH;
    case ECONNABORTED: return E_CONNABORTED;
    case ECONNRESET: return E_CONNRESET;
    case ENOBUFS: return E_NOBUFS;
    case EISCONN: return E_ISCONN;
    case ENOTCONN: return E_NOTCONN;
    case ETIMEDOUT: return E_TIMEDOUT;
    case ECONNREFUSED: return E_CONNREFUSED;
    case EHOSTUNREACH: return E_HOSTUNREACH;
    case EINTR: return E_INTR;
    case EBADF: return E_BADF;
    case EPIPE: return E_PIPE;
    case EACCES: return E_ACCES;
    default: return E_INVAL;
    }
#endif
}
#ifndef _WIN32
static int bsd_from_native_code(int e) { errno=e; return native_error(); }
#else
static int bsd_from_native_code(int e) { return e>10000 && e<10100 ? e-10000 : (e ? E_INVAL : 0); }
#endif
static __thread int32_t net_errno;
static int32_t fail(int e) { net_errno=e; return NET_ERROR(e); }
static void set_nonblocking(NativeSocket s, int on) {
#ifdef _WIN32
    u_long v=(u_long)on; ioctlsocket(s,FIONBIO,&v);
#else
    const int flags=fcntl(s,F_GETFL,0);
    fcntl(s,F_SETFL,on ? flags|O_NONBLOCK : flags&~O_NONBLOCK);
#endif
}
static void set_timeout(NativeSocket s, int option, uint32_t usec) {
#ifdef _WIN32
    DWORD ms=usec ? (usec+999)/1000 : 0;
    setsockopt(s,SOL_SOCKET,option,(const char *)&ms,sizeof ms);
#else
    struct timeval t={usec/1000000,usec%1000000};
    setsockopt(s,SOL_SOCKET,option,&t,sizeof t);
#endif
}
static int wait_ready(NativeSocket s, int write, int timeout_ms) {
    NativePollFd p={0};
    p.fd=s; p.events=write ? POLLOUT : POLLIN;
    return native_poll(&p,1,timeout_ms);
}

/* ---- Object table: sockets, epolls and resolvers share the id space, as on the console ---- */
enum { OBJ_FREE, OBJ_SOCKET, OBJ_EPOLL, OBJ_RESOLVER };
typedef struct { int id; uint32_t events; uint64_t data; int reported; } Watch;
typedef struct {
    int kind;
    char name[32];
    /* socket */
    NativeSocket s;
    int type, nbio, sent_logged, received_logged;
    /* epoll */
    Watch watch[64];
    int watches;
    volatile int abort_wait;
    /* resolver */
    volatile int resolved;
} NetObj;
#define MAX_OBJECTS 512
static NetObj objects[MAX_OBJECTS];

static int object_new(int kind, const char *name) {
    pthread_mutex_lock(&net_lock);
    for (int id=1; id<MAX_OBJECTS; ++id) if (objects[id].kind==OBJ_FREE) {
        memset(&objects[id],0,sizeof objects[id]);
        objects[id].kind=kind; objects[id].s=NATIVE_INVALID;
        snprintf(objects[id].name,sizeof objects[id].name,"%s",name ? name : "");
        pthread_mutex_unlock(&net_lock);
        return id;
    }
    pthread_mutex_unlock(&net_lock);
    return 0;
}
static NetObj *object(int id, int kind) {
    return id>0 && id<MAX_OBJECTS && objects[id].kind==kind ? &objects[id] : NULL;
}

/* ---- Addresses ---- */
static int to_native(const void *guest, uint32_t len, struct sockaddr_in *out) {
    if (!guest || len<8) return E_INVAL;
    PsSockaddrIn in;
    memset(&in,0,sizeof in);
    memcpy(&in,guest,len<sizeof in ? len : sizeof in);
    if (in.family!=PS_AF_INET) return E_AFNOSUPPORT;
    memset(out,0,sizeof *out);
    out->sin_family=AF_INET; out->sin_port=in.port; out->sin_addr.s_addr=in.addr;
    return 0;
}
static void from_native(const struct sockaddr_in *native, void *guest, uint32_t *len) {
    if (!guest || !len) return;
    PsSockaddrIn out;
    memset(&out,0,sizeof out);
    out.len=sizeof out; out.family=PS_AF_INET; out.port=native->sin_port; out.addr=native->sin_addr.s_addr;
    memcpy(guest,&out,*len<sizeof out ? *len : sizeof out);
    *len=sizeof out;
}
static const char *addr_text(const struct sockaddr_in *a, char *out, size_t size) {
    char ip[32];
    ip_text(a->sin_addr.s_addr,ip,sizeof ip);
    snprintf(out,size,"%s:%u",ip,ntohs(a->sin_port));
    return out;
}

/* ---- libSceNet: sockets ---- */
static ABI int32_t net_init(void) { return 0; }
static ABI int32_t net_term(void) { return 0; }
static ABI int32_t *net_errno_loc(void) { return &net_errno; }
static ABI int32_t net_pool_create(const char *name,int size,int flags) { (void)name; (void)size; (void)flags; return 1; }
static ABI int32_t net_pool_destroy(int id) { (void)id; return 0; }
static ABI int32_t net_pool_stats(int id,void *stats) { (void)id; if (stats) memset(stats,0,32); return 0; }

static ABI int32_t net_socket(const char *name,int family,int type,int protocol) {
    (void)protocol;
    if (family!=PS_AF_INET) return fail(E_AFNOSUPPORT);
    int native_type, native_protocol;
    switch (type) {
    case PS_SOCK_STREAM: case PS_SOCK_STREAM_P2P: native_type=SOCK_STREAM; native_protocol=IPPROTO_TCP; break;
    case PS_SOCK_DGRAM: case PS_SOCK_DGRAM_P2P: native_type=SOCK_DGRAM; native_protocol=IPPROTO_UDP; break;
    default: printf("Net: socket '%s' of type %d refused (raw sockets)\n",name ? name : "",type); return fail(E_PROTONOSUPPORT);
    }
    NativeSocket s=socket(AF_INET,native_type,native_protocol);
    if (s==NATIVE_INVALID) return fail(native_error());
    const int id=object_new(OBJ_SOCKET,name);
    if (!id) { native_close(s); return fail(E_NOBUFS); }
    objects[id].s=s; objects[id].type=type;
    printf("Net: socket %d '%s' %s%s\n",id,name ? name : "",native_type==SOCK_STREAM ? "TCP" : "UDP",
           type==PS_SOCK_DGRAM_P2P || type==PS_SOCK_STREAM_P2P ? " (P2P type: virtual port ignored)" : "");
    return id;
}
static ABI int32_t net_socket_close(int id) {
    pthread_mutex_lock(&net_lock);
    NetObj *o=object(id,OBJ_SOCKET);
    if (!o) { pthread_mutex_unlock(&net_lock); return fail(E_BADF); }
    NativeSocket s=o->s;
    o->kind=OBJ_FREE;
    pthread_mutex_unlock(&net_lock);
    native_close(s);
    if (cfg.trace) printf("Net: socket %d closed\n",id);
    return 0;
}
static ABI int32_t net_socket_abort(int id,int flags) {
    (void)flags;
    NetObj *o=object(id,OBJ_SOCKET);
    if (!o) return fail(E_BADF);
#ifdef _WIN32
    shutdown(o->s,SD_BOTH);
#else
    shutdown(o->s,SHUT_RDWR);
#endif
    return 0;
}
#define SOCKET_OR_FAIL(o, id) NetObj *o=object(id,OBJ_SOCKET); if (!o) return fail(E_BADF)
static void log_send_caller(NetObj *o, int id, void *ret);

static ABI int32_t net_connect(int id,const void *addr,uint32_t len) {
    SOCKET_OR_FAIL(o,id);
    struct sockaddr_in to;
    int e=to_native(addr,len,&to);
    if (e) return fail(e);
    char text[48];
    addr_text(&to,text,sizeof text);
    if (!o->sent_logged && !o->received_logged) log_send_caller(o,id,__builtin_return_address(0));
    if (!allowed(to.sin_addr.s_addr)) {
        printf("Net: connect %d '%s' to %s refused: not the private server\n",id,o->name,text);
        return fail(E_NETUNREACH);
    }
    const int result=connect(o->s,(struct sockaddr *)&to,sizeof to);
    if (result) {
        e=native_error();
        if (e==E_AGAIN) e=E_INPROGRESS; /* Winsock's non-blocking connect */
        if (e!=E_INPROGRESS) printf("Net: connect %d '%s' to %s failed (errno %d)\n",id,o->name,text,e);
        else printf("Net: connect %d '%s' to %s (in progress)\n",id,o->name,text);
        return fail(e);
    }
    printf("Net: connect %d '%s' to %s\n",id,o->name,text);
    return 0;
}
static ABI int32_t net_bind(int id,const void *addr,uint32_t len) {
    SOCKET_OR_FAIL(o,id);
    struct sockaddr_in at;
    int e=to_native(addr,len,&at);
    if (e) return fail(e);
    if (bind(o->s,(struct sockaddr *)&at,sizeof at)) {
        e=native_error();
        printf("Net: bind %d '%s' to port %u failed (errno %d)\n",id,o->name,ntohs(at.sin_port),e);
        return fail(e);
    }
    printf("Net: bind %d '%s' to port %u\n",id,o->name,ntohs(at.sin_port));
    return 0;
}
static ABI int32_t net_listen(int id,int backlog) {
    SOCKET_OR_FAIL(o,id);
    if (listen(o->s,backlog)) return fail(native_error());
    printf("Net: listen %d '%s'\n",id,o->name);
    return 0;
}
static ABI int32_t net_accept(int id,void *addr,uint32_t *len) {
    SOCKET_OR_FAIL(o,id);
    struct sockaddr_in from;
    socklen_t from_len=sizeof from;
    NativeSocket s=accept(o->s,(struct sockaddr *)&from,&from_len);
    if (s==NATIVE_INVALID) return fail(native_error());
    char text[48];
    addr_text(&from,text,sizeof text);
    if (!allowed(from.sin_addr.s_addr)) {
        printf("Net: accept on %d '%s' from %s refused: not the private server\n",id,o->name,text);
        native_close(s);
        return fail(E_CONNABORTED);
    }
    const int child=object_new(OBJ_SOCKET,o->name);
    if (!child) { native_close(s); return fail(E_NOBUFS); }
    objects[child].s=s; objects[child].type=o->type;
    from_native(&from,addr,len);
    printf("Net: accept on %d '%s': socket %d from %s\n",id,o->name,child,text);
    return child;
}
/* MSG_DONTWAIT on a blocking socket: Winsock has no such flag, so readiness is checked first. */
static int would_block(NetObj *o, int flags, int write) {
    return (flags & PS_MSG_DONTWAIT) && !o->nbio && wait_ready(o->s,write,0)<=0;
}
static int native_flags(int flags) {
    int f=0;
    if (flags & PS_MSG_PEEK) f|=MSG_PEEK;
    if (flags & PS_MSG_WAITALL) f|=MSG_WAITALL;
#ifdef MSG_NOSIGNAL
    f|=MSG_NOSIGNAL;
#endif
    return f;
}
static void log_packet(NetObj *o, int id, const char *what, const void *data, int64_t size, int *logged) {
    if (size<=0 || (!cfg.trace && *logged)) return;
    *logged=1;
    char label[96];
    snprintf(label,sizeof label,"%s '%s'",what,o->name);
    hexdump(label,id,data,(size_t)size);
}
/* Guest return address of the first send on a socket: pinpoints the protocol's
 * send site (image offset) without guessing. Same frame as the send call. */
static void log_send_caller(NetObj *o, int id, void *ret) {
    uint64_t image_size=0;
    const uintptr_t image=runtime_probe_image(&image_size);
    printf("Net: socket %d '%s' first use from guest %p",id,o->name,ret);
    if (image && image_size && (uintptr_t)ret>=image && (uintptr_t)ret<image+image_size)
        printf(" (image +0x%llx)",(unsigned long long)((uintptr_t)ret-image));
    printf("\n");
    /* The send wrapper is one frame below the real builder: scan this thread's stack
     * for more image return addresses (each verified by a preceding call opcode).
     * Faults (guard pages) resume below via the runtime's recovery point. */
    if (image && image_size) {
        static int warned;
        sigjmp_buf jb;
        runtime_fault_recover=&jb;
        int prospects=0, confirmed=0;
        if (!sigsetjmp(jb,1)) {
            const uintptr_t rsp=(uintptr_t)__builtin_frame_address(0);
            for (uintptr_t a=(rsp+7)&~(uintptr_t)7;
                 a<rsp+262144 && confirmed<16 && prospects<4000; a+=8) {
                const uintptr_t v=*(uintptr_t volatile *)a;
                if (v<image || v>=image+image_size || v-image<16) continue;
                ++prospects;
                const unsigned char *p=(const unsigned char *)v;
                /* Return address: preceded by E8 (direct) or FF /2 (register/memory
                 * indirect: FF D0-D7, FF 10-17 incl. [rip+rel], FF 50-57, FF 90-97). */
                const int direct=p[-5]==0xe8;
                int indirect=0;
                if (!direct && p[-3]==0xff) {
                    const unsigned char m=p[-2];
                    indirect=(m>=0xd0 && m<=0xd7) || (m>=0x10 && m<=0x17) ||
                             (m>=0x50 && m<=0x57) || (m>=0x90 && m<=0x97);
                }
                if (!direct && !indirect && p[-2]==0xff && p[-1]>=0xd0 && p[-1]<=0xd7)
                    indirect=1;
                if (!direct && !indirect) continue;
                printf("Net: socket %d stack: image +0x%llx (%s call)\n",
                       id,(unsigned long long)(v-image),direct ? "direct" : "in");
                ++confirmed;
            }
        }
        runtime_fault_recover=NULL;
        if (!warned && !confirmed) {
            warned=1;
            printf("Net: socket %d stack: no guest frames found (build without frame pointers?)\n",id);
        }
    }
}
static ABI int32_t net_send(int id,const void *data,uint64_t size,int flags) {
    SOCKET_OR_FAIL(o,id);
    if (would_block(o,flags,1)) return fail(E_AGAIN);
    const int n=send(o->s,data,(int)size,native_flags(flags & ~(PS_MSG_PEEK|PS_MSG_WAITALL)));
    if (n<0) return fail(native_error());
    if (!o->sent_logged) log_send_caller(o,id,__builtin_return_address(0));
    if (o->name[0]=='S' && size==28 && data) {
        static const unsigned char hello_prefix[20]={
            0xc8,0,0,0, 0xc8,0,0,0, 0xd2,0,0,0, 0xdc,0,0,0, 0,0,1,0};
        if (!memcmp(data,hello_prefix,sizeof hello_prefix))
            dw_dump_task((const unsigned char *)data+20);
    }
    log_packet(o,id,"send",data,n,&o->sent_logged);
    return n;
}
static ABI int32_t net_recv(int id,void *data,uint64_t size,int flags) {
    SOCKET_OR_FAIL(o,id);
    if (would_block(o,flags,0)) return fail(E_AGAIN);
    const int n=recv(o->s,data,(int)size,native_flags(flags));
    if (n<0) return fail(native_error());
    if (!o->received_logged) log_send_caller(o,id,__builtin_return_address(0));
    log_packet(o,id,"recv",data,n,&o->received_logged);
    return n;
}
static ABI int32_t net_sendto(int id,const void *data,uint64_t size,int flags,const void *addr,uint32_t len) {
    SOCKET_OR_FAIL(o,id);
    if (!addr) return net_send(id,data,size,flags);
    struct sockaddr_in to;
    const int e=to_native(addr,len,&to);
    if (e) return fail(e);
    if (!allowed(to.sin_addr.s_addr)) {
        char text[48];
        printf("Net: sendto %d '%s' to %s refused: not the private server\n",id,o->name,addr_text(&to,text,sizeof text));
        return fail(E_HOSTUNREACH);
    }
    if (would_block(o,flags,1)) return fail(E_AGAIN);
    const int n=sendto(o->s,data,(int)size,native_flags(flags & ~(PS_MSG_PEEK|PS_MSG_WAITALL)),(struct sockaddr *)&to,sizeof to);
    if (n<0) return fail(native_error());
    if (!o->sent_logged) log_send_caller(o,id,__builtin_return_address(0));
    if (!o->sent_logged || cfg.trace) {
        char text[48];
        printf("Net: sendto %d '%s' to %s\n",id,o->name,addr_text(&to,text,sizeof text));
    }
    log_packet(o,id,"sendto",data,n,&o->sent_logged);
    return n;
}
static ABI int32_t net_recvfrom(int id,void *data,uint64_t size,int flags,void *addr,uint32_t *len) {
    SOCKET_OR_FAIL(o,id);
    if (would_block(o,flags,0)) return fail(E_AGAIN);
    struct sockaddr_in from;
    socklen_t from_len=sizeof from;
    memset(&from,0,sizeof from);
    const int n=recvfrom(o->s,data,(int)size,native_flags(flags & ~PS_MSG_WAITALL),(struct sockaddr *)&from,&from_len);
    if (n<0) {
#ifdef _WIN32
        /* A UDP reply "port unreachable" resets the socket on Windows: report it as nothing. */
        if (WSAGetLastError()==WSAECONNRESET) return fail(E_AGAIN);
#endif
        return fail(native_error());
    }
    from_native(&from,addr,len);
    if (!o->received_logged) log_send_caller(o,id,__builtin_return_address(0));
    log_packet(o,id,"recvfrom",data,n,&o->received_logged);
    return n;
}
static ABI int32_t net_shutdown(int id,int how) {
    SOCKET_OR_FAIL(o,id);
    return shutdown(o->s,how) ? fail(native_error()) : 0;
}
static ABI int32_t net_getsockname(int id,void *addr,uint32_t *len) {
    SOCKET_OR_FAIL(o,id);
    struct sockaddr_in me;
    socklen_t me_len=sizeof me;
    if (getsockname(o->s,(struct sockaddr *)&me,&me_len)) return fail(native_error());
    from_native(&me,addr,len);
    return 0;
}
static ABI int32_t net_getpeername(int id,void *addr,uint32_t *len) {
    SOCKET_OR_FAIL(o,id);
    struct sockaddr_in peer;
    socklen_t peer_len=sizeof peer;
    if (getpeername(o->s,(struct sockaddr *)&peer,&peer_len)) return fail(native_error());
    from_native(&peer,addr,len);
    return 0;
}
static int read_int(const void *value, uint32_t len) {
    int v=0;
    if (value && len>=1) memcpy(&v,value,len<sizeof v ? len : sizeof v);
    return v;
}
static ABI int32_t net_setsockopt(int id,int level,int option,const void *value,uint32_t len) {
    SOCKET_OR_FAIL(o,id);
    const int v=read_int(value,len);
    int native_level=-1, native_option=-1;
    if (level==PS_SOL_SOCKET) {
        switch (option) {
        case 0x4: native_level=SOL_SOCKET; native_option=SO_REUSEADDR; break;
        case 0x8: native_level=SOL_SOCKET; native_option=SO_KEEPALIVE; break;
        case 0x20: native_level=SOL_SOCKET; native_option=SO_BROADCAST; break;
        case 0x1001: native_level=SOL_SOCKET; native_option=SO_SNDBUF; break;
        case 0x1002: native_level=SOL_SOCKET; native_option=SO_RCVBUF; break;
        case 0x80: { /* linger: two ints on the console */
            int pair[2]={0,0};
            if (value && len>=8) memcpy(pair,value,8);
            struct linger l;
            l.l_onoff=(unsigned short)(pair[0]!=0); l.l_linger=(unsigned short)pair[1];
            return setsockopt(o->s,SOL_SOCKET,SO_LINGER,(const char *)&l,sizeof l) ? fail(native_error()) : 0;
        }
        case 0x1105: set_timeout(o->s,SO_SNDTIMEO,(uint32_t)v); return 0;
        case 0x1106: set_timeout(o->s,SO_RCVTIMEO,(uint32_t)v); return 0;
        case 0x1200: o->nbio=v!=0; set_nonblocking(o->s,o->nbio); return 0;
        default: /* REUSEPORT, ONESBCAST, crypto/signature (P2P), policy, name, priority, ... */
            printf("Net: setsockopt %d '%s' option 0x%x = %d accepted (no host equivalent)\n",id,o->name,option,v);
            return 0;
        }
    } else if (level==6) {
        if (option!=1) return 0; /* TCP_MAXSEG / MSS: left to the host */
        native_level=IPPROTO_TCP; native_option=TCP_NODELAY;
    } else if (level==0) {
        if (option==3) { native_level=IPPROTO_IP; native_option=IP_TOS; }
        else if (option==4) { native_level=IPPROTO_IP; native_option=IP_TTL; }
        else return 0;
    } else {
        printf("Net: setsockopt %d '%s' level %d option 0x%x accepted (unknown)\n",id,o->name,level,option);
        return 0;
    }
    return setsockopt(o->s,native_level,native_option,(const char *)&v,sizeof v) ? fail(native_error()) : 0;
}
static ABI int32_t net_getsockopt(int id,int level,int option,void *value,uint32_t *len) {
    SOCKET_OR_FAIL(o,id);
    if (!value || !len || *len<4) return fail(E_INVAL);
    int v=0;
    socklen_t native_len=sizeof v;
    if (level==PS_SOL_SOCKET && option==0x1007) {
        getsockopt(o->s,SOL_SOCKET,SO_ERROR,(char *)&v,&native_len);
        v=bsd_from_native_code(v);
    } else if (level==PS_SOL_SOCKET && option==0x1008) v=o->type;
    else if (level==PS_SOL_SOCKET && option==0x1200) v=o->nbio;
    else if (level==PS_SOL_SOCKET && (option==0x1001 || option==0x1002))
        getsockopt(o->s,SOL_SOCKET,option==0x1001 ? SO_SNDBUF : SO_RCVBUF,(char *)&v,&native_len);
    else if (level==6 && option==1) getsockopt(o->s,IPPROTO_TCP,TCP_NODELAY,(char *)&v,&native_len);
    else printf("Net: getsockopt %d '%s' level %d option 0x%x answered 0\n",id,o->name,level,option);
    memcpy(value,&v,4); *len=4;
    return 0;
}

/* ---- libSceNet: epoll (timeouts in microseconds) ---- */
static ABI int32_t net_epoll_create(const char *name,int flags) {
    if (flags) return fail(E_INVAL);
    const int id=object_new(OBJ_EPOLL,name);
    return id ? id : fail(E_NOBUFS);
}
static ABI int32_t net_epoll_destroy(int id) {
    pthread_mutex_lock(&net_lock);
    NetObj *o=object(id,OBJ_EPOLL);
    if (o) o->kind=OBJ_FREE;
    pthread_mutex_unlock(&net_lock);
    return o ? 0 : fail(E_BADF);
}
static ABI int32_t net_epoll_control(int id,int op,int target,const PsEpollEvent *event) {
    pthread_mutex_lock(&net_lock);
    NetObj *o=object(id,OBJ_EPOLL);
    int result=0, found=-1;
    if (!o) { result=E_BADF; goto done; }
    for (int i=0;i<o->watches;++i) if (o->watch[i].id==target) found=i;
    if (op==1) {                                         /* ADD */
        if (!event) { result=E_INVAL; goto done; }
        if (found>=0) { result=E_EXIST; goto done; }
        if (!object(target,OBJ_SOCKET) && !object(target,OBJ_RESOLVER)) { result=E_BADF; goto done; }
        if (o->watches>=64) { result=E_NOSPC; goto done; }
        o->watch[o->watches++]=(Watch){target,event->events,event->data,0};
    } else if (op==2) {                                  /* MOD */
        if (!event) { result=E_INVAL; goto done; }
        if (found<0) { result=E_BADF; goto done; }
        o->watch[found].events=event->events; o->watch[found].data=event->data;
    } else if (op==3) {                                  /* DEL */
        if (found<0) { result=E_BADF; goto done; }
        o->watch[found]=o->watch[--o->watches];
    } else result=E_INVAL;
done:
    pthread_mutex_unlock(&net_lock);
    return result ? fail(result) : 0;
}
static ABI int32_t net_epoll_abort(int id,int flags) {
    (void)flags;
    NetObj *o=object(id,OBJ_EPOLL);
    if (!o) return fail(E_BADF);
    o->abort_wait=1;
    return 0;
}
static void sleep_us(int64_t us) {
#ifdef _WIN32
    compat_sleep_ns((uint64_t)us*1000);
#else
    struct timespec t={(time_t)(us/1000000),(long)(us%1000000)*1000};
    nanosleep(&t,NULL);
#endif
}
static int64_t now_us(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC,&t);
    return (int64_t)t.tv_sec*1000000+t.tv_nsec/1000;
}
static ABI int32_t net_epoll_wait(int id,PsEpollEvent *events,int max,int timeout) {
    if (!events || max<=0) return fail(E_INVAL);
    const int64_t deadline=timeout<0 ? -1 : now_us()+timeout;
    for (;;) {
        NativePollFd fds[64];
        Watch sockets[64];
        int count=0, ready=0;
        pthread_mutex_lock(&net_lock);
        NetObj *o=object(id,OBJ_EPOLL);
        if (!o) { pthread_mutex_unlock(&net_lock); return fail(E_BADF); }
        if (o->abort_wait) { o->abort_wait=0; pthread_mutex_unlock(&net_lock); return fail(E_INTR); }
        for (int i=0;i<o->watches && ready<max;++i) {
            Watch *w=&o->watch[i];
            NetObj *r=object(w->id,OBJ_RESOLVER);
            if (r && r->resolved) {                      /* an asynchronous resolution finished */
                r->resolved=0;
                events[ready++]=(PsEpollEvent){PS_EPOLLIN,0,(uint64_t)w->id,w->data};
                continue;
            }
            NetObj *s=object(w->id,OBJ_SOCKET);
            if (!s || !(w->events & (PS_EPOLLIN|PS_EPOLLOUT))) continue;
            fds[count].fd=s->s; fds[count].revents=0;
            fds[count].events=(short)(((w->events & PS_EPOLLIN) ? POLLIN : 0) | ((w->events & PS_EPOLLOUT) ? POLLOUT : 0));
            sockets[count++]=*w;
        }
        pthread_mutex_unlock(&net_lock);
        if (ready) return ready;
        int64_t left=deadline<0 ? 20000 : deadline-now_us();
        if (left<0) left=0;
        const int slice_ms=(int)(left>20000 ? 20 : (left+999)/1000);
        if (count) {
            const int n=native_poll(fds,(unsigned long)count,slice_ms);
            if (n<0) return fail(native_error());
            for (int i=0;i<count && ready<max;++i) {
                const short r=fds[i].revents;
                if (!r) continue;
                uint32_t e=0;
                if (r & (POLLIN|POLLHUP)) e|=PS_EPOLLIN;
                if (r & POLLOUT) e|=PS_EPOLLOUT;
                if (r & (POLLERR|POLLNVAL)) e|=PS_EPOLLERR;
                if (r & POLLHUP) e|=PS_EPOLLHUP;
                e&=sockets[i].events|PS_EPOLLERR|PS_EPOLLHUP;
                if (e) events[ready++]=(PsEpollEvent){e,0,(uint64_t)sockets[i].id,sockets[i].data};
            }
            if (ready) return ready;
        } else if (slice_ms) sleep_us((int64_t)slice_ms*1000);
        if (deadline>=0 && now_us()>=deadline) return 0;
    }
}

/* ---- libSceNet: resolver. Every name answers the private server. ---- */
static ABI int32_t net_resolver_create(const char *name,int pool,int flags) {
    (void)pool; (void)flags;
    const int id=object_new(OBJ_RESOLVER,name);
    return id ? id : fail(E_NOBUFS);
}
static ABI int32_t net_resolver_destroy(int id) {
    pthread_mutex_lock(&net_lock);
    NetObj *o=object(id,OBJ_RESOLVER);
    if (o) o->kind=OBJ_FREE;
    pthread_mutex_unlock(&net_lock);
    return o ? 0 : fail(E_BADF);
}
static ABI int32_t net_resolver_ntoa(int id,const char *host,uint32_t *addr,int timeout,int retry,int flags) {
    (void)timeout; (void)retry;
    NetObj *o=object(id,OBJ_RESOLVER);
    if (!o) return fail(E_BADF);
    if (!host || !addr) return fail(E_INVAL);
    uint32_t literal;
    if (!(flags & 0x10000) && parse_ipv4(host,&literal)) *addr=literal;
    else {
        *addr=cfg.server;
        if (first_time_host(host)) printf("Net: resolve '%s' -> %s (private server)\n",host,cfg.server_text);
    }
    if (flags & 1) o->resolved=1;                        /* asynchronous: report through epoll */
    return 0;
}
static ABI int32_t net_resolver_abort(int id,int flags) { (void)id; (void)flags; return 0; }

/* ---- libSceNetCtl: connected by cable, address obtained ---- */
typedef void (ABI *NetCtlCallback)(int event,void *arg);
static struct { NetCtlCallback cb; void *arg; int fired; } netctl_callbacks[2][8];
static ABI int32_t netctl_state(int32_t *state) { if (!state) return NET_CTL_INVALID_ADDR; *state=3; return 0; }
static ABI int32_t netctl_info(int code,void *info) {
    if (!info) return NET_CTL_INVALID_ADDR;
    char *text=info;
    uint32_t value=0;
    switch (code) {
    case 1: value=0; break;                                       /* device: wired */
    case 2: { const unsigned char mac[6]={0x02,0x53,0x46,(unsigned char)(cfg.account_id>>16),(unsigned char)(cfg.account_id>>8),(unsigned char)cfg.account_id};
              memcpy(info,mac,6); return 0; }
    case 3: value=1500; break;                                    /* MTU */
    case 4: value=1; break;                                       /* link connected */
    case 11: value=0; break;                                      /* IP config: DHCP */
    case 12: case 13: case 20: text[0]=0; return 0;               /* host names, proxy server */
    case 14: ip_text(cfg.local_ip,text,16); return 0;
    case 15: snprintf(text,16,"255.255.255.0"); return 0;
    case 16: { uint32_t gateway=(cfg.local_ip & htonl(0xffffff00)) | htonl(1); ip_text(gateway,text,16); return 0; }
    case 17: case 18: ip_text(cfg.server,text,16); return 0;     /* DNS: the private server */
    case 19: value=0; break;                                      /* no proxy */
    case 21: { uint16_t port=0; memcpy(info,&port,2); return 0; }
    default: printf("Net: NetCtl info %d answered 0\n",code); value=0; break;
    }
    memcpy(info,&value,4);
    return 0;
}
static int32_t netctl_register_in(int list,void *cb,void *arg,int32_t *cid) {
    if (!cid || !cb) return NET_CTL_INVALID_ADDR;
    pthread_mutex_lock(&net_lock);
    for (int i=0;i<8;++i) if (!netctl_callbacks[list][i].cb) {
        netctl_callbacks[list][i].cb=(NetCtlCallback)cb; netctl_callbacks[list][i].arg=arg; netctl_callbacks[list][i].fired=0;
        pthread_mutex_unlock(&net_lock);
        *cid=i; return 0;
    }
    pthread_mutex_unlock(&net_lock);
    return (int32_t)0x80412102; /* CALLBACK_MAX */
}
/* Each callback hears "address obtained" once, on the first check after it registered. */
static int32_t netctl_check_in(int list) {
    for (int i=0;i<8;++i) {
        pthread_mutex_lock(&net_lock);
        NetCtlCallback cb=netctl_callbacks[list][i].cb;
        void *arg=netctl_callbacks[list][i].arg;
        const int fire=cb && !netctl_callbacks[list][i].fired;
        if (fire) netctl_callbacks[list][i].fired=1;
        pthread_mutex_unlock(&net_lock);
        if (fire) cb(3,arg); /* IPOBTAINED */
    }
    return 0;
}
static int32_t netctl_unregister_in(int list,int cid) {
    if (cid<0 || cid>=8) return (int32_t)0x80412103; /* ID_NOT_FOUND */
    pthread_mutex_lock(&net_lock);
    netctl_callbacks[list][cid].cb=NULL;
    pthread_mutex_unlock(&net_lock);
    return 0;
}
static ABI int32_t netctl_register(void *cb,void *arg,int32_t *cid) { return netctl_register_in(0,cb,arg,cid); }
static ABI int32_t netctl_check(void) { return netctl_check_in(0); }
static ABI int32_t netctl_unregister(int cid) { return netctl_unregister_in(0,cid); }
static ABI int32_t netctl_register_toolkit(void *cb,void *arg,int32_t *cid) { return netctl_register_in(1,cb,arg,cid); }
static ABI int32_t netctl_check_toolkit(void) { return netctl_check_in(1); }
static ABI int32_t netctl_unregister_toolkit(int cid) { return netctl_unregister_in(1,cid); }
static ABI int32_t netctl_nat(uint32_t *info) {
    if (!info) return NET_CTL_INVALID_ADDR;
    info[1]=1; info[2]=2; info[3]=cfg.local_ip; /* STUN ok, NAT type 2, mapped address */
    return 0;
}
static ABI int32_t ok_void(void) { return 0; }
static ABI int32_t lib_init_one(void) { return 1; }

/* ---- NpManager / NpAuth: user 1 signed in ---- */
static int user_signed_in(int32_t user) { return user==1; }
typedef struct { char data[16]; int8_t term; int8_t dummy[3]; } NpOnlineId;
typedef struct { NpOnlineId handle; uint8_t opt[8]; uint8_t reserved[8]; } NpId;
static void fill_online_id(NpOnlineId *id) {
    memset(id,0,sizeof *id);
    memcpy(id->data,cfg.online_id,strlen(cfg.online_id));
}
static ABI int32_t np_state(int32_t user,int32_t *state) {
    if (!state) return NP_INVALID_ARGUMENT;
    *state=user_signed_in(user) ? 2 : 1; /* SIGNED_IN / SIGNED_OUT */
    return 0;
}
static ABI int32_t np_online_id(int32_t user,NpOnlineId *id) {
    if (!id) return NP_INVALID_ARGUMENT;
    if (!user_signed_in(user)) return NP_SIGNED_OUT;
    fill_online_id(id); return 0;
}
static ABI int32_t np_npid(int32_t user,NpId *id) {
    if (!id) return NP_INVALID_ARGUMENT;
    if (!user_signed_in(user)) return NP_SIGNED_OUT;
    memset(id,0,sizeof *id);
    fill_online_id(&id->handle); return 0;
}
static ABI int32_t np_account_id(int32_t user,uint64_t *id) {
    if (!id) return NP_INVALID_ARGUMENT;
    if (!user_signed_in(user)) { *id=0; return NP_SIGNED_OUT; }
    *id=cfg.account_id; return 0;
}
static ABI int32_t np_user_by_account(uint64_t account,int32_t *user) {
    if (!user || !account) return NP_INVALID_ARGUMENT;
    if (account!=cfg.account_id) return (int32_t)0x80550009; /* USER_NOT_FOUND */
    *user=1; return 0;
}
/* Requests (NpManager and NpAuth): everything completes at once. */
static struct { int used, async; int32_t result; } requests[64];
#define REQUEST_BASE 0x100
static int32_t request_new(int async) {
    pthread_mutex_lock(&net_lock);
    for (int i=0;i<64;++i) if (!requests[i].used) {
        requests[i].used=1; requests[i].async=async; requests[i].result=0;
        pthread_mutex_unlock(&net_lock);
        return REQUEST_BASE+i;
    }
    pthread_mutex_unlock(&net_lock);
    return (int32_t)0x80550015; /* REQUEST_MAX */
}
static int request_index(int32_t id) { const int i=id-REQUEST_BASE; return i>=0 && i<64 && requests[i].used ? i : -1; }
/* Sync requests return the result; async ones return 0 and keep it for PollAsync. */
static int32_t request_complete(int32_t id,int32_t result) {
    const int i=request_index(id);
    if (i<0) return NP_REQUEST_NOT_FOUND;
    requests[i].result=result;
    return requests[i].async ? 0 : result;
}
static ABI int32_t np_create_request(void) { return request_new(0); }
static ABI int32_t np_create_async(const void *param) { (void)param; return request_new(1); }
static ABI int32_t np_delete_request(int32_t id) { const int i=request_index(id); if (i<0) return NP_REQUEST_NOT_FOUND; requests[i].used=0; return 0; }
static ABI int32_t np_abort_request(int32_t id) { return request_index(id)<0 ? NP_REQUEST_NOT_FOUND : 0; }
static ABI int32_t np_poll(int32_t id,int32_t *result) {
    const int i=request_index(id);
    if (i<0) return NP_REQUEST_NOT_FOUND;
    if (result) *result=requests[i].result;
    return 0; /* finished */
}
static ABI int32_t np_check_availability_a(int32_t req,int32_t user) {
    return request_complete(req,user_signed_in(user) ? 0 : NP_SIGNED_OUT);
}
typedef struct { uint64_t size; int32_t user; uint8_t pad[4]; uint64_t features; uint8_t reserved[32]; } NpCheckPlusParameter;
static ABI int32_t np_check_plus(int32_t req,const NpCheckPlusParameter *param,uint8_t *result) {
    if (!param || !result) return NP_INVALID_ARGUMENT;
    memset(result,0,33);
    result[0]=user_signed_in(param->user);              /* PS Plus: authorized */
    printf("Net: PSN: PS Plus check (features 0x%llx): granted\n",(unsigned long long)param->features);
    return request_complete(req,user_signed_in(param->user) ? 0 : NP_SIGNED_OUT);
}
static ABI int32_t np_parental_a(int32_t req,int32_t user,int8_t *age,uint8_t *info) {
    if (!age || !info) return NP_INVALID_ARGUMENT;
    *age=30; memset(info,0,3);                           /* no restrictions */
    return request_complete(req,user_signed_in(user) ? 0 : NP_SIGNED_OUT);
}
/* State callbacks: "signed in" for user 1, once, on the first check after registering. */
typedef void (ABI *NpStateLegacy)(int32_t user,int32_t state,NpId *id,void *arg);
typedef void (ABI *NpStateToolkit)(int32_t user,int32_t state,void *arg);
static struct { void *cb, *arg; int fired; } np_legacy, np_toolkit;
static ABI int32_t np_register_legacy(void *cb,void *arg) {
    if (!cb) return NP_INVALID_ARGUMENT;
    pthread_mutex_lock(&net_lock); np_legacy.cb=cb; np_legacy.arg=arg; np_legacy.fired=0; pthread_mutex_unlock(&net_lock);
    return 1;
}
static ABI int32_t np_unregister_legacy(void) { pthread_mutex_lock(&net_lock); np_legacy.cb=NULL; pthread_mutex_unlock(&net_lock); return 0; }
static ABI int32_t np_register_toolkit(void *cb,void *arg) {
    if (!cb) return NP_INVALID_ARGUMENT;
    pthread_mutex_lock(&net_lock); np_toolkit.cb=cb; np_toolkit.arg=arg; np_toolkit.fired=0; pthread_mutex_unlock(&net_lock);
    return 0;
}
static ABI int32_t np_unregister_toolkit(void) { pthread_mutex_lock(&net_lock); np_toolkit.cb=NULL; pthread_mutex_unlock(&net_lock); return 0; }
static ABI int32_t np_check_callback(void) {
    pthread_mutex_lock(&net_lock);
    void *legacy=np_legacy.fired ? NULL : np_legacy.cb, *legacy_arg=np_legacy.arg;
    void *toolkit=np_toolkit.fired ? NULL : np_toolkit.cb, *toolkit_arg=np_toolkit.arg;
    if (legacy) np_legacy.fired=1;
    if (toolkit) np_toolkit.fired=1;
    pthread_mutex_unlock(&net_lock);
    if (legacy || toolkit) printf("Net: PSN: user 1 '%s' signed in\n",cfg.online_id);
    if (legacy) { NpId id; memset(&id,0,sizeof id); fill_online_id(&id.handle); ((NpStateLegacy)legacy)(1,2,&id,legacy_arg); }
    if (toolkit) ((NpStateToolkit)toolkit)(1,2,toolkit_arg);
    return 0;
}
/* Authorization codes and ID tokens: made up, for the private server only. */
typedef struct { uint64_t size; int32_t user; uint8_t pad[4]; const char *client_id; const char *scope; } NpAuthCodeParameterA;
typedef struct { uint64_t size; int32_t user; uint8_t pad[4]; const char *client_id; const char *client_secret; const char *scope; } NpAuthTokenParameterA;
static ABI int32_t np_auth_code_a(int32_t req,const NpAuthCodeParameterA *param,char *code,int32_t *issuer) {
    if (!param || !code) return NP_AUTH_INVALID_ARGUMENT;
    printf("Net: PSN: authorization code for client '%.129s', scope '%s'\n",param->client_id ? param->client_id : "",
           param->scope ? param->scope : "");
    memset(code,0,136);
    snprintf(code,129,"SACREDFIRE-%s-%016llx",cfg.online_id,(unsigned long long)cfg.account_id);
    if (issuer) *issuer=256;
    return request_complete(req,user_signed_in(param->user) ? 0 : NP_SIGNED_OUT);
}
static ABI int32_t np_id_token_a(int32_t req,const NpAuthTokenParameterA *param,char *token) {
    if (!param || !token) return NP_AUTH_INVALID_ARGUMENT;
    printf("Net: PSN: ID token for client '%.129s', scope '%s'\n",param->client_id ? param->client_id : "",
           param->scope ? param->scope : "");
    memset(token,0,4104);
    snprintf(token,4097,"sacredfire.%s.%016llx",cfg.online_id,(unsigned long long)cfg.account_id);
    return request_complete(req,user_signed_in(param->user) ? 0 : NP_SIGNED_OUT);
}

/* ---- libSceHttp: plain HTTP to the private server ---- */
typedef struct { char *name, *value; } Header;
typedef struct {
    int kind;                       /* 0 free, 1 template, 2 connection, 3 request */
    int parent;
    char *url;
    char method[16];
    char user_agent[128];
    Header headers[32];
    int header_count;
    uint32_t connect_timeout_us;
    /* response */
    int sent, status;
    char *response_headers;
    size_t response_headers_size;
    char *body;
    size_t body_size, body_read;
    void *epoll;
    void *user_arg;
    int reported;
} HttpObj;
#define MAX_HTTP 256
static HttpObj http[MAX_HTTP];
static HttpObj *http_get(int id) { return id>0 && id<MAX_HTTP && http[id].kind ? &http[id] : NULL; }
static int http_new(int kind,int parent) {
    pthread_mutex_lock(&net_lock);
    for (int id=1; id<MAX_HTTP; ++id) if (!http[id].kind) {
        memset(&http[id],0,sizeof http[id]);
        http[id].kind=kind; http[id].parent=parent;
        pthread_mutex_unlock(&net_lock);
        return id;
    }
    pthread_mutex_unlock(&net_lock);
    return HTTP_OUT_OF_MEMORY;
}
static void http_free_response(HttpObj *h) {
    free(h->response_headers); free(h->body);
    h->response_headers=h->body=NULL; h->response_headers_size=h->body_size=h->body_read=0;
    h->sent=0; h->status=0; h->reported=0;
}
static void http_free(HttpObj *h) {
    for (int i=0;i<h->header_count;++i) { free(h->headers[i].name); free(h->headers[i].value); }
    free(h->url);
    http_free_response(h);
    h->kind=0;
}
static char *dup_text(const char *s) { if (!s) s=""; char *d=malloc(strlen(s)+1); if (d) strcpy(d,s); return d; }
static ABI int32_t http_init(int mem,int ssl,uint64_t pool) { (void)mem; (void)ssl; (void)pool; return 1; }
static ABI int32_t http_template(int ctx,const char *agent,int version,int proxy) {
    (void)ctx; (void)version; (void)proxy;
    const int id=http_new(1,0);
    if (id>0) snprintf(http[id].user_agent,sizeof http[id].user_agent,"%s",agent ? agent : "");
    return id;
}
static ABI int32_t http_connection(int tmpl,const char *url,int keepalive) {
    (void)keepalive;
    if (!http_get(tmpl)) return HTTP_INVALID_ID;
    const int id=http_new(2,tmpl);
    if (id>0) http[id].url=dup_text(url);
    return id;
}
static int32_t http_request_new(int conn,const char *method,const char *url) {
    if (!http_get(conn)) return HTTP_INVALID_ID;
    const int id=http_new(3,conn);
    if (id>0) { http[id].url=dup_text(url); snprintf(http[id].method,sizeof http[id].method,"%s",method); }
    return id;
}
static ABI int32_t http_request(int conn,int32_t method,const char *url,uint64_t length) {
    (void)length;
    static const char *const methods[]={"GET","POST","HEAD","OPTIONS","PUT","DELETE","TRACE","CONNECT"};
    return http_request_new(conn,method>=0 && method<8 ? methods[method] : "GET",url);
}
static ABI int32_t http_request2(int conn,const char *method,const char *url,uint64_t length) {
    (void)length;
    return http_request_new(conn,method && *method ? method : "GET",url);
}
static ABI int32_t http_delete(int id) {
    pthread_mutex_lock(&net_lock);
    HttpObj *h=http_get(id);
    if (h) http_free(h);
    pthread_mutex_unlock(&net_lock);
    return h ? 0 : HTTP_INVALID_ID;
}
static ABI int32_t http_add_header(int id,const char *name,const char *value,int32_t mode) {
    HttpObj *h=http_get(id);
    if (!h) return HTTP_INVALID_ID;
    if (!name || !value) return HTTP_INVALID_VALUE;
    if (mode==0) for (int i=0;i<h->header_count;++i) if (!strcasecmp(h->headers[i].name,name)) {
        free(h->headers[i].value); h->headers[i].value=dup_text(value); return 0;
    }
    if (h->header_count>=32) return HTTP_OUT_OF_MEMORY;
    h->headers[h->header_count].name=dup_text(name);
    h->headers[h->header_count++].value=dup_text(value);
    return 0;
}
static ABI int32_t http_content_length(int id,uint64_t length) { (void)length; return http_get(id) ? 0 : HTTP_INVALID_ID; }
static ABI int32_t http_connect_timeout(int id,uint32_t usec) {
    HttpObj *h=http_get(id);
    if (!h) return HTTP_INVALID_ID;
    h->connect_timeout_us=usec; return 0;
}
static ABI int32_t http_set_id_flag(int id,int value) { (void)value; return http_get(id) ? 0 : HTTP_INVALID_ID; }
static ABI int32_t http_https_option(int id,uint32_t flags) { (void)flags; return http_get(id) ? 0 : HTTP_INVALID_ID; }
static ABI int32_t http_ssl_callback(int id,void *cb,void *arg) { (void)cb; (void)arg; return http_get(id) ? 0 : HTTP_INVALID_ID; }
static ABI int32_t http_pool_stats(int ctx,void *stats) { (void)ctx; if (stats) memset(stats,0,28); return 0; }

/* scheme://host[:port]/path -> its parts (path keeps the query). */
static int parse_url(const char *url,char *scheme,size_t scheme_size,char *host,size_t host_size,const char **path) {
    const char *p=strstr(url,"://");
    if (!p) return 0;
    snprintf(scheme,scheme_size,"%.*s",(int)(p-url),url);
    p+=3;
    const char *end=p+strcspn(p,"/?#");
    snprintf(host,host_size,"%.*s",(int)(end-p),p);
    *path=*end ? end : "/";
    return 1;
}
typedef struct { char *data; size_t size, capacity; } Buffer;
static int buffer_add(Buffer *b,const void *data,size_t size) {
    if (b->size+size+1>b->capacity) {
        size_t capacity=b->capacity ? b->capacity*2 : 4096;
        while (capacity<b->size+size+1) capacity*=2;
        char *grown=realloc(b->data,capacity);
        if (!grown) return 0;
        b->data=grown; b->capacity=capacity;
    }
    memcpy(b->data+b->size,data,size); b->size+=size; b->data[b->size]=0;
    return 1;
}
static void collect_headers(int id,Buffer *out,const char **skip,int skip_count,int depth) {
    HttpObj *h=http_get(id);
    if (!h || depth>3) return;
    collect_headers(h->parent,out,skip,skip_count,depth+1); /* template, connection, then request */
    for (int i=0;i<h->header_count;++i) {
        int skipped=0;
        for (int k=0;k<skip_count;++k) if (!strcasecmp(h->headers[i].name,skip[k])) skipped=1;
        if (skipped) continue;
        char line[1024];
        const int n=snprintf(line,sizeof line,"%s: %s\r\n",h->headers[i].name,h->headers[i].value);
        buffer_add(out,line,(size_t)(n<(int)sizeof line ? n : (int)sizeof line-1));
    }
}
static const char *user_agent_of(int id) {
    for (int depth=0; depth<3; ++depth) {
        HttpObj *h=http_get(id);
        if (!h) break;
        if (h->user_agent[0]) return h->user_agent;
        id=h->parent;
    }
    return "SacredFire";
}
/* Chunked transfer coding, decoded in place; returns the body's size. */
static size_t dechunk(char *body,size_t size) {
    size_t in=0, out=0;
    while (in<size) {
        char *end;
        const unsigned long chunk=strtoul(body+in,&end,16);
        const char *line=strstr(body+in,"\r\n");
        if (!line || end==body+in) break;
        in=(size_t)(line-body)+2;
        if (!chunk) break;
        if (in+chunk>size) { memmove(body+out,body+in,size-in); out+=size-in; break; }
        memmove(body+out,body+in,chunk); out+=chunk; in+=chunk+2;
    }
    return out;
}
static ABI int32_t http_send(int id,const void *data,uint64_t size) {
    HttpObj *h=http_get(id);
    if (!h || h->kind!=3) return HTTP_INVALID_ID;
    http_free_response(h);
    char scheme[16], host[256];
    const char *path;
    if (!h->url || !parse_url(h->url,scheme,sizeof scheme,host,sizeof host,&path)) return HTTP_INVALID_URL;
    if (strstr(h->url,"lavender-ps4-auth3") && strstr(path,"/auth/")) dw_test_key_ensure();
    Buffer request={0};
    char line[2048];
    int n=snprintf(line,sizeof line,"%s %s HTTP/1.1\r\nHost: %s\r\nX-SacredFire-Scheme: %s\r\nUser-Agent: %s\r\nConnection: close\r\n",
                   h->method,path,host,scheme,user_agent_of(id));
    buffer_add(&request,line,(size_t)(n<(int)sizeof line ? n : (int)sizeof line-1));
    static const char *skip[]={"Host","Connection","Content-Length","User-Agent","Transfer-Encoding"};
    collect_headers(id,&request,skip,5,0);
    if (data || size || !strcmp(h->method,"POST") || !strcmp(h->method,"PUT")) {
        n=snprintf(line,sizeof line,"Content-Length: %llu\r\n",(unsigned long long)size);
        buffer_add(&request,line,(size_t)n);
    }
    buffer_add(&request,"\r\n",2);
    if (data && size) buffer_add(&request,data,(size_t)size);
    printf("Net: HTTP %s %s (%llu bytes) -> %s:%u\n",h->method,h->url,(unsigned long long)size,cfg.server_text,cfg.http_port);
    if (data && size) hexdump("HTTP body",id,data,(size_t)size);
    { /* M4: the Demonware auth request carries X-TransactionID and JSON fields the reply
       * validation depends on; show the head (no behavior change, offline path untouched). */
        char *head_end=request.data ? strstr(request.data,"\r\n\r\n") : NULL;
        if (head_end && head_end>request.data) {
            size_t head_len=(size_t)(head_end-request.data);
            if (head_len>2048) head_len=2048;
            printf("Net: HTTP request %d head (%zu bytes):\n%.*s\n",id,head_len,(int)head_len,request.data);
        }
    }

    int32_t result=0;
    Buffer response={0};
    NativeSocket s=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);
    if (s==NATIVE_INVALID) { free(request.data); return HTTP_NETWORK; }
    struct sockaddr_in to={0};
    to.sin_family=AF_INET; to.sin_port=htons(cfg.http_port); to.sin_addr.s_addr=cfg.server;
    int timeout_ms=h->connect_timeout_us ? (int)(h->connect_timeout_us/1000) : 10000;
    for (int up=h->parent, depth=0; !h->connect_timeout_us && depth<2; ++depth) {
        HttpObj *p=http_get(up);
        if (!p) break;
        if (p->connect_timeout_us) { timeout_ms=(int)(p->connect_timeout_us/1000); break; }
        up=p->parent;
    }
    set_nonblocking(s,1);
    int connected=!connect(s,(struct sockaddr *)&to,sizeof to);
    if (!connected) {
        const int e=native_error();
        if ((e==E_INPROGRESS || e==E_AGAIN) && wait_ready(s,1,timeout_ms>0 ? timeout_ms : 10000)>0) {
            int error=0;
            socklen_t len=sizeof error;
            getsockopt(s,SOL_SOCKET,SO_ERROR,(char *)&error,&len);
            connected=!error;
        }
    }
    set_nonblocking(s,0);
    if (!connected) { result=HTTP_NETWORK; printf("Net: HTTP: the private server's port %u does not answer\n",cfg.http_port); goto done; }
    set_timeout(s,SO_RCVTIMEO,15000000);
    set_timeout(s,SO_SNDTIMEO,15000000);
    for (size_t sent=0; sent<request.size;) {
        const int k=send(s,request.data+sent,(int)(request.size-sent),0);
        if (k<=0) { result=HTTP_NETWORK; goto done; }
        sent+=(size_t)k;
    }
    for (;;) {
        char chunk[8192];
        const int k=recv(s,chunk,sizeof chunk,0);
        if (k<0) { result=response.size ? 0 : HTTP_TIMEOUT; break; }
        if (!k) break;
        if (!buffer_add(&response,chunk,(size_t)k)) { result=HTTP_OUT_OF_MEMORY; break; }
    }
    if (!result) {
        char *end=response.data ? strstr(response.data,"\r\n\r\n") : NULL;
        if (!end || sscanf(response.data,"HTTP/%*s %d",&h->status)!=1) { result=HTTP_NETWORK; goto done; }
        const size_t header_size=(size_t)(end-response.data)+4;
        h->response_headers=malloc(header_size+1);
        h->body=malloc(response.size-header_size+1);
        if (!h->response_headers || !h->body) { result=HTTP_OUT_OF_MEMORY; goto done; }
        memcpy(h->response_headers,response.data,header_size); h->response_headers[header_size]=0;
        h->response_headers_size=header_size;
        h->body_size=response.size-header_size;
        memcpy(h->body,response.data+header_size,h->body_size); h->body[h->body_size]=0;
        const char *te=NULL;
        for (const char *p=h->response_headers; (p=strchr(p,'\n'))!=NULL; ++p)
            if (!strncasecmp(p+1,"Transfer-Encoding:",18)) { te=p+19; break; }
        if (te && strstr(te,"chunked") && strstr(te,"chunked")<strstr(te,"\n")) h->body_size=dechunk(h->body,h->body_size);
        h->sent=1;
        printf("Net: HTTP %s %s -> %d (%zu bytes)\n",h->method,h->url,h->status,h->body_size);
        if (h->response_headers && h->response_headers_size) {
            /* M4: X-Signature travels as a response header; without it no ticket can
             * validate. Show headers (capped) so a signed vs unsigned reply is visible. */
            size_t shown=h->response_headers_size<2048 ? h->response_headers_size : 2048;
            printf("Net: HTTP reply %d headers (%zu bytes):\n%.*s\n",id,h->response_headers_size,(int)shown,h->response_headers);
        }
        if (h->body_size) hexdump("HTTP reply",id,h->body,h->body_size);
    }
done:
    native_close(s);
    free(request.data); free(response.data);
    if (result) http_free_response(h);
    return result;
}
static ABI int32_t http_status(int id,int *status) {
    HttpObj *h=http_get(id);
    if (!h) return HTTP_INVALID_ID;
    if (!status) return HTTP_INVALID_VALUE;
    if (!h->sent) return HTTP_BEFORE_SEND;
    *status=h->status; return 0;
}
static ABI int32_t http_response_length(int id,int *result,uint64_t *length) {
    HttpObj *h=http_get(id);
    if (!h) return HTTP_INVALID_ID;
    if (!result || !length) return HTTP_INVALID_VALUE;
    if (!h->sent) return HTTP_BEFORE_SEND;
    *result=0; *length=h->body_size; /* the whole body is here: its length is known */
    return 0;
}
static ABI int32_t http_read(int id,void *data,uint64_t size) {
    HttpObj *h=http_get(id);
    if (!h) return HTTP_INVALID_ID;
    if (!h->sent) return HTTP_BEFORE_SEND;
    if (!data) return HTTP_INVALID_VALUE;
    const size_t left=h->body_size-h->body_read, n=size<left ? (size_t)size : left;
    memcpy(data,h->body+h->body_read,n);
    h->body_read+=n;
    return (int32_t)n;
}
static ABI int32_t http_all_headers(int id,char **header,uint64_t *size) {
    HttpObj *h=http_get(id);
    if (!h) return HTTP_INVALID_ID;
    if (!header || !size) return HTTP_INVALID_VALUE;
    if (!h->sent) return HTTP_BEFORE_SEND;
    *header=h->response_headers; *size=h->response_headers_size;
    return 0;
}
static ABI int32_t http_parse_header(const char *header,uint64_t length,const char *field,const char **value,uint64_t *value_length) {
    if (!header || !field || !value || !value_length) return HTTP_INVALID_VALUE;
    const size_t field_length=strlen(field);
    for (const char *line=header; line<header+length;) {
        const char *next=memchr(line,'\n',(size_t)(header+length-line));
        const char *end=next ? next : header+length;
        if ((size_t)(end-line)>field_length && !strncasecmp(line,field,field_length) && line[field_length]==':') {
            const char *v=line+field_length+1;
            while (v<end && (*v==' ' || *v=='\t')) ++v;
            const char *e=end;
            while (e>v && (e[-1]=='\r' || e[-1]==' ')) --e;
            *value=v; *value_length=(uint64_t)(e-v);
            return 0;
        }
        if (!next) break;
        line=next+1;
    }
    return HTTP_PARSE_NOT_FOUND;
}
static ABI int32_t http_uri_escape(char *out,uint64_t *require,uint64_t prepare,const char *in) {
    if (!in) return HTTP_INVALID_VALUE;
    size_t need=1;
    for (const unsigned char *p=(const unsigned char *)in; *p; ++p)
        need+=isalnum(*p) || strchr("-._~",*p) ? 1 : 3;
    if (require) *require=need;
    if (!out) return 0;
    if (prepare<need) return HTTP_OUT_OF_MEMORY;
    char *o=out;
    for (const unsigned char *p=(const unsigned char *)in; *p; ++p) {
        if (isalnum(*p) || strchr("-._~",*p)) *o++=(char)*p;
        else { snprintf(o,4,"%%%02X",*p); o+=3; }
    }
    *o=0; return 0;
}
/* Non-blocking use: requests finish inside sceHttpSendRequest, so an epoll reports each request
 * once as readable after it was sent. */
static ABI int32_t http_create_epoll(int ctx,void **handle) {
    (void)ctx;
    if (!handle) return HTTP_INVALID_VALUE;
    static int next=1;
    *handle=(void *)(uintptr_t)(0x5f000000+next++); return 0;
}
static ABI int32_t http_set_epoll(int id,void *handle,void *arg) {
    HttpObj *h=http_get(id);
    if (!h) return HTTP_INVALID_ID;
    h->epoll=handle; h->user_arg=arg; return 0;
}
static ABI int32_t http_unset_epoll(int id) { HttpObj *h=http_get(id); if (!h) return HTTP_INVALID_ID; h->epoll=NULL; return 0; }
typedef struct { uint32_t events, detail; int32_t id; void *arg; } HttpEvent;
static ABI int32_t http_wait(void *handle,HttpEvent *events,int32_t max,int64_t timeout) {
    if (!events || max<=0) return HTTP_INVALID_VALUE;
    int n=0;
    pthread_mutex_lock(&net_lock);
    for (int id=1; id<MAX_HTTP && n<max; ++id) {
        HttpObj *h=&http[id];
        if (h->kind==3 && h->epoll==handle && h->sent && !h->reported) {
            h->reported=1;
            events[n++]=(HttpEvent){1,0,id,h->user_arg};
        }
    }
    pthread_mutex_unlock(&net_lock);
    if (!n && timeout>0) sleep_us(timeout>100000 ? 100000 : timeout);
    return n;
}
static ABI int32_t http_abort(int id) { return http_get(id) ? 0 : HTTP_INVALID_ID; }

/* ---- libSceNpWebApi: PSN's web services (friends, profiles, sessions), which NpToolkit2 uses
 * once the user is signed in. A request to API group G and path P is the HTTPS request
 * https://G.np.community.playstation.net/P, sent like any other to the private server (Sony is
 * never contacted); replies of 400 and above become 0x82f00000 | status, as on the console. ---- */
#define WEBAPI_INVALID_ARGUMENT ((int32_t)0x80552902)
#define WEBAPI_NOT_SIGNED_IN ((int32_t)0x80552907)
#define WEBAPI_REQUEST_NOT_FOUND ((int32_t)0x80552906)
static int webapi_next_id=1;
static int webapi_template;
static int webapi_id(void) { pthread_mutex_lock(&net_lock); const int id=webapi_next_id++; pthread_mutex_unlock(&net_lock); return id; }
static ABI int32_t webapi_init(int http_ctx,uint64_t pool) { (void)http_ctx; (void)pool; return webapi_id(); }
static ABI int32_t webapi_create_context_a(int lib,int32_t user) {
    (void)lib;
    if (!user_signed_in(user)) return WEBAPI_NOT_SIGNED_IN;
    return 0x1000+webapi_id();
}
typedef struct { uint64_t length; const char *type; uint8_t reserved[16]; } WebApiContent;
static ABI int32_t webapi_create_request(int ctx,const char *group,const char *path,int32_t method,const WebApiContent *content,int64_t *id) {
    (void)ctx;
    static const char *const methods[]={"GET","POST","PUT","DELETE","PATCH"};
    if (!group || !path || !id || method<0 || method>4) return WEBAPI_INVALID_ARGUMENT;
    if (!http_get(webapi_template)) webapi_template=http_template(1,"libsceNpWebApi",1,0);
    char url[1024];
    snprintf(url,sizeof url,"https://%s.np.community.playstation.net%s%s",group,path[0]=='/' ? "" : "/",path);
    const int conn=http_connection(webapi_template,url,1);
    if (conn<0) return conn;
    const int req=http_request_new(conn,methods[method],url);
    if (req<0) { http_delete(conn); return req; }
    if (content && content->type) http_add_header(req,"Content-Type",content->type,0);
    *id=req;
    return 0;
}
static HttpObj *webapi_request(int64_t id) { HttpObj *h=id>0 && id<MAX_HTTP ? http_get((int)id) : NULL; return h && h->kind==3 ? h : NULL; }
static ABI int32_t webapi_add_header(int64_t id,const char *name,const char *value) {
    if (!name || !value) return WEBAPI_INVALID_ARGUMENT;
    return webapi_request(id) ? http_add_header((int)id,name,value,0) : WEBAPI_REQUEST_NOT_FOUND;
}
typedef struct { int32_t status; char *error; uint64_t error_size; uint64_t data_size; } WebApiResponseInfo;
static ABI int32_t webapi_send2(int64_t id,const void *data,uint64_t size,WebApiResponseInfo *info) {
    HttpObj *h=webapi_request(id);
    if (!h) return WEBAPI_REQUEST_NOT_FOUND;
    const int32_t sent=http_send((int)id,data,size);
    if (sent) return sent;
    if (info) info->status=h->status;
    if (h->status<400) return 0;
    if (info) {
        info->data_size=h->body_size;
        if (info->error && info->error_size) {
            const size_t n=h->body_size<info->error_size-1 ? h->body_size : (size_t)info->error_size-1;
            memcpy(info->error,h->body,n); info->error[n]=0;
        }
    }
    h->body_read=h->body_size;
    return (int32_t)(0x82f00000u | (uint32_t)h->status);
}
static ABI int32_t webapi_send(int64_t id,const void *data,uint64_t size) { return webapi_send2(id,data,size,NULL); }
static ABI int32_t webapi_read(int64_t id,void *data,uint64_t size) {
    if (!data || !size) return WEBAPI_INVALID_ARGUMENT;
    return webapi_request(id) ? http_read((int)id,data,size) : WEBAPI_REQUEST_NOT_FOUND;
}
static ABI int32_t webapi_status(int64_t id,int32_t *status) {
    if (!status) return WEBAPI_INVALID_ARGUMENT;
    return webapi_request(id) ? http_status((int)id,status) : WEBAPI_REQUEST_NOT_FOUND;
}
static int32_t webapi_header(int64_t id,const char *name,char *value,uint64_t size,uint64_t *length) {
    HttpObj *h=webapi_request(id);
    if (!h) return WEBAPI_REQUEST_NOT_FOUND;
    if (!name) return WEBAPI_INVALID_ARGUMENT;
    if (!h->sent) return HTTP_BEFORE_SEND;
    const char *found;
    uint64_t found_size;
    const int32_t r=http_parse_header(h->response_headers,h->response_headers_size,name,&found,&found_size);
    if (r) return r;
    if (length) *length=found_size;
    if (value) {
        if (size<=found_size) return (int32_t)0x80552901; /* buffer too small */
        memcpy(value,found,found_size); value[found_size]=0;
    }
    return 0;
}
static ABI int32_t webapi_header_length(int64_t id,const char *name,uint64_t *length) {
    if (!length) return WEBAPI_INVALID_ARGUMENT;
    return webapi_header(id,name,NULL,0,length);
}
static ABI int32_t webapi_header_value(int64_t id,const char *name,char *value,uint64_t size) {
    if (!value || !size) return WEBAPI_INVALID_ARGUMENT;
    return webapi_header(id,name,value,size,NULL);
}
static ABI int32_t webapi_delete_request(int64_t id) {
    HttpObj *h=webapi_request(id);
    if (!h) return WEBAPI_REQUEST_NOT_FOUND;
    const int conn=h->parent;
    http_delete((int)id); http_delete(conn);
    return 0;
}
static ABI int32_t webapi_abort_request(int64_t id) { return webapi_request(id) ? 0 : WEBAPI_REQUEST_NOT_FOUND; }
static ABI int32_t webapi_new_id(void) { return webapi_id(); }
static ABI int32_t webapi_filter(int lib,int handle,const char *service,uint32_t label,const void *param,uint64_t count) {
    (void)lib; (void)handle; (void)label;
    if (!param || !count) return WEBAPI_INVALID_ARGUMENT;
    if (service) printf("Net: PSN: push event filter for service '%s' (no push events from the private server yet)\n",service);
    return webapi_id();
}
static ABI int32_t webapi_register_push(int ctx,int filter,void *cb,void *arg) {
    (void)ctx; (void)filter; (void)arg;
    return cb ? webapi_id() : WEBAPI_INVALID_ARGUMENT;
}
/* "<online id>@<platform>..." in base64 -> NpId (online id, opt left zero). */
static ABI int32_t webapi_parse_npid(const char *json,NpId *id) {
    if (!json || !id) return NP_INVALID_ARGUMENT;
    static const char alphabet[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    char decoded[64]={0};
    size_t n=0;
    uint32_t bits=0;
    int count=0;
    for (const char *p=json; *p && *p!='"' && n<sizeof decoded-1; ++p) {
        const char *at=strchr(alphabet,*p);
        if (!at || !*p) continue;
        bits=bits<<6 | (uint32_t)(at-alphabet);
        if ((count+=6)>=8) { count-=8; decoded[n++]=(char)(bits>>count & 0xff); }
    }
    memset(id,0,sizeof *id);
    const size_t handle=strcspn(decoded,"@");
    memcpy(id->handle.data,decoded,handle<16 ? handle : 16);
    return 0;
}

/* ---- libScePosix sockets (NpToolkit2 and the game may use them): the same sockets, POSIX
 * returns (-1 and the guest's errno). Socket ids and file descriptors share one space here. ---- */
static int64_t posix_result(int64_t r) {
    if (r>=0) return r;
    *runtime_errno()=net_errno;
    return -1;
}
static ABI int32_t posix_socket(int family,int type,int protocol) { return (int32_t)posix_result(net_socket("posix",family,type,protocol)); }
static ABI int32_t posix_connect(int s,const void *addr,uint32_t len) { return (int32_t)posix_result(net_connect(s,addr,len)); }
static ABI int32_t posix_bind(int s,const void *addr,uint32_t len) { return (int32_t)posix_result(net_bind(s,addr,len)); }
static ABI int32_t posix_listen(int s,int backlog) { return (int32_t)posix_result(net_listen(s,backlog)); }
static ABI int32_t posix_accept(int s,void *addr,uint32_t *len) { return (int32_t)posix_result(net_accept(s,addr,len)); }
static ABI int64_t posix_send(int s,const void *data,uint64_t size,int flags) { return posix_result(net_send(s,data,size,flags)); }
static ABI int64_t posix_recv(int s,void *data,uint64_t size,int flags) { return posix_result(net_recv(s,data,size,flags)); }
static ABI int32_t posix_setsockopt(int s,int level,int option,const void *value,uint32_t len) { return (int32_t)posix_result(net_setsockopt(s,level,option,value,len)); }
static ABI int32_t posix_inet_pton(int af,const char *src,void *dst) {
    if (af!=PS_AF_INET) { *runtime_errno()=E_AFNOSUPPORT; return -1; }
    return inet_pton(AF_INET,src,dst);
}
static ABI const char *posix_inet_ntop(int af,const void *src,char *dst,uint32_t size) {
    if (af!=PS_AF_INET) { *runtime_errno()=E_AFNOSUPPORT; return NULL; }
    return inet_ntop(AF_INET,src,dst,size);
}
/* select: FreeBSD fd_set (1024 bits) over socket ids, timeval of two 64-bit fields. */
typedef struct { uint64_t bits[16]; } GuestFdSet;
typedef struct { int64_t sec, usec; } GuestTimeval;
static ABI int32_t posix_select(int count,GuestFdSet *read,GuestFdSet *write,GuestFdSet *except,const GuestTimeval *timeout) {
    if (count<0 || count>1024) { *runtime_errno()=E_INVAL; return -1; }
    NativePollFd fds[64];
    int ids[64], n=0;
    for (int id=0; id<count && n<64; ++id) {
        const uint64_t bit=1ull<<(id&63);
        const int r=read && (read->bits[id>>6] & bit), w=write && (write->bits[id>>6] & bit), e=except && (except->bits[id>>6] & bit);
        if (!r && !w && !e) continue;
        NetObj *o=object(id,OBJ_SOCKET);
        if (!o) { *runtime_errno()=E_BADF; return -1; }
        fds[n].fd=o->s; fds[n].revents=0;
        fds[n].events=(short)((r ? POLLIN : 0) | (w ? POLLOUT : 0));
        ids[n++]=id;
    }
    const int ms=timeout ? (int)(timeout->sec*1000+(timeout->usec+999)/1000) : -1;
    int ready=0;
    if (n) {
        ready=native_poll(fds,(unsigned long)n,ms);
        if (ready<0) { *runtime_errno()=native_error(); return -1; }
    } else if (ms>0) sleep_us((int64_t)ms*1000);
    if (read) memset(read,0,sizeof *read);
    if (write) memset(write,0,sizeof *write);
    if (except) memset(except,0,sizeof *except);
    int total=0;
    for (int i=0;i<n;++i) {
        const uint64_t bit=1ull<<(ids[i]&63);
        const short r=fds[i].revents;
        if (read && (r & (POLLIN|POLLHUP))) { read->bits[ids[i]>>6]|=bit; ++total; }
        if (write && (r & POLLOUT)) { write->bits[ids[i]>>6]|=bit; ++total; }
        if (except && (r & (POLLERR|POLLNVAL))) { except->bits[ids[i]>>6]|=bit; ++total; }
    }
    (void)ready;
    return total;
}

/* ---- PSN services the private server does not offer yet: their calls fail like an
 * unavailable service (cleanup calls succeed), logged once per service, instead of stopping
 * the game. Score, TUS (title user storage), TSS, word filter, Matching2 (PSN rooms; CTR
 * matches through Demonware), bandwidth test, in-game messages, Facebook. ---- */
typedef struct { const char *prefix, *label; int32_t error; int logged; } Unavailable;
static Unavailable unavailable[]={
    {"sceNpScore","NpScore (rankings)",(int32_t)0x80550809,0},
    {"sceNpTus","NpTus (title user storage)",(int32_t)0x80550809,0},
    {"sceNpTss","NpTss (title small storage)",(int32_t)0x80550809,0},
    {"sceNpWordFilter","NpWordFilter",(int32_t)0x80550809,0},
    {"sceNpMatching2","NpMatching2 (PSN rooms)",(int32_t)0x80550D02,0},
    {"sceNpBandwidthTest","NpBandwidthTest",(int32_t)0x80551F07,0},
    {"sceNpInGameMessage","NpInGameMessage",(int32_t)0x80552B03,0},
    {"sceNpSnsFacebook","NpSnsFacebook",(int32_t)0x80550809,0},
};
#define UNAVAILABLE(i) \
    static ABI int32_t unavailable_##i(void) { \
        if (!unavailable[i].logged) { unavailable[i].logged=1; printf("Net: PSN: %s is not offered by the private server yet: calls fail as unavailable\n",unavailable[i].label); } \
        return unavailable[i].error; \
    }
UNAVAILABLE(0) UNAVAILABLE(1) UNAVAILABLE(2) UNAVAILABLE(3) UNAVAILABLE(4) UNAVAILABLE(5) UNAVAILABLE(6) UNAVAILABLE(7)
typedef int32_t (ABI *UnavailableCall)(void);
static const UnavailableCall unavailable_calls[]={unavailable_0,unavailable_1,unavailable_2,unavailable_3,
                                                         unavailable_4,unavailable_5,unavailable_6,unavailable_7};
static uintptr_t unavailable_service(const char *symbol) {
    if (!symbol) return 0;
    for (size_t i=0;i<sizeof unavailable/sizeof *unavailable;++i) {
        if (strncmp(symbol,unavailable[i].prefix,strlen(unavailable[i].prefix))) continue;
        if (strstr(symbol,"Delete") || strstr(symbol,"Abort") || strstr(symbol,"Terminate") || strstr(symbol,"Shutdown") ||
            strstr(symbol,"Destroy") || strstr(symbol,"Unregister")) return (uintptr_t)ok_void;
        return (uintptr_t)unavailable_calls[i];
    }
    return 0;
}

static const RuntimeExport exports[]={
    {"sceNetInit",net_init}, {"sceNetTerm",net_term}, {"sceNetErrnoLoc",net_errno_loc},
    {"sceNetPoolCreate",net_pool_create}, {"sceNetPoolDestroy",net_pool_destroy},
    {"sceNetGetMemoryPoolStats",net_pool_stats},
    {"sceNetSocket",net_socket}, {"sceNetSocketClose",net_socket_close}, {"sceNetSocketAbort",net_socket_abort},
    {"sceNetConnect",net_connect}, {"sceNetBind",net_bind}, {"sceNetListen",net_listen}, {"sceNetAccept",net_accept},
    {"sceNetSend",net_send}, {"sceNetRecv",net_recv}, {"sceNetSendto",net_sendto}, {"sceNetRecvfrom",net_recvfrom},
    {"sceNetShutdown",net_shutdown}, {"sceNetGetsockname",net_getsockname}, {"sceNetGetpeername",net_getpeername},
    {"sceNetSetsockopt",net_setsockopt}, {"sceNetGetsockopt",net_getsockopt},
    {"sceNetEpollCreate",net_epoll_create}, {"sceNetEpollDestroy",net_epoll_destroy},
    {"sceNetEpollControl",net_epoll_control}, {"sceNetEpollWait",net_epoll_wait}, {"sceNetEpollAbort",net_epoll_abort},
    {"sceNetResolverCreate",net_resolver_create}, {"sceNetResolverDestroy",net_resolver_destroy},
    {"sceNetResolverStartNtoa",net_resolver_ntoa}, {"sceNetResolverAbort",net_resolver_abort},
    {"sceNetCtlInit",ok_void}, {"sceNetCtlTerm",ok_void},
    {"sceNetCtlGetState",netctl_state}, {"sceNetCtlGetInfo",netctl_info}, {"sceNetCtlGetNatInfo",netctl_nat},
    {"sceNetCtlRegisterCallback",netctl_register}, {"sceNetCtlCheckCallback",netctl_check},
    {"sceNetCtlUnregisterCallback",netctl_unregister},
    {"sceNetCtlRegisterCallbackForNpToolkit",netctl_register_toolkit},
    {"sceNetCtlCheckCallbackForNpToolkit",netctl_check_toolkit},
    {"sceNetCtlUnregisterCallbackForNpToolkit",netctl_unregister_toolkit},
    {"sceSslInit",lib_init_one}, {"sceSslTerm",ok_void}, {"sceSslGetMemoryPoolStats",http_pool_stats},
    {"sceHttpInit",http_init}, {"sceHttpTerm",ok_void}, {"sceHttpGetMemoryPoolStats",http_pool_stats},
    {"sceHttpCreateTemplate",http_template}, {"sceHttpDeleteTemplate",http_delete},
    {"sceHttpCreateConnectionWithURL",http_connection}, {"sceHttpDeleteConnection",http_delete},
    {"sceHttpCreateRequestWithURL",http_request}, {"sceHttpCreateRequestWithURL2",http_request2},
    {"sceHttpDeleteRequest",http_delete}, {"sceHttpAddRequestHeader",http_add_header},
    {"sceHttpSetRequestContentLength",http_content_length}, {"sceHttpSetConnectTimeOut",http_connect_timeout},
    {"sceHttpSetNonblock",http_set_id_flag}, {"sceHttpSetChunkedTransferEnabled",http_set_id_flag},
    {"sceHttpsEnableOption",http_https_option}, {"sceHttpsDisableOption",http_https_option},
    {"sceHttpsSetSslCallback",http_ssl_callback},
    {"sceHttpSendRequest",http_send}, {"sceHttpAbortRequest",http_abort},
    {"sceHttpGetStatusCode",http_status}, {"sceHttpGetResponseContentLength",http_response_length},
    {"sceHttpReadData",http_read}, {"sceHttpGetAllResponseHeaders",http_all_headers},
    {"sceHttpParseResponseHeader",http_parse_header}, {"sceHttpUriEscape",http_uri_escape},
    {"sceHttpCreateEpoll",http_create_epoll}, {"sceHttpDestroyEpoll",ok_void},
    {"sceHttpSetEpoll",http_set_epoll}, {"sceHttpUnsetEpoll",http_unset_epoll},
    {"sceHttpWaitRequest",http_wait}, {"sceHttpAbortWaitRequest",ok_void},
    {"sceNpGetState",np_state}, {"sceNpGetOnlineId",np_online_id}, {"sceNpGetNpId",np_npid},
    {"sceNpGetAccountIdA",np_account_id}, {"sceNpGetUserIdByAccountId",np_user_by_account},
    {"sceNpCreateRequest",np_create_request}, {"sceNpCreateAsyncRequest",np_create_async},
    {"sceNpDeleteRequest",np_delete_request}, {"sceNpAbortRequest",np_abort_request}, {"sceNpPollAsync",np_poll},
    {"sceNpCheckNpAvailabilityA",np_check_availability_a}, {"sceNpCheckPlus",np_check_plus},
    {"sceNpGetParentalControlInfoA",np_parental_a},
    {"sceNpRegisterStateCallback",np_register_legacy}, {"sceNpUnregisterStateCallback",np_unregister_legacy},
    {"sceNpRegisterStateCallbackForToolkit",np_register_toolkit},
    {"sceNpUnregisterStateCallbackForToolkit",np_unregister_toolkit},
    {"sceNpCheckCallback",np_check_callback}, {"sceNpCheckCallbackForLib",np_check_callback},
    {"sceNpAuthCreateRequest",np_create_request}, {"sceNpAuthCreateAsyncRequest",np_create_async},
    {"sceNpAuthDeleteRequest",np_delete_request}, {"sceNpAuthAbortRequest",np_abort_request},
    {"sceNpAuthPollAsync",np_poll},
    {"sceNpAuthGetAuthorizationCodeA",np_auth_code_a}, {"sceNpAuthGetIdTokenA",np_id_token_a},
    {"sceNpWebApiInitialize",webapi_init}, {"sceNpWebApiTerminate",ok_void},
    {"sceNpWebApiGetMemoryPoolStats",http_pool_stats},
    {"sceNpWebApiCreateContextA",webapi_create_context_a}, {"sceNpWebApiDeleteContext",ok_void},
    {"sceNpWebApiCreateHandle",webapi_new_id}, {"sceNpWebApiDeleteHandle",ok_void},
    {"sceNpWebApiCreateRequest",webapi_create_request}, {"sceNpWebApiDeleteRequest",webapi_delete_request},
    {"sceNpWebApiAbortRequest",webapi_abort_request}, {"sceNpWebApiAddHttpRequestHeader",webapi_add_header},
    {"sceNpWebApiSendRequest",webapi_send}, {"sceNpWebApiSendRequest2",webapi_send2},
    {"sceNpWebApiReadData",webapi_read}, {"sceNpWebApiGetHttpStatusCode",webapi_status},
    {"sceNpWebApiGetHttpResponseHeaderValueLength",webapi_header_length},
    {"sceNpWebApiGetHttpResponseHeaderValue",webapi_header_value},
    {"sceNpWebApiCreateExtdPushEventFilter",webapi_filter}, {"sceNpWebApiDeleteExtdPushEventFilter",ok_void},
    {"sceNpWebApiRegisterExtdPushEventCallbackA",webapi_register_push},
    {"sceNpWebApiUnregisterExtdPushEventCallback",ok_void},
    {"sceNpWebApiUtilityParseNpId",webapi_parse_npid},
    {"socket",posix_socket}, {"connect",posix_connect}, {"bind",posix_bind}, {"listen",posix_listen},
    {"accept",posix_accept}, {"send",posix_send}, {"recv",posix_recv}, {"setsockopt",posix_setsockopt},
    {"select",posix_select}, {"inet_pton",posix_inet_pton}, {"inet_ntop",posix_inet_ntop},
};
/* Online: these contracts replace runtime_services.c's offline ones. Offline: nothing here. */
uintptr_t runtime_net_resolve(const char *name) {
    if (!online()) return 0;
    const uintptr_t found=RUNTIME_LOOKUP(exports,name);
    if (found) return found;
    const char *library=strchr(name,'#');
    return library && !strncmp(library+1,"libSceNp",8) ? unavailable_service(runtime_symbol(name)) : 0;
}
