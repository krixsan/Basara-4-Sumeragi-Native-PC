/* Offline AppContent provider for the configured base-game profile.
 * Add-ons (DLC) without extra data are reported installed when the content profile lists them
 * (the player's own DLC packages, scripts/content_profile.py); no mounting or downloads. */
#include "runtime.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#define INVALID_ID ((int32_t)0x805a1000)
#define NOT_LOADED ((int32_t)0x805a1001)
#define PARAMETER ((int32_t)0x80d90002)
#define BUSY ((int32_t)0x80d90003)
#define SCE_APP_CONTENT_ERROR_NOT_FOUND ((int32_t)0x80d90005)
static unsigned refs, initialized, configured;
static uint32_t parameters[5];
static unsigned queries, lists;
/* SceAppContentAddcontInfo: SceNpUnifiedEntitlementLabel (17 chars + 3 padding) and a status. */
typedef struct { char label[17]; char padding[3]; uint32_t status; } AddcontInfo;
_Static_assert(sizeof(AddcontInfo)==24,"SceAppContentAddcontInfo layout");
#define ADDCONT_INSTALLED 4u
static char addons[128][17];
static unsigned addon_count;
static char dlc_directory[512] = "DLC/SB4S PS4";

typedef struct {
    char label[17];
    char folder[512];
} DlcCacheEntry;
static DlcCacheEntry dlc_cache[128];
static int dlc_cache_count = -1;

int runtime_content_configure_dlc_dir(const char *path) {
    if (!path || !*path || strlen(path) >= sizeof(dlc_directory)) return -1;
    char temp[512];
    snprintf(temp, sizeof(temp), "%s", path);
    size_t len = strlen(temp);
    int guard = 512;
    while (len > 0 && (temp[len - 1] == '/' || temp[len - 1] == '\\') && --guard > 0) {
        temp[--len] = '\0';
    }
    if (len >= 8 && (!strcmp(temp + len - 8, "/sce_sys") || !strcmp(temp + len - 8, "\\sce_sys"))) {
        temp[len - 8] = '\0';
        len = strlen(temp);
    }
    /* If path points to a specific DLC subfolder (has sce_sys/param.sfo directly),
     * strip the subfolder name so dlc_directory points to the DLC root folder containing all add-ons. */
    char sfo_test[1024];
    snprintf(sfo_test, sizeof(sfo_test), "%s/sce_sys/param.sfo", temp);
    FILE *f = fopen(sfo_test, "rb");
    if (f) {
        fclose(f);
        char *last_slash = strrchr(temp, '/');
        char *last_bslash = strrchr(temp, '\\');
        char *sep = last_slash > last_bslash ? last_slash : last_bslash;
        if (sep) {
            *sep = '\0';
        }
    }
    DIR *d = opendir(temp);
    if (!d) {
        fprintf(stderr, "DLC: directory '%s' cannot be opened\n", temp);
        return -1;
    }
    closedir(d);
    snprintf(dlc_directory, sizeof(dlc_directory), "%s", temp);
    dlc_cache_count = -1;
    printf("DLC: configured folder %s\n", dlc_directory);
    return 0;
}

int runtime_content_addon_index(uint32_t service_label, const char *label) {
    if (service_label || !label) return -1;
    for (unsigned i = 0; i < addon_count; ++i) {
        if (!strncmp(addons[i], label, 16)) return (int)i;
    }
    return -1;
}

static int read_sfo_label(const char *folder, char *out_label, size_t out_label_sz) {
    char sfo_path[1024];
    snprintf(sfo_path, sizeof(sfo_path), "%s/sce_sys/param.sfo", folder);
    FILE *file = fopen(sfo_path, "rb");
    if (!file) return 0;
    unsigned char data[65536];
    size_t size = fread(data, 1, sizeof(data), file);
    fclose(file);
    if (size < 20 || memcmp(data, "\0PSF", 4)) return 0;
    uint32_t keys, values, count;
    memcpy(&keys, data + 8, 4);
    memcpy(&values, data + 12, 4);
    memcpy(&count, data + 16, 4);
    if (count > (size - 20) / 16 || keys < 20 + count * 16 || keys > values || values > size) return 0;
    for (uint32_t i = 0; i < count; ++i) {
        const unsigned char *entry = data + 20 + i * 16;
        uint16_t key_offset;
        uint32_t length, value_offset;
        memcpy(&key_offset, entry, 2);
        memcpy(&length, entry + 4, 4);
        memcpy(&value_offset, entry + 12, 4);
        if (key_offset > values - keys || value_offset > size - values) continue;
        size_t key_start = (size_t)keys + key_offset;
        size_t value_start = (size_t)values + value_offset;
        if (key_start >= values || length > size - value_start) continue;
        const unsigned char *key_end = memchr(data + key_start, 0, (size_t)values - key_start);
        if (!key_end || (size_t)(key_end - (data + key_start)) != 10 ||
            memcmp(data + key_start, "CONTENT_ID", 10)) continue;
        char content_id[256];
        size_t content_length = length;
        const unsigned char *terminator = memchr(data + value_start, 0, content_length);
        if (terminator) content_length = (size_t)(terminator - (data + value_start));
        if (content_length != 36) return 0;
        memcpy(content_id, data + value_start, content_length);
        content_id[content_length] = 0;
        snprintf(out_label, out_label_sz, "%.16s", content_id + 20);
        return 1;
    }
    return 0;
}

static void dlc_cache_init(void) {
    if (dlc_cache_count >= 0) return;
    dlc_cache_count = 0;
    if (!dlc_directory[0]) return;
    DIR *dir = opendir(dlc_directory);
    if (!dir) return;
    for (struct dirent *entry; (entry = readdir(dir)) != NULL;) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        char candidate[512];
        int n = snprintf(candidate, sizeof(candidate), "%s/%s", dlc_directory, entry->d_name);
        if (n < 0 || (size_t)n >= sizeof(candidate)) continue;
        char sfo_test[512];
        snprintf(sfo_test, sizeof(sfo_test), "%s/sce_sys/param.sfo", candidate);
        FILE *f = fopen(sfo_test, "rb");
        if (!f) continue;
        fclose(f);
        char label[17] = "";
        if (read_sfo_label(candidate, label, sizeof(label))) {
            if (dlc_cache_count < 128) {
                snprintf(dlc_cache[dlc_cache_count].label, sizeof(dlc_cache[dlc_cache_count].label), "%s", label);
                snprintf(dlc_cache[dlc_cache_count].folder, sizeof(dlc_cache[dlc_cache_count].folder), "%s", candidate);
                ++dlc_cache_count;
            }
        }
    }
    closedir(dir);
    if (dlc_cache_count > 0) {
        printf("DLC: cached %d add-on folders from %s\n", dlc_cache_count, dlc_directory);
    }
}

static int find_dlc_folder(const char *label, char *host, size_t host_size) {
    if (!label || !*label) return -1;
    dlc_cache_init();
    for (int i = 0; i < dlc_cache_count; ++i) {
        if (!strncmp(dlc_cache[i].label, label, 16) || strstr(dlc_cache[i].folder, label)) {
            snprintf(host, host_size, "%s", dlc_cache[i].folder);
            return 0;
        }
    }
    return -1;
}

void runtime_content_add_addon(const char *label) {
    if (addon_count>=128) return;
    memcpy(addons[addon_count],label,16);
    addons[addon_count][16]=0;
    printf("Runtime: add-on %s (installed)\n",addons[addon_count]);
    ++addon_count;
}
void runtime_content_configure(const uint32_t values[5]) {
    if (refs || initialized || (values[0]!=1 && values[0]!=3)) {
        fputs("ERROR: invalid or late content profile\n",stderr); exit(1);
    }
    memcpy(parameters,values,sizeof(parameters)); configured=1;
}
static void require_provider(void) {
    if (!configured) { fputs("STOP: AppContent needs --content-profile\n",stderr); exit(21); }
}
/* System modules: every library this eboot imports is provided by the host
 * runtime, so loading one only tracks a reference count. AppContent (0xb4)
 * additionally requires the configured content profile. */
static unsigned module_refs[0x10000];
static ABI int32_t module_load(uint16_t id) {
    if (!id) return INVALID_ID;
    if (id==0xb4) require_provider();
    if (module_refs[id]==UINT32_MAX) { fputs("STOP: module reference overflow\n",stderr); exit(21); }
    ++module_refs[id];
    if (id==0xb4) { refs=module_refs[id]; printf("Runtime: AppContent host provider loaded; references=%u\n",refs); }
    else printf("Runtime: system module 0x%x loaded (host implementation)\n",id);
    return 0;
}
/* Engine: sceSysmoduleLoadModuleInternalWithArg: internal module ids are 0x8000xxxx; the
 * module's start arguments are ignored and the module's start result is 0. */
static ABI int32_t module_load_internal(uint32_t id,uint64_t argc,const void *argv,uint32_t flags,const void *option,int32_t *result) {
    (void)argc; (void)argv; (void)flags; (void)option;
    if ((id&0xffff0000)!=0x80000000) return INVALID_ID;
    int32_t r=module_load((uint16_t)id);
    if (!r && result) *result=0;
    return r;
}
static ABI int32_t module_loaded(uint16_t id) {
    if (!id) return INVALID_ID;
    return module_refs[id] ? 0 : NOT_LOADED;
}
static ABI int32_t module_unload(uint16_t id) {
    int32_t result=module_loaded(id);
    if (result) return result;
    --module_refs[id];
    if (id==0xb4) { refs=module_refs[id]; if (!refs) initialized=0; }
    return 0;
}
static void require_loaded(void) {
    require_provider();
    if (!refs) { fputs("STOP: AppContent called before module load\n",stderr); exit(21); }
}
static ABI int32_t content_init(const unsigned char *init,unsigned char *boot) {
    require_loaded();
    if (!init || !boot) return PARAMETER;
    if (initialized) return BUSY;
    /* Only the reserved-zero init profile is implemented. */
    for (unsigned i=0;i<32;++i) if (init[i]) return PARAMETER;
    memset(boot,0,40); initialized=1;
    printf("Runtime: AppContent initialized; offline base-game profile, %u add-on(s)\n",addon_count);
    return 0;
}
static void require_initialized(void) {
    require_loaded();
    if (!initialized) { fputs("STOP: AppContent query before initialization\n",stderr); exit(21); }
}
static ABI int32_t param_int(uint32_t id,int32_t *out) {
    require_initialized();
    if (id>4 || !out) return PARAMETER;
    memcpy(out,&parameters[id],4); ++queries;
    printf("Runtime: AppContent parameter %u = %d\n",id,*out);
    return 0;
}
static ABI int32_t addon_list(uint32_t service,void *list,uint32_t capacity,uint32_t *hits) {
    require_initialized();
    if (service) { fputs("STOP: nonzero AppContent service label unsupported\n",stderr); exit(21); }
    if ((!capacity || !list) && !hits) return PARAMETER;
    ++lists;
    /* Without a list: the number of add-ons. With one: up to capacity entries, never touching
     * the unused slots. BB_ADDCONT_STATUS overrides the status (tests). */
    if (!capacity || !list) { *hits=addon_count; return 0; }
    static int status_read; static uint32_t status=ADDCONT_INSTALLED;
    if (!status_read) { const char *v=getenv("BB_ADDCONT_STATUS"); if (v && *v) status=(uint32_t)strtoul(v,NULL,0); status_read=1; }
    AddcontInfo *out=list;
    uint32_t n=addon_count<capacity ? addon_count : capacity;
    for (uint32_t i=0;i<n;++i) {
        memset(&out[i],0,sizeof(out[i]));
        memcpy(out[i].label,addons[i],17);
        out[i].status=status;
    }
    if (hits) *hits=n;
    if (lists<=3) printf("Runtime: AppContent add-on list: %u of %u\n",n,addon_count);
    return 0;
}
static ABI int32_t addcont_mount(uint32_t service,const void *label_arg,char *mount_point) {
    require_initialized();
    if (service > 7 || !label_arg || !mount_point) return PARAMETER;
    const char *label = (const char *)label_arg;
    if (!memchr(label, '\0', 17)) return PARAMETER;
    int index = runtime_content_addon_index(service, label);
    if (index < 0) {
        printf("Runtime: AppContent addcont_mount label '%s' not registered\n", label);
        return SCE_APP_CONTENT_ERROR_NOT_FOUND;
    }
    char guest[16], host[512];
    int guest_size = snprintf(guest, sizeof(guest), "/addcont%d", index);
    if (guest_size < 0 || (size_t)guest_size >= sizeof(guest)) {
        return SCE_APP_CONTENT_ERROR_NOT_FOUND;
    }
    int found = find_dlc_folder(label, host, sizeof(host));
    if (found != 0) {
        /* Fallback: use extracted_game/addcont if available so unlock keys and unified packages succeed */
        snprintf(host, sizeof(host), "extracted_game/addcont");
        DIR *d = opendir(host);
        if (d) {
            closedir(d);
            found = 0;
        }
    }
    if (found != 0) {
        printf("Runtime: AppContent addcont_mount label '%s' folder not found (0x80d90005)\n", label);
        return SCE_APP_CONTENT_ERROR_NOT_FOUND;
    }

    if (runtime_file_mount(guest, host) != 0) {
        return SCE_APP_CONTENT_ERROR_NOT_FOUND;
    }
    if (index == 0) {
        runtime_file_mount("/addcont0", host);
        runtime_file_mount("/addcont", host);
    }
    memset(mount_point, 0, 16);
    memcpy(mount_point, guest, (size_t)guest_size);
    printf("Runtime: AppContent mounted %s -> %s (label %s)\n", guest, host, label);
    return 0;
}
static ABI int32_t addcont_unmount(const char *mount_point) {
    if (!mount_point) return PARAMETER;
    printf("Runtime: AppContent unmount %s\n", mount_point);
    runtime_file_unmount(mount_point);
    return 0;
}
static ABI int32_t temp_mount2(uint32_t option,char *mount_point) {
    (void)option;
    if (!mount_point) return PARAMETER;
    snprintf(mount_point,16,"/temp0");
    return 0;
}
static ABI int32_t temp_space_kb(const char *mount_point,uint64_t *kb) {
    (void)mount_point;
    if (!kb) return PARAMETER;
    *kb=1024*1024;
    return 0;
}
static const RuntimeExport content_exports[]={
    {"sceAppContentAddcontMount",addcont_mount},
    {"sceAppContentAddcontUnmount",addcont_unmount},
    {"sceAppContentTemporaryDataMount2",temp_mount2},
    {"sceAppContentTemporaryDataGetAvailableSpaceKb",temp_space_kb},
    {"sceAppContentDownloadDataGetAvailableSpaceKb",temp_space_kb},
};
static ABI int32_t module_loaded_internal(uint32_t id) {
    if ((id&0xffff0000)!=0x80000000) return INVALID_ID;
    return module_loaded((uint16_t)id);
}
uintptr_t runtime_content_resolve(const char *name) {
    if (runtime_nid_equals(name,"g8cM39EUZ6o#libSceSysmodule")) return (uintptr_t)module_load;
    if (runtime_nid_equals(name,"fMP5NHUOaMk#libSceSysmodule")) return (uintptr_t)module_loaded;
    if (runtime_nid_equals(name,"ynFKQ5bfGks#libSceSysmodule")) return (uintptr_t)module_loaded_internal;
    if (runtime_nid_equals(name,"eR2bZFAAU0Q#libSceSysmodule")) return (uintptr_t)module_unload;
    if (runtime_nid_equals(name,"hHrGoGoNf+s#libSceSysmodule")) return (uintptr_t)module_load_internal;
    if (runtime_nid_equals(name,"R9lA82OraNs#libSceAppContent")) return (uintptr_t)content_init;
    if (runtime_nid_equals(name,"99b82IKXpH4#libSceAppContent")) return (uintptr_t)param_int;
    if (runtime_nid_equals(name,"xnd8BJzAxmk#libSceAppContent")) return (uintptr_t)addon_list;
    if (runtime_nid_equals(name,"VANhIWcqYak#libSceAppContent") ||
        runtime_nid_equals(name,"VANhIWcqYak")) return (uintptr_t)addcont_mount;
    if (runtime_nid_equals(name,"3rHWaV-1KC4#libSceAppContent") ||
        runtime_nid_equals(name,"3rHWaV-1KC4")) return (uintptr_t)addcont_unmount;
    return RUNTIME_LOOKUP(content_exports,name);
}
void runtime_content_report(void) {
    printf("Runtime: AppContent references=%u, initialized=%u, parameter queries=%u, list queries=%u\n",refs,initialized,queries,lists);
}
