#ifndef BARO_BAMBOO_H
#define BARO_BAMBOO_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

uintptr_t baro_engine_new(const char *method);
void baro_engine_free(uintptr_t handle);
void baro_engine_set_options(uintptr_t handle, bool modern_style,
                             bool free_marking, bool auto_restore);
void baro_engine_set_method(uintptr_t handle, const char *method);
void baro_engine_set_enabled(uintptr_t handle, bool enabled);
bool baro_engine_enabled(uintptr_t handle);
bool baro_engine_process_key(uintptr_t handle, uint32_t keyval);
bool baro_engine_backspace(uintptr_t handle);
char *baro_engine_pull_preedit(uintptr_t handle);
char *baro_engine_pull_commit(uintptr_t handle);
void baro_engine_commit(uintptr_t handle);
void baro_engine_reset(uintptr_t handle);
void baro_engine_string_free(char *text);

#ifdef __cplusplus
}
#endif

#endif
