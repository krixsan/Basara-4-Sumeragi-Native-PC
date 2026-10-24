#ifndef BASARA_LOG_H
#define BASARA_LOG_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    LOG_LEVEL_DEBUG = 0,
    LOG_LEVEL_INFO  = 1,
    LOG_LEVEL_WARN  = 2,
    LOG_LEVEL_ERROR = 3,
    LOG_LEVEL_FATAL = 4
} LogLevel;

void log_init(void);
void log_shutdown(void);
void log_write(LogLevel level, const char *subsystem, const char *fmt, ...);
void log_dump_ring_buffer(const char *target_path);

#define LOG_DEBUG(sub, ...) log_write(LOG_LEVEL_DEBUG, sub, __VA_ARGS__)
#define LOG_INFO(sub, ...)  log_write(LOG_LEVEL_INFO,  sub, __VA_ARGS__)
#define LOG_WARN(sub, ...)  log_write(LOG_LEVEL_WARN,  sub, __VA_ARGS__)
#define LOG_ERROR(sub, ...) log_write(LOG_LEVEL_ERROR, sub, __VA_ARGS__)
#define LOG_FATAL(sub, ...) log_write(LOG_LEVEL_FATAL, sub, __VA_ARGS__)

#ifdef __cplusplus
}
#endif

#endif /* BASARA_LOG_H */
