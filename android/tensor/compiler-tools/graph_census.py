"""Read-only static LiteRT graph census; no inference or model changes.
Costs are logical MAC and tensor byte counts, not accelerator measurements.
"""
import argparse, collections, hashlib, json, math, mmap, pathlib
from ai_edge_litert import schema_py_generated as schema

p=argparse.ArgumentParser()
p.add_argument('--model',type=pathlib.Path,required=True)
p.add_argument('--output',type=pathlib.Path,required=True)
a=p.parse_args()
if a.output.exists(): raise SystemExit('Refusing to overwrite report')
OP={v:k for k,v in vars(schema.BuiltinOperator).items() if isinstance(v,int)}
TY={v:k for k,v in vars(schema.TensorType).items() if isinstance(v,int)}
WIDTH={'FLOAT32':4,'FLOAT16':2,'INT32':4,'UINT8':1,'INT64':8,'STRING':0,'BOOL':1,'INT16':2,'COMPLEX64':8,'INT8':1,'FLOAT64':8,'COMPLEX128':16,'UINT64':8,'UINT32':4,'UINT16':2,'INT4':0.5,'BFLOAT16':2}
def shape(t): return [int(t.Shape(i)) for i in range(t.ShapeLength())]
def numel(sh): return math.prod(sh) if all(x>=0 for x in sh) else None
with a.model.open('rb') as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mm:
 m=schema.Model.GetRootAsModel(mm,0)
 sizes=[int(m.Buffers(i).Size() or m.Buffers(i).DataLength()) for i in range(m.BuffersLength())]
 result={'source':a.model.name,'source_bytes':len(mm),'caveat':'Logical graph estimates only. Compiler fusion, tiling, compression, padding, on-chip reuse, and memory scheduling can change physical work. Tensor bytes are not DRAM traffic. MAC convention multiply-add counts as one MAC.','subgraphs':[]}
 for si in range(m.SubgraphsLength()):
  g=m.Subgraphs(si)
  ts=[g.Tensors(i) for i in range(g.TensorsLength())]
  def td(i):
   t=ts[i]; sh=shape(t); n=numel(sh); ty=TY.get(t.Type(),str(t.Type()))
   return {'id':i,'name':t.Name().decode(errors='replace') if t.Name() else '', 'shape':sh,'type':ty,'logical_bytes':int(n*WIDTH.get(ty,0)) if n is not None else None,'buffer':int(t.Buffer()),'constant_bytes':sizes[t.Buffer()]}
  tensors=[td(i) for i in range(len(ts))]
  origins={i:{t["buffer"]} for i,t in enumerate(tensors) if t["constant_bytes"]}
  kinds=collections.Counter(); bykind={}; ops=[]; usecount=collections.Counter(); constants=set(); symbolic=[]
  for oi in range(g.OperatorsLength()):
   op=g.Operators(oi); code=m.OperatorCodes(op.OpcodeIndex()); kind=OP.get(max(code.BuiltinCode(),code.DeprecatedBuiltinCode()),str(code.BuiltinCode()))
   ins=[int(op.Inputs(i)) for i in range(op.InputsLength()) if op.Inputs(i)>=0]; outs=[int(op.Outputs(i)) for i in range(op.OutputsLength()) if op.Outputs(i)>=0]
   for ti in ins: usecount[ti]+=1
   constant_ids=set().union(*(origins.get(i,set()) for i in ins))
   if ins and all(i in origins for i in ins):
    for i in outs: origins[i]=constant_ids
   constants.update(constant_ids)
   out_elements=sum(numel(tensors[i]['shape']) or 0 for i in outs)
   out_bytes=sum(tensors[i]['logical_bytes'] or 0 for i in outs)
   mac=None
   if kind=='CONV_2D' and len(ins)>1 and len(tensors[ins[1]]['shape'])==4:
    w=tensors[ins[1]]['shape']; mac=out_elements*math.prod(w[1:])
   elif kind=='DEPTHWISE_CONV_2D' and len(ins)>1 and len(tensors[ins[1]]['shape'])==4:
    w=tensors[ins[1]]['shape']; mac=out_elements*w[1]*w[2]
   elif kind=='FULLY_CONNECTED' and len(ins)>1:
    w=tensors[ins[1]]['shape']; mac=out_elements*w[-1]
   elif kind=='BATCH_MATMUL' and len(ins)>1:
    w=tensors[ins[0]]['shape']
    bo=op.BuiltinOptions(); o=schema.BatchMatMulOptions(); o.Init(bo.Bytes,bo.Pos)
    mac=out_elements*w[-2 if o.AdjX() else -1]
   row={'index':oi,'kind':kind,'input_ids':ins,'output_ids':outs,'input_shapes':[tensors[i]['shape'] for i in ins],'output_shapes':[tensors[i]['shape'] for i in outs],'constant_bytes_referenced':sum(sizes[i] for i in constant_ids),'logical_output_bytes':out_bytes,'estimated_mac':mac}
   ops.append(row); kinds[kind]+=1
   ag=bykind.setdefault(kind,{'operators':0,'estimated_mac':0,'logical_output_bytes':0,'constant_buffers':set()})
   ag['operators']+=1;ag['estimated_mac']+=mac or 0;ag['logical_output_bytes']+=out_bytes;ag['constant_buffers'].update(constant_ids)
  for v in bykind.values(): v['unique_constant_bytes']=sum(sizes[i] for i in v.pop('constant_buffers'))
  out={'index':si,'operators':len(ops),'tensors':len(tensors),'inputs':[tensors[int(g.Inputs(i))] for i in range(g.InputsLength())],'outputs':[tensors[int(g.Outputs(i))] for i in range(g.OutputsLength())], 'type_counts':dict(collections.Counter(t['type'] for t in tensors)),'by_kind':bykind,'estimated_total_mac':sum(o['estimated_mac'] or 0 for o in ops),'unique_used_constant_bytes':sum(sizes[i] for i in constants),'constant_origin_tensor_count':len(origins),'top_mac_ops':sorted([o for o in ops if o['estimated_mac'] is not None],key=lambda x:x['estimated_mac'],reverse=True)[:25],'top_constants':sorted([t for t in tensors if t['constant_bytes']],key=lambda t:t['constant_bytes'],reverse=True)[:25],'layout_ops':[o for o in ops if o['kind'] in {'TRANSPOSE','RESHAPE','CAST','CONCATENATION','SLICE','STRIDED_SLICE','PAD','PADV2','GATHER','SQUEEZE','EXPAND_DIMS'}], 'dynamic_shapes':[t for t in tensors if any(x<0 for x in t['shape'])]}
  result['subgraphs'].append(out)
 a.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'report':str(a.output),'subgraphs':[{'operators':s['operators'],'estimated_total_mac':s['estimated_total_mac'],'unique_used_constant_bytes':s['unique_used_constant_bytes'],'by_kind':s['by_kind']} for s in result['subgraphs']]},indent=2))
