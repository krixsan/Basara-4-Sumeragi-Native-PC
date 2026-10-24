#define _CRT_SECURE_NO_WARNINGS
#include "log.h"
#include <stdint.h>
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

#define RING_BUFFER_SIZE 1000
#define LINE_MAX_LEN 256
#define MAX_LOG_FILE_SIZE (10 * 1024 * 1024) /* 10MB */
#define MAX_BACKUP_FILES 4

static CRITICAL_SECTION s_log_cs;
static int s_initialized = 0;
static LogLevel s_current_level = LOG_LEVEL_INFO;
static FILE *s_log_file = NULL;
static int64_t s_current_file_bytes = 0;

static char s_ring_buffer[RING_BUFFER_SIZE][LINE_MAX_LEN];
static int s_ring_head = 0;
static int s_ring_count = 0;

static const char *s_level_strings[] = {
    "DEBUG",
    "INFO",
    "WARN",
    "ERROR",
    "FATAL"
};

static void read_ini_log_level(void) {
    FILE *f = fopen("basara.ini", "r");
    if (!f) return;
    char line[256];
    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == ';' || *p == '\r' || *p == '\n' || *p == '\0') continue;
        char *eq = strchr(p, '=');
        if (eq) {
            *eq = '\0';
            char *k = p, *v = eq + 1;
            char *kend = k + strlen(k) - 1;
            while (kend >= k && (*kend == ' ' || *kend == '\t')) *kend-- = '\0';
            while (*v == ' ' || *v == '\t') v++;
            char *vend = v + strlen(v) - 1;
            while (vend >= v && (*vend == ' ' || *vend == '\t' || *vend == '\r' || *vend == '\n')) *vend-- = '\0';
            if (strcmp(k, "log_level") == 0) {
                if (_stricmp(v, "debug") == 0) s_current_level = LOG_LEVEL_DEBUG;
                else if (_stricmp(v, "info") == 0) s_current_level = LOG_LEVEL_INFO;
                else if (_stricmp(v, "warn") == 0) s_current_level = LOG_LEVEL_WARN;
                else if (_stricmp(v, "error") == 0) s_current_level = LOG_LEVEL_ERROR;
                break;
            }
        }
    }
    fclose(f);
}

static void rotate_logs_locked(void) {
    if (s_log_file) {
        fclose(s_log_file);
        s_log_file = NULL;
    }
    char old_name[MAX_PATH];
    char new_name[MAX_PATH];

    snprintf(old_name, sizeof(old_name), "user/logs/basara.%d.log", MAX_BACKUP_FILES);
    DeleteFileA(old_name);

    for (int i = MAX_BACKUP_FILES - 1; i >= 1; --i) {
        snprintf(old_name, sizeof(old_name), "user/logs/basara.%d.log", i);
        snprintf(new_name, sizeof(new_name), "user/logs/basara.%d.log", i + 1);
        MoveFileExA(old_name, new_name, MOVEFILE_REPLACE_EXISTING);
    }

    MoveFileExA("user/logs/basara.log", "user/logs/basara.1.log", MOVEFILE_REPLACE_EXISTING);

    s_log_file = fopen("user/logs/basara.log", "w");
    if (s_log_file) {
        setvbuf(s_log_file, NULL, _IONBF, 0);
    }
    s_current_file_bytes = 0;
}

void log_init(void) {
    if (s_initialized) return;
    InitializeCriticalSection(&s_log_cs);
    s_initialized = 1;

    read_ini_log_level();

    CreateDirectoryA("user", NULL);
    CreateDirectoryA("user/logs", NULL);

    s_log_file = fopen("user/logs/basara.log", "a");
    if (s_log_file) {
        setvbuf(s_log_file, NULL, _IONBF, 0);
        fseek(s_log_file, 0, SEEK_END);
        s_current_file_bytes = _ftelli64(s_log_file);
        if (s_current_file_bytes >= MAX_LOG_FILE_SIZE) {
            rotate_logs_locked();
        }
    }
}

void log_shutdown(void) {
    if (!s_initialized) return;
    EnterCriticalSection(&s_log_cs);
    if (s_log_file) {
        fflush(s_log_file);
        fclose(s_log_file);
        s_log_file = NULL;
    }
    LeaveCriticalSection(&s_log_cs);
    DeleteCriticalSection(&s_log_cs);
    s_initialized = 0;
}

void log_write(LogLevel level, const char *subsystem, const char *fmt, ...) {
    if (!s_initialized) log_init();
    if (level < s_current_level) return;

    SYSTEMTIME st;
    GetLocalTime(&st);

    char msg[192];
    va_list args;
    va_start(args, fmt);
    vsnprintf(msg, sizeof(msg), fmt, args);
    va_end(args);

    const char *lvl_str = (level >= 0 && level <= LOG_LEVEL_FATAL) ? s_level_strings[level] : "UNKNOWN";

    char line[LINE_MAX_LEN];
    int len = snprintf(line, sizeof(line), "[%04u-%02u-%02u %02u:%02u:%02u.%03u] [%-5s] [%-8s] %s\n",
                       st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond, st.wMilliseconds,
                       lvl_str, subsystem ? subsystem : "core", msg);

    if (len < 0) return;
    if (len >= (int)sizeof(line)) len = (int)sizeof(line) - 1;

    EnterCriticalSection(&s_log_cs);

    /* Update ring buffer */
    memcpy(s_ring_buffer[s_ring_head], line, len + 1);
    s_ring_head = (s_ring_head + 1) % RING_BUFFER_SIZE;
    if (s_ring_count < RING_BUFFER_SIZE) s_ring_count++;

    /* Write to file */
    if (s_log_file) {
        fputs(line, s_log_file);
        s_current_file_bytes += len;
        fflush(s_log_file); /* Unbuffered flush on every write */
        if (s_current_file_bytes >= MAX_LOG_FILE_SIZE) {
            rotate_logs_locked();
        }
    }

    LeaveCriticalSection(&s_log_cs);

    /* Output to stderr as well */
    fputs(line, stderr);
}

void log_dump_ring_buffer(const char *target_path) {
    if (!s_initialized) return;

    /* Use TryEnterCriticalSection to guarantee zero deadlock in crash path */
    if (!TryEnterCriticalSection(&s_log_cs)) {
        FILE *f = fopen(target_path, "w");
        if (f) {
            fputs("[LOG RING BUFFER] Lock contention detected in crash path. Ring dump skipped to avoid deadlock.\n", f);
            fclose(f);
        }
        return;
    }

    FILE *f = fopen(target_path, "w");
    if (f) {
        int start = (s_ring_head - s_ring_count + RING_BUFFER_SIZE) % RING_BUFFER_SIZE;
        for (int i = 0; i < s_ring_count; ++i) {
            int idx = (start + i) % RING_BUFFER_SIZE;
            fputs(s_ring_buffer[idx], f);
        }
        fclose(f);
    }

    LeaveCriticalSection(&s_log_cs);
}
