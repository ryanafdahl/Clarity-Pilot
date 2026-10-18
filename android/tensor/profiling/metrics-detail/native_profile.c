#define _GNU_SOURCE
#include "jl_litert.h"
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <sys/resource.h>
#include <unistd.h>

int jl_bench_mode = 5;
int jl_bench_metrics_detail = 0;
extern void jl_bench_metrics(jl_litert_model *model, int start);
static uint64_t now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (uint64_t)t.tv_sec*1000000000ULL+t.tv_nsec; }
static void check(char *error) { if(error) { fprintf(stderr,"%s\n",error); jl_litert_free(error); exit(2); } }
static uint32_t random_state=17;
static uint32_t random_value(void) { random_state^=random_state<<13;random_state^=random_state>>17;random_state^=random_state<<5;return random_state; }
static size_t element_size(int type) {
  switch(type) { case 1: case 6:return 4;case 2:case 3:case 9:return 1;case 4:case 5:case 10:return 2;case 7:case 11:return 8;default:fprintf(stderr,"unsupported type %d\n",type);exit(2); }
}
typedef struct { jl_litert_buffer *device; void *host; size_t bytes; int type; char name[128]; } tensor;
static tensor make_tensor(jl_litert_model *model, int output, size_t i) {
  tensor t={0}; int64_t dims[16];size_t rank=0,n=1;
  check(jl_litert_model_io_info(model,output,i,t.name,sizeof(t.name),&t.type,dims,16,&rank));
  if(rank>16)exit(2);
  for(size_t j=0;j<rank;j++){if(dims[j]<=0||n>SIZE_MAX/(size_t)dims[j])exit(2);n*=dims[j];}
  if(n>SIZE_MAX/element_size(t.type))exit(2);
  t.bytes=n*element_size(t.type);
  if(posix_memalign(&t.host,64,t.bytes))exit(2);
  memset(t.host,0,t.bytes);
  if(!output) {
    if(t.type==2)for(size_t j=0;j<n;j++)((uint8_t*)t.host)[j]=random_value()%256;
    if(t.type==1)for(size_t j=0;j<n;j++)((float*)t.host)[j]=((int)(random_value()%201)-100)*0.0001f;
    if(t.type==10)for(size_t j=0;j<n;j++)((_Float16*)t.host)[j]=(_Float16)(((int)(random_value()%201)-100)*0.0001f);
  }
  check(jl_litert_buffer_create(model,output,i,&t.device));
  if(!output)check(jl_litert_buffer_write(t.device,t.host,t.bytes));
  printf("{\"tensor\":\"%s\",\"output\":%d,\"bytes\":%zu,\"type\":%d}\n",t.name,output,t.bytes,t.type);
  return t;
}
int main(int argc,char **argv) {
  const char *metrics_detail = getenv("BENCH_METRICS_DETAIL");
  if (metrics_detail && strcmp(metrics_detail,"0") && strcmp(metrics_detail,"1")) {
    fprintf(stderr,"BENCH_METRICS_DETAIL must be exactly 0 or 1\n");
    return 2;
  }
  jl_bench_metrics_detail = metrics_detail && !strcmp(metrics_detail,"1");
  fprintf(stderr,"METRICS requested detail_level=%d (vendor-dependent)\n",jl_bench_metrics_detail);

  if(argc!=8){fprintf(stderr,"usage: bench runtime model mode frames period_us output_dir copy_inputs\n");return 2;}
  jl_bench_mode=atoi(argv[3]);int frames=atoi(argv[4]),period=atoi(argv[5]),copy_inputs=atoi(argv[7]);
  if(jl_bench_mode<3||jl_bench_mode>5||frames<10||frames>12000||period<0||period>1000000||(copy_inputs!=0&&copy_inputs!=1))return 2;
  setvbuf(stdout,NULL,_IOLBF,0);
  const char *pid_path=getenv("BENCH_PID_FILE");
  if(pid_path){FILE *pid_file=fopen(pid_path,"w");if(!pid_file)return 2;fprintf(pid_file,"%d\n",getpid());fclose(pid_file);}
  check(jl_litert_open(argv[1]));
  jl_litert_options options={.npu=1};jl_litert_model *model=NULL;
  uint64_t load=now();check(jl_litert_model_create(argv[2],&options,&model));
  int full=0,hardware=0;check(jl_litert_model_fully_accelerated(model,&full));check(jl_litert_model_input_hardware(model,0,&hardware));
  if(!full||hardware!=JL_LITERT_NPU){fprintf(stderr,"Refusing non-NPU or partial execution\n");return 2;}
  printf("{\"mode\":%d,\"frames\":%d,\"period_us\":%d,\"copy_inputs\":%d,\"fully_accelerated\":%d,\"hardware\":%d,\"load_ms\":%.6f}\n",jl_bench_mode,frames,period,copy_inputs,full,hardware,(now()-load)/1e6);
  size_t ni=jl_litert_model_io_count(model,0),no=jl_litert_model_io_count(model,1);
  if(ni>32||no>32)return 2;
  tensor inputs[32],outputs[32];jl_litert_buffer *in[32],*out[32];
  for(size_t i=0;i<ni;i++){inputs[i]=make_tensor(model,0,i);in[i]=inputs[i].device;}
  for(size_t i=0;i<no;i++){outputs[i]=make_tensor(model,1,i);out[i]=outputs[i].device;}
  uint64_t due=now();
  const char *priority=getenv("BENCH_NICE");
  if(priority) {
    int target=atoi(priority);
    if(target < -10 || target > 0)return 2;
    int status=setpriority(PRIO_PROCESS,0,target),error=errno;
    fprintf(stderr,"PRIORITY target=%d status=%d errno=%d actual=%d\n",target,status,status?error:0,getpriority(PRIO_PROCESS,0));
    if(status)return 5;
  }
  struct timespec boot; uint64_t mono=now(); clock_gettime(CLOCK_BOOTTIME,&boot);
  printf("{\"pid\":%d,\"mono_ns\":%llu,\"boot_ns\":%llu}\n",getpid(),(unsigned long long)mono,(unsigned long long)boot.tv_sec*1000000000ULL+boot.tv_nsec);
  for(int frame=-20;frame<frames;frame++) {
    if(frame==0 && getenv("BENCH_METRICS"))jl_bench_metrics(model,1);
    if(period){struct timespec t={.tv_sec=due/1000000000ULL,.tv_nsec=due%1000000000ULL};while(clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&t,NULL)==EINTR){}}
    struct rusage before,after;getrusage(RUSAGE_THREAD,&before);
    uint64_t start=now(),cpu0=jl_litert_thread_cpu_ns();
    if(copy_inputs)for(size_t i=0;i<ni;i++)check(jl_litert_buffer_write(in[i],inputs[i].host,inputs[i].bytes));
    uint64_t copied=now(),cpu1=jl_litert_thread_cpu_ns();
    check(jl_litert_run(model,in,ni,out,no));
    uint64_t invoked=now(),cpu2=jl_litert_thread_cpu_ns();
    for(size_t i=0;i<no;i++)check(jl_litert_buffer_read(out[i],outputs[i].host,outputs[i].bytes));
    uint64_t finish=now(),cpu3=jl_litert_thread_cpu_ns();getrusage(RUSAGE_THREAD,&after);
    for(size_t i=0;i<no;i++) {
      if(outputs[i].type==1)for(size_t j=0;j<outputs[i].bytes/4;j++)if(!isfinite(((float*)outputs[i].host)[j]))return 3;
      if(outputs[i].type==10)for(size_t j=0;j<outputs[i].bytes/2;j++)if(!isfinite((float)((_Float16*)outputs[i].host)[j]))return 3;
    }
    printf("{\"frame\":%d,\"start_ns\":%llu,\"input_ms\":%.6f,\"invoke_ms\":%.6f,\"output_ms\":%.6f,\"total_ms\":%.6f,\"input_cpu_ms\":%.6f,\"invoke_cpu_ms\":%.6f,\"output_cpu_ms\":%.6f,\"voluntary_switches\":%ld,\"involuntary_switches\":%ld,\"minor_faults\":%ld}\n",frame,(unsigned long long)start,(copied-start)/1e6,(invoked-copied)/1e6,(finish-invoked)/1e6,(finish-start)/1e6,(cpu1-cpu0)/1e6,(cpu2-cpu1)/1e6,(cpu3-cpu2)/1e6,after.ru_nvcsw-before.ru_nvcsw,after.ru_nivcsw-before.ru_nivcsw,after.ru_minflt-before.ru_minflt);
    due=now(); if(period)due=start+(uint64_t)period*1000;
  }
  if(getenv("BENCH_METRICS"))jl_bench_metrics(model,0);
  for(size_t i=0;i<no;i++) {
    char path[512];snprintf(path,sizeof(path),"%s/output-%zu.bin",argv[6],i);FILE *f=fopen(path,"wb");if(!f)return 4;
    if(fwrite(outputs[i].host,1,outputs[i].bytes,f)!=outputs[i].bytes)return 4;fclose(f);
  }
  for(size_t i=0;i<ni;i++){jl_litert_buffer_release(in[i]);free(inputs[i].host);}
  for(size_t i=0;i<no;i++){jl_litert_buffer_release(out[i]);free(outputs[i].host);}
  jl_litert_model_release(model);return 0;
}
