#ifndef JL_IO_PROFILE_H
#define JL_IO_PROFILE_H
#include "jl_litert.h"
#include <stddef.h>
void jl_io_profile_register(jl_litert_buffer *buffer, int output, size_t index, const char *name, size_t bytes);
void jl_io_profile_begin(int enabled);
void jl_io_profile_end(void);
void jl_io_profile_report(void);
#endif
