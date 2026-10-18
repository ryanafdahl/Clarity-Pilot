#ifndef MOCK_ANDROID_HARDWARE_BUFFER_H
#define MOCK_ANDROID_HARDWARE_BUFFER_H
#include <stdint.h>
typedef struct AHardwareBuffer AHardwareBuffer;
typedef struct {
  uint32_t width,height,layers,format;
  uint64_t usage;
  uint32_t stride,rfu0;
  uint64_t rfu1;
} AHardwareBuffer_Desc;
#define AHARDWAREBUFFER_FORMAT_BLOB 0x21U
#define AHARDWAREBUFFER_USAGE_CPU_READ_RARELY UINT64_C(2)
#define AHARDWAREBUFFER_USAGE_CPU_READ_OFTEN UINT64_C(3)
#define AHARDWAREBUFFER_USAGE_CPU_WRITE_RARELY (UINT64_C(2)<<4)
#define AHARDWAREBUFFER_USAGE_CPU_WRITE_OFTEN (UINT64_C(3)<<4)
#define AHARDWAREBUFFER_USAGE_GPU_DATA_BUFFER (UINT64_C(1)<<24)
int AHardwareBuffer_isSupported(const AHardwareBuffer_Desc*);
int AHardwareBuffer_allocate(const AHardwareBuffer_Desc*,AHardwareBuffer**);
void AHardwareBuffer_describe(const AHardwareBuffer*,AHardwareBuffer_Desc*);
void AHardwareBuffer_release(AHardwareBuffer*);
#endif
