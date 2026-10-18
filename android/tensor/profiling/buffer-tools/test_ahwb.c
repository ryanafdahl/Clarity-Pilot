#define _GNU_SOURCE
#include <assert.h>
#include <signal.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include "jl_litert.c"
int jl_bench_mode=5;

struct AHardwareBuffer { AHardwareBuffer_Desc desc; int refs; unsigned char bytes[64]; };
struct LiteRtTensorBufferT { AHardwareBuffer *ahwb; int locked; };
struct LiteRtTensorBufferRequirementsT { int unused; };
static struct LiteRtTensorBufferRequirementsT mock_req;
static int allocations,releases,imports,destroys,locks,unlocks;
static int api_step,fail_step,req_types,req_strides,supported,allocate_fail;
static int desc_mismatch,import_failure_with_handle,type_mismatch,identity_mismatch;
static int lock_fail,unlock_fail,packed_overflow,no_ahwb;
static size_t req_bytes;
static uint64_t allocated_usage;
static int cleanup_sequence[8],cleanup_count;
static const char *mock_status(LiteRtStatus s){(void)s;return "mock failure";}
static LiteRtStatus next(void){return ++api_step==fail_step?kLiteRtStatusErrorRuntimeFailure:kLiteRtStatusOk;}
static LiteRtStatus get_req(LiteRtCompiledModel m,LiteRtParamIndex s,LiteRtParamIndex i,LiteRtTensorBufferRequirements *out){
  (void)m;(void)s;(void)i;*out=&mock_req;return next();
}
static LiteRtStatus get_count(LiteRtTensorBufferRequirements r,int *out){assert(r==&mock_req);*out=req_types;return next();}
static LiteRtStatus get_type(LiteRtTensorBufferRequirements r,int i,LiteRtTensorBufferType *out){
  assert(r==&mock_req);*out=i==0&&!no_ahwb?kLiteRtTensorBufferTypeAhwb:kLiteRtTensorBufferTypeHostMemory;return next();
}
static LiteRtStatus get_size(LiteRtTensorBufferRequirements r,size_t *out){assert(r==&mock_req);*out=req_bytes;return next();}
static LiteRtStatus get_strides(LiteRtTensorBufferRequirements r,int *n,const uint32_t **out){
  assert(r==&mock_req);*n=req_strides;*out=NULL;return next();
}
static LiteRtStatus get_alignment(LiteRtTensorBufferRequirements r,size_t *out){assert(r==&mock_req);*out=64;return next();}
int AHardwareBuffer_isSupported(const AHardwareBuffer_Desc *d){assert(d->width==req_bytes);return supported;}
int AHardwareBuffer_allocate(const AHardwareBuffer_Desc *d,AHardwareBuffer **out){
  ++allocations;
  if(allocate_fail){*out=NULL;return -1;}
  AHardwareBuffer *b=calloc(1,sizeof(*b));assert(b);b->desc=*d;b->refs=1;
  memset(b->bytes,0xa5,sizeof(b->bytes));*out=b;allocated_usage=d->usage;return 0;
}
void AHardwareBuffer_describe(const AHardwareBuffer *b,AHardwareBuffer_Desc *d){assert(b->refs==1);*d=b->desc;if(desc_mismatch)++d->width;}
void AHardwareBuffer_release(AHardwareBuffer *b){assert(b&&b->refs==1);--b->refs;++releases;cleanup_sequence[cleanup_count++]=2;free(b);}
static LiteRtStatus import_buffer(LiteRtEnvironment e,const LiteRtRankedTensorType *t,AHardwareBuffer *a,size_t off,LiteRtAhwbDeallocator d,LiteRtTensorBuffer *out){
  (void)e;(void)t;assert(a&&a->refs==1&&off==0&&d==NULL);++imports;
  LiteRtStatus status=next();
  if(status!=kLiteRtStatusOk&&!import_failure_with_handle){*out=NULL;return status;}
  *out=calloc(1,sizeof(**out));assert(*out);(*out)->ahwb=a;return status;
}
static LiteRtStatus actual_type(LiteRtTensorBuffer b,LiteRtTensorBufferType *out){assert(b);*out=type_mismatch?kLiteRtTensorBufferTypeHostMemory:kLiteRtTensorBufferTypeAhwb;return next();}
static LiteRtStatus actual_ahwb(LiteRtTensorBuffer b,AHardwareBuffer **out){assert(b);*out=identity_mismatch?NULL:b->ahwb;return next();}
static LiteRtStatus actual_size(LiteRtTensorBuffer b,size_t *out){assert(b);*out=req_bytes;return next();}
static LiteRtStatus packed_size(LiteRtTensorBuffer b,size_t *out){assert(b);*out=packed_overflow?req_bytes+1:32;return next();}
static LiteRtStatus lock_tensor(LiteRtTensorBuffer b,void **out,LiteRtTensorBufferLockMode mode){
  (void)mode;assert(!b->locked&&b->ahwb->refs==1);++locks;
  if(lock_fail)return kLiteRtStatusErrorRuntimeFailure;
  b->locked=1;*out=b->ahwb->bytes;return kLiteRtStatusOk;
}
static LiteRtStatus unlock_tensor(LiteRtTensorBuffer b){
  assert(b->locked);++unlocks;if(unlock_fail)return kLiteRtStatusErrorRuntimeFailure;b->locked=0;return kLiteRtStatusOk;
}
static void destroy_tensor(LiteRtTensorBuffer b){
  assert(b&&!b->locked&&b->ahwb->refs==1);++destroys;cleanup_sequence[cleanup_count++]=1;free(b);
}
static jl_litert_model model;
static LiteRtRankedTensorType types[2];
static void reset(void){
  assert(ahwb_live==0);
  allocations=releases=imports=destroys=locks=unlocks=api_step=fail_step=0;
  req_types=1;req_strides=0;req_bytes=64;supported=1;allocate_fail=0;
  desc_mismatch=import_failure_with_handle=type_mismatch=identity_mismatch=lock_fail=unlock_fail=packed_overflow=no_ahwb=0;
  cleanup_count=0;allocated_usage=0;
  model=(jl_litert_model){.n_inputs=1,.n_outputs=1,.types=types};
  lrt.LiteRtGetStatusString=mock_status;
  lrt.LiteRtGetCompiledModelInputBufferRequirements=get_req;
  lrt.LiteRtGetCompiledModelOutputBufferRequirements=get_req;
  lrt.LiteRtGetNumTensorBufferRequirementsSupportedBufferTypes=get_count;
  lrt.LiteRtGetTensorBufferRequirementsSupportedTensorBufferType=get_type;
  lrt.LiteRtGetTensorBufferRequirementsBufferSize=get_size;
  lrt.LiteRtGetTensorBufferRequirementsStrides=get_strides;
  lrt.LiteRtGetTensorBufferRequirementsAlignment=get_alignment;
  lrt.LiteRtCreateTensorBufferFromAhwb=import_buffer;
  lrt.LiteRtGetTensorBufferType=actual_type;lrt.LiteRtGetTensorBufferAhwb=actual_ahwb;
  lrt.LiteRtGetTensorBufferSize=actual_size;lrt.LiteRtGetTensorBufferPackedSize=packed_size;
  lrt.LiteRtLockTensorBuffer=lock_tensor;lrt.LiteRtUnlockTensorBuffer=unlock_tensor;lrt.LiteRtDestroyTensorBuffer=destroy_tensor;
  setenv("BENCH_AHWB_USAGE","rarely",1);
}
static void expect_failure(void){
  jl_litert_buffer *b=(jl_litert_buffer*)1;
  char *error=jl_litert_buffer_create(&model,0,0,&b);
  assert(error&&b==NULL&&ahwb_live==0);free(error);
  assert(locks==0&&unlocks==0);
  assert(releases==allocations-(allocate_fail?1:0));
  if(destroys){assert(cleanup_count==2&&cleanup_sequence[0]==1&&cleanup_sequence[1]==2);}
}
static void success(const char *mode,int output){
  reset();setenv("BENCH_AHWB_USAGE",mode,1);req_types=2;
  jl_litert_buffer *b=NULL;assert(!jl_litert_buffer_create(&model,output,0,&b));
  assert(b&&ahwb_live==1&&allocations==1&&imports==1&&locks==1&&unlocks==1);
  assert(allocated_usage==((UINT64_C(1)<<24)|(!strcmp(mode,"often")?0x33:0x22)));
  for(int i=0;i<32;++i)assert(((LiteRtTensorBuffer)b)->ahwb->bytes[i]==0);
  for(int i=32;i<64;++i)assert(((LiteRtTensorBuffer)b)->ahwb->bytes[i]==0xa5);
  unsigned char data[32],out[32];for(int i=0;i<32;++i)data[i]=(unsigned char)(i*13);
  assert(!jl_litert_buffer_write(b,data,32));assert(!jl_litert_buffer_read(b,out,32));
  assert(!memcmp(data,out,32));assert(locks==3&&unlocks==3);
  AHardwareBuffer *retained=((LiteRtTensorBuffer)b)->ahwb;
  jl_litert_buffer_release(b);assert(ahwb_live==1&&destroys==1&&releases==0);
  /* Simulated model cache still has access after the caller wrapper is dropped. */
  assert(retained->refs==1&&!memcmp(retained->bytes,data,32));
  jl_ahwb_release_after_model();
  assert(ahwb_live==0&&destroys==1&&releases==1);
  assert(cleanup_sequence[0]==1&&cleanup_sequence[1]==2);
  jl_litert_buffer_release(NULL);assert(destroys==1);
}
static void death(int lock_error){
  pid_t child=fork();assert(child>=0);
  if(!child){
    struct rlimit limit={0,0};setrlimit(RLIMIT_CORE,&limit);
    reset();lock_fail=lock_error;unlock_fail=!lock_error;
    jl_litert_buffer *b=NULL;char *error=jl_litert_buffer_create(&model,0,0,&b);free(error);_exit(99);
  }
  int status;assert(waitpid(child,&status,0)==child);assert(WIFSIGNALED(status)&&WTERMSIG(status)==SIGABRT);
}
int main(void){
  setvbuf(stdout,NULL,_IOLBF,0);
  reset();
  success("rarely",0);success("often",0);success("rarely",1);success("often",1);
  for(int step=1;step<=11;++step){reset();fail_step=step;expect_failure();}
  reset();fail_step=7;import_failure_with_handle=1;expect_failure();
  reset();no_ahwb=1;expect_failure();
  reset();req_types=0;expect_failure();
  reset();req_types=65;expect_failure();
  reset();req_strides=1;expect_failure();
  reset();req_bytes=0;expect_failure();
  reset();req_bytes=(size_t)UINT32_MAX+1;expect_failure();
  reset();supported=0;expect_failure();
  reset();allocate_fail=1;expect_failure();
  reset();desc_mismatch=1;expect_failure();
  reset();type_mismatch=1;expect_failure();
  reset();identity_mismatch=1;expect_failure();
  reset();packed_overflow=1;expect_failure();
  reset();unsetenv("BENCH_AHWB_USAGE");expect_failure();
  reset();setenv("BENCH_AHWB_USAGE","bad",1);expect_failure();
  reset();death(1);death(0);
  puts("{\"offline_tests\":\"passed\",\"unchanged_copy_and_lock_order\":true,\"cleanup_order_verified\":true,\"init_lock_failure_aborts\":true}");
  return 0;
}


