/* Diagnostic only: no writes, reads, locks, unlocks or synchronization skipped.
 * Aggregation follows timed API stages; single benchmark thread. */
#include "io_profile.h"
#include <inttypes.h>
typedef struct {
  jl_litert_buffer *buffer;
  int output;
  size_t index, bytes;
  char name[128];
  uint64_t count, ns[4], max_ns[4], min_ns[4];
} jl_io_profile_row;
static jl_io_profile_row io_rows[64];
static size_t io_row_count;
static int io_active;
static uint64_t io_clock_mean_ns, io_clock_min_ns, io_clock_max_ns;
static uint64_t io_now(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_MONOTONIC, &ts)) abort();
  return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}
static jl_io_profile_row *io_row(jl_litert_buffer *buffer) {
  for (size_t i=0;i<io_row_count;++i) if(io_rows[i].buffer==buffer)return &io_rows[i];
  fprintf(stderr,"Unregistered buffer in measured I/O\n");abort();
}
void jl_io_profile_register(jl_litert_buffer *buffer,int output,size_t index,const char *name,size_t bytes) {
  if(io_row_count>=64||!buffer||!name||!bytes)abort();
  for(size_t i=0;i<io_row_count;++i)if(io_rows[i].buffer==buffer)abort();
  jl_io_profile_row *r=&io_rows[io_row_count++];
  *r=(jl_io_profile_row){.buffer=buffer,.output=output,.index=index,.bytes=bytes};
  snprintf(r->name,sizeof(r->name),"%s",name);
  for(int k=0;k<4;++k)r->min_ns[k]=UINT64_MAX;
}
void jl_io_profile_begin(int enabled) {
  /* Timer floor reported, never subtracted. Five reads per measured copy. */
  uint64_t total=0,minimum=UINT64_MAX,maximum=0;
  for(int i=0;i<10000;++i) {
    uint64_t a=io_now(),b=io_now(),delta=b-a;total+=delta;
    if(delta<minimum)minimum=delta;
    if(delta>maximum)maximum=delta;
  }
  io_clock_mean_ns=total/10000;io_clock_min_ns=minimum;io_clock_max_ns=maximum;io_active=enabled;
}
void jl_io_profile_end(void){io_active=0;}
static void io_record(jl_litert_buffer *buffer,int output,size_t bytes,const uint64_t t[5]) {
  jl_io_profile_row *r=io_row(buffer);
  if(r->output!=output||r->bytes!=bytes)abort();
  ++r->count;
  for(int k=0;k<4;++k) {
    uint64_t duration=t[k+1]-t[k];r->ns[k]+=duration;
    if(duration<r->min_ns[k])r->min_ns[k]=duration;
    if(duration>r->max_ns[k])r->max_ns[k]=duration;
  }
}
static void io_json_string(const char *s) {
  putchar('"');
  for(const unsigned char *p=(const unsigned char *)s;*p;++p) {
    if(*p=='"'||*p=='\\'){putchar('\\');putchar(*p);}
    else if(*p<32)printf("\\u%04x",*p);
    else putchar(*p);
  }
  putchar('"');
}
void jl_io_profile_report(void) {
  printf("{\"diagnostic\":\"io_clock\",\"samples\":10000,\"mean_ns\":%" PRIu64
         ",\"min_ns\":%" PRIu64 ",\"max_ns\":%" PRIu64
         ",\"clock_reads_per_measured_copy\":5,\"overhead_subtracted\":false}\n",
         io_clock_mean_ns,io_clock_min_ns,io_clock_max_ns);
  const char *stages[]={"packed_size_query","lock","memcpy","unlock"};
  for(size_t i=0;i<io_row_count;++i) {
    const jl_io_profile_row *r=&io_rows[i];
    printf("{\"diagnostic\":\"buffer_io\",\"direction\":\"%s\",\"index\":%zu,\"name\":",
           r->output?"output_read":"input_write",r->index);
    io_json_string(r->name);
    printf(",\"logical_bytes\":%zu,\"measured_copies\":%" PRIu64 ",\"stages\":{",r->bytes,r->count);
    for(int k=0;k<4;++k) {
      if(k)putchar(',');
      printf("\"%s\":{\"total_ns\":%" PRIu64 ",\"mean_ns\":%.3f,\"min_ns\":%" PRIu64 ",\"max_ns\":%" PRIu64 "}",
             stages[k],r->ns[k],r->count?(double)r->ns[k]/r->count:0.0,
             r->count?r->min_ns[k]:0,r->max_ns[k]);
    }
    printf("}}\n");
  }
}
static char *io_measured_write(jl_litert_buffer *buffer,const void *data,size_t nbytes) {
  void *host=NULL;size_t size=0;uint64_t t[5];
  t[0]=io_now();
  TRY(LiteRtGetTensorBufferPackedSize,handle(buffer),&size);
  if(data!=NULL&&nbytes!=0&&nbytes!=size)return format("a copy of %zu bytes for a tensor of %zu",nbytes,size);
  t[1]=io_now();
  TRY(LiteRtLockTensorBuffer,handle(buffer),&host,kLiteRtTensorBufferLockModeWrite);
  t[2]=io_now();
  if(data!=NULL)memcpy(host,data,size);else memset(host,0,size);
  t[3]=io_now();
  TRY(LiteRtUnlockTensorBuffer,handle(buffer));
  t[4]=io_now();
  io_record(buffer,0,size,t);
  return NULL;
}
static char *io_measured_read(jl_litert_buffer *buffer,void *data,size_t nbytes) {
  void *host=NULL;size_t size=0;uint64_t t[5];
  t[0]=io_now();
  TRY(LiteRtGetTensorBufferPackedSize,handle(buffer),&size);
  if(nbytes!=0&&nbytes!=size)return format("a copy of %zu bytes for a tensor of %zu",nbytes,size);
  t[1]=io_now();
  TRY(LiteRtLockTensorBuffer,handle(buffer),&host,kLiteRtTensorBufferLockModeRead);
  t[2]=io_now();
  memcpy(data,host,size);
  t[3]=io_now();
  TRY(LiteRtUnlockTensorBuffer,handle(buffer));
  t[4]=io_now();
  io_record(buffer,1,size,t);
  return NULL;
}
