/* Offline tests for diagnostic accounting and unchanged public-call ordering. */
#include "jl_litert.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
typedef enum { kLiteRtTensorBufferLockModeWrite, kLiteRtTensorBufferLockModeRead } Mode;
struct jl_litert_buffer { unsigned char bytes[16]; int query,lock,unlock,locked; };
#define handle(b) (b)
static int query(jl_litert_buffer *b,size_t *n){++b->query;*n=sizeof(b->bytes);return 0;}
static int lock_buffer(jl_litert_buffer *b,void **p,Mode mode){(void)mode;assert(!b->locked);++b->lock;b->locked=1;*p=b->bytes;return 0;}
static int unlock_buffer(jl_litert_buffer *b){assert(b->locked);++b->unlock;b->locked=0;return 0;}
#define LiteRtGetTensorBufferPackedSize query
#define LiteRtLockTensorBuffer lock_buffer
#define LiteRtUnlockTensorBuffer unlock_buffer
#define TRY(name,...) do{if(name(__VA_ARGS__))return "api failure";}while(0)
static char *format(const char *f,size_t a,size_t b){(void)f;(void)a;(void)b;return "invalid bytes";}
#include "io_profile.inc"
int main(void){
  jl_litert_buffer input={0},output={0};
  unsigned char data[16],readback[16];
  for(size_t i=0;i<16;i++)data[i]=(unsigned char)(i*7);
  memcpy(output.bytes,data,16);
  jl_io_profile_register(&input,0,0,"image",16);
  jl_io_profile_register(&output,1,0,"out",16);
  jl_io_profile_begin(0);
  assert(!io_active && io_rows[0].count==0 && io_rows[1].count==0);
  jl_io_profile_begin(1);
  assert(io_active);
  for(int i=0;i<5;i++){
    assert(!io_measured_write(&input,data,16));
    assert(!memcmp(input.bytes,data,16));
    assert(!io_measured_read(&output,readback,16));
    assert(!memcmp(readback,data,16));
  }
  assert(input.query==5&&input.lock==5&&input.unlock==5&&!input.locked);
  assert(output.query==5&&output.lock==5&&output.unlock==5&&!output.locked);
  assert(io_rows[0].count==5&&io_rows[1].count==5);
  assert(io_measured_write(&input,data,15)!=NULL);
  assert(input.query==6&&input.lock==5&&input.unlock==5&&io_rows[0].count==5);
  jl_io_profile_end();
  assert(!io_active);
  jl_io_profile_report();
  puts("{\"offline_test\":\"passed\"}");
  return 0;
}
