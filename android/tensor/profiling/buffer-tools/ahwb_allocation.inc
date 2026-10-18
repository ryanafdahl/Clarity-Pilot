/* Native diagnostic only. Single-threaded harness; every copy and LiteRT
 * lock/unlock remains unchanged. No persistent mappings or event manipulation.
 *
 * An imported buffer uses NULL deallocator: we retain the sole allocated AHWB
 * reference ourselves until wrappers and compiled model have been destroyed.
 * This also makes failed imports unambiguous: LiteRT never owns our reference.
 */
#include <android/hardware_buffer.h>
#include <inttypes.h>
#include <limits.h>

typedef struct {
  LiteRtTensorBuffer tensor;
  AHardwareBuffer *ahwb;
} ahwb_owned;
static ahwb_owned ahwb_rows[64];
static size_t ahwb_live;

static char *ahwb_error(const char *message) {
  char *error = copy(message);
  if (!error) abort(); /* NULL must never turn allocation failure into success. */
  return error;
}
static char *ahwb_status(LiteRtStatus status, const char *name) {
  char *error = take(status, name);
  if (status != kLiteRtStatusOk && !error) abort();
  return error;
}
static int ahwb_free_slot(void) {
  for (size_t i=0;i<64;++i) if (!ahwb_rows[i].ahwb) return (int)i;
  return -1;
}
static void ahwb_release(jl_litert_buffer *opaque) {
  if (!opaque) return;
  LiteRtTensorBuffer tensor = handle(opaque);
  for (size_t i=0;i<64;++i) if (ahwb_rows[i].tensor == tensor) {
    lrt.LiteRtDestroyTensorBuffer(tensor);
    /* A compiled-model cache may still hold a duplicate wrapper reference.
     * Keep our raw AHWB alive through compiled-model destruction. */
    ahwb_rows[i].tensor = NULL;
    return;
  }
  /* This isolated harness must never receive a foreign or duplicate handle. */
  fprintf(stderr, "AHWB diagnostic release of unknown tensor\n");
  abort();
}

/* Called by the harness only after all synchronous invocations succeeded, all
 * public buffer wrappers were dropped, and jl_litert_model_release returned. */
void jl_ahwb_release_after_model(void) {
  for(size_t i=0;i<64;++i)if(ahwb_rows[i].tensor)abort();
  for(size_t i=0;i<64;++i)if(ahwb_rows[i].ahwb){
    AHardwareBuffer_release(ahwb_rows[i].ahwb);
    ahwb_rows[i]=(ahwb_owned){0};
    --ahwb_live;
  }
  if(ahwb_live)abort();
}
static char *ahwb_create(jl_litert_model *model, int output, size_t index,
                         jl_litert_buffer **out) {
  *out = NULL;
  ptrdiff_t slot_index = slot(model, output, index);
  if (slot_index < 0) return ahwb_error("no such input or output");
  const char *mode = getenv("BENCH_AHWB_USAGE");
  if (!mode || (strcmp(mode,"rarely") && strcmp(mode,"often")))
    return ahwb_error("BENCH_AHWB_USAGE must be exactly rarely or often");
  int registry_index = ahwb_free_slot();
  if (registry_index < 0) return ahwb_error("AHWB diagnostic registry full");

  LiteRtTensorBufferRequirements req = NULL; /* Borrowed from compiled model. */
  char *error = NULL;
  int count=0,num_strides=0;
  const uint32_t *strides=NULL;
  size_t size=0,alignment=0,packed=0,actual_size=0;
  LiteRtTensorBuffer tensor=NULL;
  AHardwareBuffer *ahwb=NULL,*borrowed=NULL;
  LiteRtTensorBufferType actual=kLiteRtTensorBufferTypeUnknown;
  int supported_types[64],has_ahwb=0;
  AHardwareBuffer_Desc requested={0},described={0};

#define AHWB_CHECK(name, ...) do { \
  error=ahwb_status(lrt.name(__VA_ARGS__),#name); \
  if(error)goto failed; \
} while(0)
  if(output) {
    AHWB_CHECK(LiteRtGetCompiledModelOutputBufferRequirements,model->compiled,0,index,&req);
  } else {
    AHWB_CHECK(LiteRtGetCompiledModelInputBufferRequirements,model->compiled,0,index,&req);
  }
  AHWB_CHECK(LiteRtGetNumTensorBufferRequirementsSupportedBufferTypes,req,&count);
  if(count<1||count>64){error=ahwb_error("invalid or excessive supported buffer types");goto failed;}
  for(int i=0;i<count;++i) {
    LiteRtTensorBufferType type=kLiteRtTensorBufferTypeUnknown;
    AHWB_CHECK(LiteRtGetTensorBufferRequirementsSupportedTensorBufferType,req,i,&type);
    supported_types[i]=(int)type;
    if(type==kLiteRtTensorBufferTypeAhwb)has_ahwb=1;
  }
  AHWB_CHECK(LiteRtGetTensorBufferRequirementsBufferSize,req,&size);
  AHWB_CHECK(LiteRtGetTensorBufferRequirementsStrides,req,&num_strides,&strides);
  AHWB_CHECK(LiteRtGetTensorBufferRequirementsAlignment,req,&alignment);
  /* Report requirements even if this backend is unsupported; never fallback. */
  printf("{\"diagnostic\":\"ahwb_requirements\",\"direction\":\"%s\",\"index\":%zu,"
         "\"supported_types\":[",output?"output":"input",index);
  for(int i=0;i<count;++i)printf("%s%d",i?",":"",supported_types[i]);
  printf("],\"required_bytes\":%zu,\"required_alignment\":%zu,\"num_strides\":%d}\n",
         size,alignment,num_strides);
  if(!has_ahwb){error=ahwb_error("AHWB is not a supported model buffer type");goto failed;}
  if(num_strides!=0){error=ahwb_error("AHWB diagnostic refuses strided requirements");goto failed;}
  if(!size||size>UINT32_MAX){error=ahwb_error("AHWB BLOB requirement exceeds width range");goto failed;}

  requested.width=(uint32_t)size;
  requested.height=1;
  requested.layers=1;
  requested.format=AHARDWAREBUFFER_FORMAT_BLOB;
  requested.usage=AHARDWAREBUFFER_USAGE_GPU_DATA_BUFFER |
    (!strcmp(mode,"often")
      ? AHARDWAREBUFFER_USAGE_CPU_READ_OFTEN | AHARDWAREBUFFER_USAGE_CPU_WRITE_OFTEN
      : AHARDWAREBUFFER_USAGE_CPU_READ_RARELY | AHARDWAREBUFFER_USAGE_CPU_WRITE_RARELY);
  if(AHardwareBuffer_isSupported(&requested)!=1){
    error=ahwb_error("AHWB description is unsupported");goto failed;
  }
  int allocation=AHardwareBuffer_allocate(&requested,&ahwb);
  if(allocation!=0||!ahwb){error=ahwb_error("AHWB allocation failed");goto failed;}
  AHardwareBuffer_describe(ahwb,&described);
  if(described.width!=requested.width||described.height!=1||described.layers!=1||
     described.format!=requested.format||described.usage!=requested.usage){
    error=ahwb_error("AHWB allocation description differs from request");goto failed;
  }
  /* Do not transfer ownership: failed-import destructor behavior is irrelevant. */
  AHWB_CHECK(LiteRtCreateTensorBufferFromAhwb,environment_of(model),
             &model->types[slot_index],ahwb,0,NULL,&tensor);
  if(!tensor){error=ahwb_error("AHWB import returned a null tensor");goto failed;}
  AHWB_CHECK(LiteRtGetTensorBufferType,tensor,&actual);
  AHWB_CHECK(LiteRtGetTensorBufferAhwb,tensor,&borrowed);
  AHWB_CHECK(LiteRtGetTensorBufferSize,tensor,&actual_size);
  AHWB_CHECK(LiteRtGetTensorBufferPackedSize,tensor,&packed);
  if(actual!=kLiteRtTensorBufferTypeAhwb||borrowed!=ahwb||
     actual_size<size||!packed||packed>actual_size){
    error=ahwb_error("AHWB imported type, identity, or size validation failed");goto failed;
  }
  ahwb_rows[registry_index]=(ahwb_owned){tensor,ahwb};
  ++ahwb_live;
  error=jl_litert_buffer_write((jl_litert_buffer*)tensor,NULL,0);
  if(error){
    /* Lock/unlock failure may leave mapping state uncertain. No eager release;
     * terminate this diagnostic process and let OS teardown own cleanup. */
    fprintf(stderr,"AHWB initialization failed: %s\n",error);
    free(error);
    abort();
  }
  printf("{\"diagnostic\":\"ahwb_allocation\",\"direction\":\"%s\",\"index\":%zu,"
         "\"mode\":\"%s\",\"actual_type\":%d,\"logical_bytes\":%zu,"
         "\"buffer_bytes\":%zu,\"width\":%u,\"height\":%u,\"layers\":%u,"
         "\"format\":%u,\"usage\":%" PRIu64 ",\"stride\":%u,"
         "\"ownership\":\"caller_retained_null_deallocator\"}\n",
         output?"output":"input",index,mode,(int)actual,packed,actual_size,
         described.width,described.height,described.layers,described.format,
         described.usage,described.stride);
  *out=(jl_litert_buffer*)tensor;
  return NULL;
failed:
  /* These paths precede first lock and first inference, so cleanup is bounded. */
  if(tensor)lrt.LiteRtDestroyTensorBuffer(tensor);
  if(ahwb)AHardwareBuffer_release(ahwb);
  return error ? error : ahwb_error("AHWB creation failed without an error");
#undef AHWB_CHECK
}


