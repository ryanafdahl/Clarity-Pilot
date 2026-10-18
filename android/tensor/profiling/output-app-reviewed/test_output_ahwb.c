#define _GNU_SOURCE
#define JL_OUTPUT_AHWB_HOST_TEST 1
#include <assert.h>
#include <signal.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include <stdlib.h>
static int inject_oom;
static void *fixture_malloc(size_t size){return inject_oom?NULL:malloc(size);}
#define malloc fixture_malloc
#include "jl_litert.c"
#undef malloc


struct AHardwareBuffer { AHardwareBuffer_Desc desc; int refs; unsigned char bytes[64]; };
struct LiteRtTensorBufferT { AHardwareBuffer *ahwb; int locked; unsigned char managed[64]; };
struct LiteRtTensorBufferRequirementsT { int unused; };
static struct LiteRtTensorBufferRequirementsT mock_req;
static int allocations,releases,imports,destroys,locks,unlocks,managed_creates,compiled_destroys;
static AHardwareBuffer *cached[8]; static int cached_count;
static int api_step,fail_step,req_types,req_strides,supported,allocate_fail;
static int desc_mismatch,import_failure_with_handle,type_mismatch,identity_mismatch;
static int lock_fail,unlock_fail,packed_overflow,no_ahwb;
static size_t req_bytes;
static uint64_t allocated_usage;
static int cleanup_sequence[32],cleanup_count;
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
  (void)mode;assert(!b->locked&&(!b->ahwb||b->ahwb->refs==1));++locks;
  if(lock_fail)return kLiteRtStatusErrorRuntimeFailure;
  b->locked=1;*out=b->ahwb?b->ahwb->bytes:b->managed;return kLiteRtStatusOk;
}
static LiteRtStatus unlock_tensor(LiteRtTensorBuffer b){
  assert(b->locked);++unlocks;if(unlock_fail)return kLiteRtStatusErrorRuntimeFailure;b->locked=0;return kLiteRtStatusOk;
}
static void destroy_tensor(LiteRtTensorBuffer b){
  assert(b&&!b->locked&&(!b->ahwb||b->ahwb->refs==1));++destroys;cleanup_sequence[cleanup_count++]=1;free(b);
}
static LiteRtStatus managed_buffer(LiteRtEnvironment e,const LiteRtRankedTensorType *t,LiteRtTensorBufferRequirements r,LiteRtTensorBuffer *out){
  (void)e;(void)t;assert(r==&mock_req);++managed_creates;*out=calloc(1,sizeof(**out));assert(*out);return kLiteRtStatusOk;
}
static void compiled_destroy(LiteRtCompiledModel c){
  assert(c==(LiteRtCompiledModel)1);++compiled_destroys;cleanup_sequence[cleanup_count++]=3;
  for(int i=0;i<cached_count;++i)assert(cached[i]->refs==1);
  cached_count=0;
}
static void noop(void){}
static jl_litert_model *model;
static void reset(void){
  assert(!model);
  allocations=releases=imports=destroys=locks=unlocks=api_step=fail_step=0;
  managed_creates=compiled_destroys=cached_count=0;
  req_types=1;req_strides=0;req_bytes=64;supported=1;allocate_fail=0;
  desc_mismatch=import_failure_with_handle=type_mismatch=identity_mismatch=lock_fail=unlock_fail=packed_overflow=no_ahwb=0;
  cleanup_count=0;allocated_usage=0;
  model=calloc(1,sizeof(*model));assert(model);
  model->n_inputs=6;model->n_outputs=1;model->types=calloc(8,sizeof(*model->types));assert(model->types);
  model->output_ahwb=true;model->compiled=(LiteRtCompiledModel)1;
  /* Complete the actual once guard before injecting the API fixture table. */
  pthread_once(&output_ahwb_once,noop);output_ahwb_available=true;
  output_ahwb_platform.supported=AHardwareBuffer_isSupported;
  output_ahwb_platform.allocate=AHardwareBuffer_allocate;
  output_ahwb_platform.describe=AHardwareBuffer_describe;
  output_ahwb_platform.release=AHardwareBuffer_release;
  lrt.LiteRtGetStatusString=mock_status;
  lrt.LiteRtDestroyCompiledModel=compiled_destroy;
  lrt.LiteRtCreateManagedTensorBufferFromRequirements=managed_buffer;
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
}
static void finish(void){jl_litert_model_release(model);model=NULL;assert(compiled_destroys==1);}
static void expect_failure(void){
  jl_litert_buffer *b=(jl_litert_buffer*)1;
  char *error=jl_litert_buffer_create(model,1,0,&b);
  assert(error&&b==NULL&&!model->owned_outputs);free(error);
  assert(locks==0&&unlocks==0);
  assert(releases==allocations-(allocate_fail?1:0));
  if(destroys){assert(cleanup_count==2&&cleanup_sequence[0]==1&&cleanup_sequence[1]==2);}
  finish();
}
static void success(void){
  reset();req_types=2;
  jl_litert_buffer *b=NULL;assert(!jl_litert_buffer_create(model,1,0,&b));
  assert(b&&model->owned_outputs&&allocations==1&&imports==1&&locks==1&&unlocks==1&&!managed_creates);
  assert(allocated_usage==((UINT64_C(1)<<24)|(JL_OUTPUT_AHWB_OFTEN?0x33:0x22)));
  for(int i=0;i<32;++i)assert(((LiteRtTensorBuffer)b)->ahwb->bytes[i]==0);
  for(int i=32;i<64;++i)assert(((LiteRtTensorBuffer)b)->ahwb->bytes[i]==0xa5);
  unsigned char data[32],out[32];for(int i=0;i<32;++i)data[i]=(unsigned char)(i*13);
  assert(!jl_litert_buffer_write(b,data,32));assert(!jl_litert_buffer_read(b,out,32));
  assert(!memcmp(data,out,32));assert(locks==3&&unlocks==3);
  cached[cached_count++]=((LiteRtTensorBuffer)b)->ahwb;
  jl_litert_buffer_release(b);assert(destroys==1&&releases==0);
  assert(!memcmp(cached[0]->bytes,data,32));
  finish();assert(releases==1&&cleanup_count==3);
  assert(cleanup_sequence[0]==1&&cleanup_sequence[1]==3&&cleanup_sequence[2]==2);
  jl_litert_buffer_release(NULL);assert(destroys==1);
}
static void seven_buffers(void){
  reset();jl_litert_buffer *buffers[7]={0};
  for(int i=0;i<7;++i){
    int output=i==6;size_t index=output?0:(size_t)i;
    assert(!jl_litert_buffer_create(model,output,index,&buffers[i]));
    assert((i==6)==(((LiteRtTensorBuffer)buffers[i])->ahwb!=NULL));
  }
  assert(managed_creates==6&&allocations==1&&locks==7&&unlocks==7);
  cached[cached_count++]=((LiteRtTensorBuffer)buffers[6])->ahwb;
  for(int i=0;i<7;++i)jl_litert_buffer_release(buffers[i]);
  assert(destroys==7&&releases==0);finish();
  assert(releases==1&&cleanup_count==9);
  for(int i=0;i<7;++i)assert(cleanup_sequence[i]==1);
  assert(cleanup_sequence[7]==3&&cleanup_sequence[8]==2);
}
static void other_backend(void){
  reset();model->output_ahwb=false;output_ahwb_available=false;
  jl_litert_buffer *b=NULL;assert(!jl_litert_buffer_create(model,1,0,&b));
  assert(managed_creates==1&&!allocations&&!imports&&!model->owned_outputs);
  jl_litert_buffer_release(b);finish();
}
static void partial_rebind(void){
  reset();jl_litert_buffer *first=NULL,*second=NULL;
  assert(!jl_litert_buffer_create(model,1,0,&first));cached[cached_count++]=((LiteRtTensorBuffer)first)->ahwb;
  api_step=0;fail_step=7;char *error=jl_litert_buffer_create(model,1,0,&second);
  assert(error&&!second);free(error);assert(model->owned_outputs&&!model->owned_outputs->next&&releases==1);
  jl_litert_buffer_release(first);finish();assert(releases==2);
}
static void multiple_outputs(void){
  reset();model->n_outputs=2;jl_litert_buffer *a=NULL,*b=NULL;
  assert(!jl_litert_buffer_create(model,1,0,&a));assert(!jl_litert_buffer_create(model,1,1,&b));
  cached[cached_count++]=((LiteRtTensorBuffer)a)->ahwb;cached[cached_count++]=((LiteRtTensorBuffer)b)->ahwb;
  jl_litert_buffer_release(a);jl_litert_buffer_release(b);assert(releases==0);finish();assert(releases==2);
}
static LiteRtStatus failed_run(LiteRtCompiledModel c,LiteRtParamIndex s,size_t ni,LiteRtTensorBuffer *in,size_t no,LiteRtTensorBuffer *out){
  (void)c;(void)s;(void)ni;(void)in;(void)no;(void)out;return kLiteRtStatusErrorRuntimeFailure;
}
static void oom_death(int run){
  pid_t child=fork();assert(child>=0);
  if(!child){
    struct rlimit limit={0,0};setrlimit(RLIMIT_CORE,&limit);reset();
    jl_litert_buffer *b=NULL;assert(!jl_litert_buffer_create(model,1,0,&b));
    unlock_fail=1;lrt.LiteRtRunCompiledModel=failed_run;inject_oom=1;
    char *error=run?jl_litert_run(model,NULL,0,&b,1):jl_litert_buffer_write(b,NULL,0);
    (void)error;_exit(99);
  }
  int status;assert(waitpid(child,&status,0)==child);assert(WIFSIGNALED(status)&&WTERMSIG(status)==SIGABRT);
}
static void death(int lock_error){
  pid_t child=fork();assert(child>=0);
  if(!child){
    struct rlimit limit={0,0};setrlimit(RLIMIT_CORE,&limit);
    reset();lock_fail=lock_error;unlock_fail=!lock_error;
    jl_litert_buffer *b=NULL;char *error=jl_litert_buffer_create(model,1,0,&b);free(error);_exit(99);
  }
  int status;assert(waitpid(child,&status,0)==child);assert(WIFSIGNALED(status)&&WTERMSIG(status)==SIGABRT);
}
int main(void){
  setvbuf(stdout,NULL,_IOLBF,0);
  success();seven_buffers();other_backend();partial_rebind();multiple_outputs();
  for(int step=1;step<=11;++step){reset();fail_step=step;expect_failure();}
  reset();fail_step=7;import_failure_with_handle=1;expect_failure();
  reset();no_ahwb=1;expect_failure();
  reset();req_types=0;expect_failure();reset();req_types=65;expect_failure();
  reset();req_strides=1;expect_failure();reset();req_bytes=0;expect_failure();
  reset();req_bytes=(size_t)UINT32_MAX+1;expect_failure();reset();supported=0;expect_failure();
  reset();allocate_fail=1;expect_failure();reset();desc_mismatch=1;expect_failure();
  reset();type_mismatch=1;expect_failure();reset();identity_mismatch=1;expect_failure();
  reset();packed_overflow=1;expect_failure();reset();output_ahwb_available=false;expect_failure();
  death(1);death(0);oom_death(0);oom_death(1);
  puts("app output ownership fixtures passed");return 0;
}
