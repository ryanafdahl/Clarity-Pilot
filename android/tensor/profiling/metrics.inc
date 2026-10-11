// Optional hardware counters for this isolated benchmark, never the app.
void jl_bench_metrics(jl_litert_model *model, int start) {
  static int active=0;
  char path[1024]; snprintf(path,sizeof(path),"%s/libLiteRt.so",runtime_dir);
  void *lib=dlopen(path,RTLD_NOW|RTLD_LOCAL);
  if(!lib){fprintf(stderr,"METRICS runtime unavailable\n");return;}
#define METRIC_FN(name) __typeof__(&name) fn_##name = (__typeof__(&name))dlsym(lib,#name); if(!fn_##name){fprintf(stderr,"METRICS missing %s\n",#name);dlclose(lib);return;}
  METRIC_FN(LiteRtCompiledModelStartMetricsCollection)
  METRIC_FN(LiteRtCompiledModelStopMetricsCollection)
  METRIC_FN(LiteRtCreateMetrics)
  METRIC_FN(LiteRtGetNumMetrics)
  METRIC_FN(LiteRtGetMetric)
  METRIC_FN(LiteRtDestroyMetrics)
#undef METRIC_FN
  if(start) {
    LiteRtStatus status=fn_LiteRtCompiledModelStartMetricsCollection(model->compiled,0);
    fprintf(stderr,"METRICS start status=%d\n",status);active=status==kLiteRtStatusOk;
  } else if(active) {
    LiteRtMetrics metrics=NULL;LiteRtStatus status=fn_LiteRtCreateMetrics(&metrics);
    if(status==kLiteRtStatusOk) {
      status=fn_LiteRtCompiledModelStopMetricsCollection(model->compiled,metrics);
      fprintf(stderr,"METRICS stop status=%d\n",status);
      int count=0;if(status==kLiteRtStatusOk)fn_LiteRtGetNumMetrics(metrics,&count);
      for(int i=0;i<count;i++) {
        LiteRtMetric metric={0};if(fn_LiteRtGetMetric(metrics,i,&metric)!=kLiteRtStatusOk)continue;
        if(metric.value.type==kLiteRtAnyTypeInt)fprintf(stderr,"METRIC %s=%lld\n",metric.name,(long long)metric.value.int_value);
        else if(metric.value.type==kLiteRtAnyTypeReal)fprintf(stderr,"METRIC %s=%.9f\n",metric.name,metric.value.real_value);
      }
      fn_LiteRtDestroyMetrics(metrics);
    }
    active=0;
  }
  dlclose(lib);
}
