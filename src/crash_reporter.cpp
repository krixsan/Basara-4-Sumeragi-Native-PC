#define _CRT_SECURE_NO_WARNINGS
#include "crash_reporter.h"
#include <stdint.h>
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef LONG (WINAPI *RtlGetVersion_t)(PRTL_OSVERSIONINFOW);

static void get_cpuid(uint32_t level, uint32_t *eax, uint32_t *ebx, uint32_t *ecx, uint32_t *edx) {
#if defined(__x86_64__) || defined(_M_X64)
    __asm__ volatile (
        "cpuid"
        : "=a"(*eax), "=b"(*ebx), "=c"(*ecx), "=d"(*edx)
        : "a"(level), "c"(0)
    );
#else
    *eax = *ebx = *ecx = *edx = 0;
#endif
}

static void escape_json_str(const char *src, char *dst, size_t dst_size) {
    size_t d = 0;
    for (size_t s = 0; src[s] != '\0' && d + 2 < dst_size; ++s) {
        if (src[s] == '"' || src[s] == '\\') {
            dst[d++] = '\\';
            dst[d++] = src[s];
        } else if (src[s] == '\n') {
            dst[d++] = '\\';
            dst[d++] = 'n';
        } else if (src[s] == '\r') {
            dst[d++] = '\\';
            dst[d++] = 'r';
        } else if (src[s] == '\t') {
            dst[d++] = '\\';
            dst[d++] = 't';
        } else if ((unsigned char)src[s] >= 32 && (unsigned char)src[s] <= 126) {
            dst[d++] = src[s];
        }
    }
    dst[d] = '\0';
}

char *collect_hardware_info_json(void) {
    char cpu_vendor[13] = {0};
    char cpu_brand[49] = {0};
    uint32_t eax, ebx, ecx, edx;

    /* CPU Vendor */
    get_cpuid(0, &eax, &ebx, &ecx, &edx);
    memcpy(cpu_vendor, &ebx, 4);
    memcpy(cpu_vendor + 4, &edx, 4);
    memcpy(cpu_vendor + 8, &ecx, 4);
    cpu_vendor[12] = '\0';

    /* CPU Brand string */
    get_cpuid(0x80000000, &eax, &ebx, &ecx, &edx);
    if (eax >= 0x80000004) {
        uint32_t brand_buf[12];
        get_cpuid(0x80000002, &brand_buf[0], &brand_buf[1], &brand_buf[2], &brand_buf[3]);
        get_cpuid(0x80000003, &brand_buf[4], &brand_buf[5], &brand_buf[6], &brand_buf[7]);
        get_cpuid(0x80000004, &brand_buf[8], &brand_buf[9], &brand_buf[10], &brand_buf[11]);
        memcpy(cpu_brand, brand_buf, 48);
        cpu_brand[48] = '\0';

        /* Trim leading spaces */
        char *p = cpu_brand;
        while (*p == ' ') p++;
        if (p != cpu_brand) memmove(cpu_brand, p, strlen(p) + 1);
    } else {
        snprintf(cpu_brand, sizeof(cpu_brand), "x86_64 Compatible Processor");
    }

    /* Logical processors */
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    DWORD num_cores = si.dwNumberOfProcessors;

    /* Memory info */
    MEMORYSTATUSEX ms;
    ms.dwLength = sizeof(ms);
    GlobalMemoryStatusEx(&ms);
    uint64_t total_ram_mb = ms.ullTotalPhys / (1024 * 1024);
    uint64_t avail_ram_mb = ms.ullAvailPhys / (1024 * 1024);

    /* Windows Version via RtlGetVersion */
    DWORD os_major = 0, os_minor = 0, os_build = 0;
    HMODULE hNtdll = GetModuleHandleA("ntdll.dll");
    if (hNtdll) {
        RtlGetVersion_t pRtlGetVersion = (RtlGetVersion_t)(void(*)(void))GetProcAddress(hNtdll, "RtlGetVersion");
        if (pRtlGetVersion) {
            RTL_OSVERSIONINFOW ovi = {0};
            ovi.dwOSVersionInfoSize = sizeof(ovi);
            if (pRtlGetVersion(&ovi) == 0) {
                os_major = ovi.dwMajorVersion;
                os_minor = ovi.dwMinorVersion;
                os_build = ovi.dwBuildNumber;
            }
        }
    }

    /* GPU display device name */
    char gpu_name[128] = "Unknown Graphics Device";
    DISPLAY_DEVICEA dd = {0};
    dd.cb = sizeof(dd);
    if (EnumDisplayDevicesA(NULL, 0, &dd, 0)) {
        if (dd.DeviceString[0]) {
            strncpy(gpu_name, dd.DeviceString, sizeof(gpu_name) - 1);
            gpu_name[sizeof(gpu_name) - 1] = '\0';
        }
    }

    char clean_cpu_vendor[64], clean_cpu_brand[128], clean_gpu_name[256];
    escape_json_str(cpu_vendor, clean_cpu_vendor, sizeof(clean_cpu_vendor));
    escape_json_str(cpu_brand, clean_cpu_brand, sizeof(clean_cpu_brand));
    escape_json_str(gpu_name, clean_gpu_name, sizeof(clean_gpu_name));

    size_t buf_size = 2048;
    char *json = (char *)malloc(buf_size);
    if (!json) return NULL;

    snprintf(json, buf_size,
        "{\n"
        "  \"cpu\": {\n"
        "    \"vendor\": \"%s\",\n"
        "    \"brand\": \"%s\",\n"
        "    \"logical_cores\": %lu\n"
        "  },\n"
        "  \"memory\": {\n"
        "    \"total_mb\": %llu,\n"
        "    \"avail_mb\": %llu\n"
        "  },\n"
        "  \"os\": {\n"
        "    \"platform\": \"Windows\",\n"
        "    \"major\": %lu,\n"
        "    \"minor\": %lu,\n"
        "    \"build\": %lu\n"
        "  },\n"
        "  \"gpu\": {\n"
        "    \"device_name\": \"%s\"\n"
        "  }\n"
        "}\n",
        clean_cpu_vendor, clean_cpu_brand, num_cores,
        (unsigned long long)total_ram_mb, (unsigned long long)avail_ram_mb,
        os_major, os_minor, os_build,
        clean_gpu_name
    );

    return json;
}
