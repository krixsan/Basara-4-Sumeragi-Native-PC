#ifndef BASARA_CRASH_REPORTER_H
#define BASARA_CRASH_REPORTER_H

#ifdef __cplusplus
extern "C" {
#endif

/* Collects system/hardware info and returns a heap-allocated JSON string (caller frees with free()) */
char *collect_hardware_info_json(void);

#ifdef __cplusplus
}
#endif

#endif /* BASARA_CRASH_REPORTER_H */
