#define _GNU_SOURCE
#include <assert.h>
#include <signal.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include "jl_litert.c"

struct LiteRtEventT { int id, status, completed; };
struct LiteRtTensorBufferT { int refs, lookup_status, clear_status; struct LiteRtEventT *event; };
static int submit_status, actual_async, sync_calls, async_calls, get_calls, wait_calls, clear_calls;
static int duplicate_calls, duplicate_status, destroy_calls, compiled_destroy_calls, lock_calls;
static int waited[8], cleared[8];
static LiteRtStatus mock_sync(LiteRtCompiledModel m,LiteRtParamIndex s,size_t ni,LiteRtTensorBuffer *in,size_t no,LiteRtTensorBuffer *out) {
  (void)m;(void)s;(void)ni;(void)in;(void)no;(void)out; ++sync_calls; return submit_status;
}
static LiteRtStatus mock_async(LiteRtCompiledModel m,LiteRtParamIndex s,size_t ni,LiteRtTensorBuffer *in,size_t no,LiteRtTensorBuffer *out,bool *actual) {
  (void)m;(void)s;(void)ni;(void)in;(void)no;(void)out; ++async_calls; *actual=actual_async;return submit_status;
}
static LiteRtStatus mock_event(LiteRtTensorBuffer b,LiteRtEvent *out) { ++get_calls;*out=b->event;return b->lookup_status; }
static LiteRtStatus mock_wait(LiteRtEvent e,int64_t timeout) { assert(timeout==-1);waited[wait_calls++]=e->id;if(!e->status)e->completed=1;return e->status; }
static LiteRtStatus mock_clear(LiteRtTensorBuffer b) { assert(b->event && b->event->completed);cleared[clear_calls++]=b->event->id;if(!b->clear_status)b->event=NULL;return b->clear_status; }
static LiteRtStatus mock_duplicate(LiteRtTensorBuffer b) { ++duplicate_calls;if(!duplicate_status)++b->refs;return duplicate_status; }
static void mock_destroy(LiteRtTensorBuffer b) { ++destroy_calls;--b->refs; }
static void mock_compiled_destroy(LiteRtCompiledModel m) { (void)m;++compiled_destroy_calls; }
static const char *mock_status(LiteRtStatus status) { (void)status;return "mock error"; }
static void once_noop(void) {}
static void reset(void) {
  atomic_store(&experiment_failed,false);
  submit_status=0;actual_async=1;sync_calls=async_calls=get_calls=wait_calls=clear_calls=0;
  duplicate_calls=duplicate_status=destroy_calls=compiled_destroy_calls=lock_calls=0;
  memset(waited,0,sizeof(waited));memset(cleared,0,sizeof(cleared));
  pthread_once(&wake_async_once,once_noop);
  wake_async_api.run=mock_async;wake_async_api.event=mock_event;wake_async_api.wait=mock_wait;wake_async_api.clear=mock_clear;
  lrt.LiteRtGetStatusString=mock_status;lrt.LiteRtRunCompiledModel=mock_sync;lrt.LiteRtDuplicateTensorBuffer=mock_duplicate;
  lrt.LiteRtDestroyTensorBuffer=mock_destroy;lrt.LiteRtDestroyCompiledModel=mock_compiled_destroy;
}
typedef struct { jl_litert_model *m; struct LiteRtTensorBufferT in[2],out[3];struct LiteRtEventT e[3];jl_litert_buffer *ip[2],*op[3]; } Case;
static void setup(Case *c) {
  memset(c,0,sizeof(*c));c->m=calloc(1,sizeof(*c->m));assert(c->m);c->m->experimental_tensor=true;c->m->compiled=(LiteRtCompiledModel)1;
  for(int i=0;i<2;i++){c->in[i].refs=1;c->ip[i]=(jl_litert_buffer*)&c->in[i];}
  for(int i=0;i<3;i++){c->out[i].refs=1;c->e[i].id=i;c->out[i].event=&c->e[i];c->op[i]=(jl_litert_buffer*)&c->out[i];}
}
static char *run_case(Case *c) { return jl_litert_run(c->m,c->ip,2,c->op,3); }
static void check_quarantine(Case *c) {
  assert(experiment_blocked() && c->m->quarantined && duplicate_calls==5);
  int prior_sync=sync_calls,prior_async=async_calls,prior_get=get_calls;
  char *error=run_case(c);assert(error);free(error);
  assert(sync_calls==prior_sync && async_calls==prior_async && get_calls==prior_get);
  char bytes[8]={0};error=jl_litert_buffer_write(c->ip[0],bytes,8);assert(error);free(error);
  error=jl_litert_buffer_read(c->op[0],bytes,8);assert(error);free(error);
  jl_litert_options options={0};jl_litert_model *made=(jl_litert_model*)1;
  error=jl_litert_model_create("unused",&options,&made);assert(error && made==NULL);free(error);
  for(int i=0;i<2;i++){jl_litert_buffer_release(c->ip[i]);assert(c->in[i].refs==1);}
  for(int i=0;i<3;i++){jl_litert_buffer_release(c->op[i]);assert(c->out[i].refs==1);}
  jl_litert_model_release(c->m);assert(compiled_destroy_calls==0);
  // Unit-test memory only: production intentionally never clears this latch
  // or releases the quarantined model before process termination.
  free(c->m);c->m=NULL;
}
int main(void) {
  struct rlimit limit={0,0};setrlimit(RLIMIT_CORE,&limit);
  int cases=0; Case c; char *error;
  reset();setup(&c);c.m->experimental_tensor=false;error=run_case(&c);assert(!error && sync_calls==1 && async_calls==0);jl_litert_model_release(c.m);assert(compiled_destroy_calls==1);cases++;
  reset();setup(&c);submit_status=kLiteRtStatusErrorRuntimeFailure;c.m->experimental_tensor=false;error=run_case(&c);assert(error);free(error);check_quarantine(&c);cases++;
#if JL_WAKE_ASYNC
  reset();setup(&c);error=run_case(&c);assert(!error && async_calls==1 && sync_calls==0 && wait_calls==3 && clear_calls==3 && duplicate_calls==0);for(int i=0;i<3;i++)assert(waited[i]==i && cleared[i]==i);jl_litert_model_release(c.m);cases++;
  reset();setup(&c);c.out[1].event=NULL;error=run_case(&c);assert(error && get_calls==3 && wait_calls==2 && clear_calls==2);free(error);check_quarantine(&c);cases++;
  reset();setup(&c);submit_status=kLiteRtStatusErrorRuntimeFailure;error=run_case(&c);assert(error && wait_calls==3 && clear_calls==3);free(error);check_quarantine(&c);cases++;
  reset();setup(&c);c.out[0].lookup_status=kLiteRtStatusErrorRuntimeFailure;error=run_case(&c);assert(error && get_calls==3 && wait_calls==2 && clear_calls==2);free(error);check_quarantine(&c);cases++;
  reset();setup(&c);c.e[0].status=kLiteRtStatusErrorRuntimeFailure;error=run_case(&c);assert(error && wait_calls==3 && clear_calls==2 && c.out[0].event!=NULL);free(error);check_quarantine(&c);cases++;
  reset();setup(&c);c.out[0].clear_status=kLiteRtStatusErrorRuntimeFailure;error=run_case(&c);assert(error && wait_calls==3 && clear_calls==3);free(error);check_quarantine(&c);cases++;
  reset();setup(&c);for(int i=0;i<3;i++)c.out[i].event=NULL;error=run_case(&c);assert(error && get_calls==3 && wait_calls==0);free(error);check_quarantine(&c);cases++;
  reset();setup(&c);actual_async=0;error=run_case(&c);assert(error && wait_calls==3);free(error);check_quarantine(&c);cases++;
  reset();setup(&c);wake_async_api.wait=NULL;error=run_case(&c);assert(error && async_calls==0 && get_calls==0);free(error);check_quarantine(&c);cases++;
  reset();setup(&c);submit_status=kLiteRtStatusErrorRuntimeFailure;duplicate_status=kLiteRtStatusErrorRuntimeFailure;
  pid_t child=fork();assert(child>=0);if(child==0){(void)run_case(&c);_exit(88);}int status=0;assert(waitpid(child,&status,0)==child);assert(WIFSIGNALED(status) && WTERMSIG(status)==SIGABRT);free(c.m);cases++;
#else
  reset();setup(&c);error=run_case(&c);assert(!error && sync_calls==1 && async_calls==0 && get_calls==0);jl_litert_model_release(c.m);cases++;
#endif
  printf("PASS async=%d cases=%d: completion drainage, borrowed-event ownership, fail-closed reuse and close quarantine\n",JL_WAKE_ASYNC,cases);
  return 0;
}


