"""Experimental, exact-weight MatMul-to-FC representation change.

Default is dry-run. --write creates a separate file; it never modifies source.
All existing tensors, signatures, ADDs, buffers and non-selected operations stay.
FP16 weights are transposed as uint16 bit patterns, without numeric conversion.
The extra FP16 constant and DEQUANTIZE are inserted before each selected matmul.
This is a numerical/performance hypothesis requiring reference/device validation.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, mmap, pathlib, shutil
import flatbuffers
import numpy as np
from ai_edge_litert import schema_py_generated as s


def require(condition, message):
    if not condition: raise ValueError(message)


def arr(value): return [] if value is None else [int(x) for x in value]


def code(model, op):
    c=model.operatorCodes[op.opcodeIndex]
    return max(c.builtinCode,c.deprecatedBuiltinCode)


def static(t):
    shape=arr(t.shape)
    return bool(shape) and all(x>0 for x in shape) and (t.shapeSignature is None or arr(t.shapeSignature)==shape)


def plain_float(t, dtype):
    return t.type==dtype and not t.isVariable and t.sparsity is None and static(t)


def candidates(model):
    require(len(model.subgraphs)==1,'Only a single statically shaped subgraph is supported')
    g=model.subgraphs[0]
    producers={}
    for oi,op in enumerate(g.operators):
        require(not getattr(op,'largeCustomOptionsSize',0),'External custom option relocation is unsupported')
        for output in arr(op.outputs):
            require(output not in producers,'Multiple tensor producers')
            producers[output]=(oi,op)
    plans=[]
    for oi,op in enumerate(g.operators):
        if code(model,op)!=s.BuiltinOperator.BATCH_MATMUL: continue
        inputs,outputs=arr(op.inputs),arr(op.outputs)
        if len(inputs)!=2 or len(outputs)!=1: continue
        x,rhs,out=[g.tensors[i] for i in inputs+outputs]
        options=op.builtinOptions
        if options is None or options.adjX or options.adjY or getattr(options,'asymmetricQuantizeInputs',False): continue
        if not all(plain_float(t,s.TensorType.FLOAT32) for t in (x,rhs,out)): continue
        if len(rhs.shape)!=2 or len(x.shape)<2: continue
        if inputs[1] not in producers: continue
        di,dq=producers[inputs[1]]
        if code(model,dq)!=s.BuiltinOperator.DEQUANTIZE or len(arr(dq.inputs))!=1 or arr(dq.outputs)!=[inputs[1]]: continue
        wi=int(dq.inputs[0]); w=g.tensors[wi]
        if not plain_float(w,s.TensorType.FLOAT16) or arr(w.shape)!=arr(rhs.shape): continue
        k,n=arr(w.shape)
        if int(x.shape[-1])!=k or arr(out.shape)!=arr(x.shape)[:-1]+[n]: continue
        b=model.buffers[w.buffer]
        if not b.offset or b.size!=k*n*2 or (b.data is not None and len(b.data)): continue
        if getattr(op,'intermediates',None) is not None and len(op.intermediates): continue
        if getattr(op,'mutatingVariableInputs',None) is not None and any(op.mutatingVariableInputs): continue
        plans.append({'operator_index':oi,'dequantize_index':di,'weight_tensor':wi,'rhs_tensor':inputs[1],
                      'input_tensor':inputs[0],'output_tensor':outputs[0],'source_buffer':w.buffer,
                      'source_offset':int(b.offset),'weight_bytes':int(b.size),'k':k,'n':n,
                      'input_shape':arr(x.shape),'output_shape':arr(out.shape)})
    return plans


def pack(model):
    builder=flatbuffers.Builder(1024*1024)
    root=model.Pack(builder)
    builder.Finish(root,file_identifier=b'TFL3')
    return bytes(builder.Output())


def align64(n): return (n+63)&~63


def mutate(model,plans):
    g=model.subgraphs[0]
    new_code=s.OperatorCodeT()
    new_code.builtinCode=s.BuiltinOperator.FULLY_CONNECTED
    new_code.deprecatedBuiltinCode=s.BuiltinOperator.FULLY_CONNECTED
    new_code.version=5 # keep_num_dims requires FC version 5 or newer.
    fc_code=len(model.operatorCodes)
    model.operatorCodes.append(new_code)
    selected={p['operator_index']:p for p in plans}
    result=[]
    for oi,op in enumerate(g.operators):
        if oi not in selected:
            result.append(op); continue
        plan=selected[oi]
        shape=[plan['n'],plan['k']]
        b=s.BufferT(); b.offset=1; b.size=plan['weight_bytes']
        plan['new_buffer']=len(model.buffers); model.buffers.append(b)
        w=copy.deepcopy(g.tensors[plan['weight_tensor']])
        w.shape=np.array(shape,dtype=np.int32)
        if w.shapeSignature is not None: w.shapeSignature=w.shape.copy()
        w.buffer=plan['new_buffer']; w.name=(w.name or b'weight')+b'__fc_exact_transpose'
        wt=len(g.tensors);g.tensors.append(w)
        rhs=copy.deepcopy(g.tensors[plan['rhs_tensor']])
        rhs.shape=np.array(shape,dtype=np.int32)
        if rhs.shapeSignature is not None: rhs.shapeSignature=rhs.shape.copy()
        rhs.buffer=0;rhs.name=(rhs.name or b'weight_f32')+b'__fc_exact_transpose'
        rt=len(g.tensors);g.tensors.append(rhs)
        dq=copy.deepcopy(g.operators[plan['dequantize_index']])
        dq.inputs=np.array([wt],dtype=np.int32);dq.outputs=np.array([rt],dtype=np.int32)
        result.append(dq)
        fc=copy.deepcopy(op)
        fc.opcodeIndex=fc_code
        fc.inputs=np.array([plan['input_tensor'],rt,-1],dtype=np.int32)
        fc.builtinOptionsType=s.BuiltinOptions.FullyConnectedOptions
        opts=s.FullyConnectedOptionsT()
        opts.keepNumDims=True
        opts.fusedActivationFunction=s.ActivationFunctionType.NONE
        opts.weightsFormat=s.FullyConnectedOptionsWeightsFormat.DEFAULT
        opts.asymmetricQuantizeInputs=False
        fc.builtinOptions=opts
        result.append(fc)
    g.operators=result


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def transform(source:pathlib.Path,output:pathlib.Path|None):
    require(source.is_file(),'Source model is missing')
    if output is not None: require(not output.exists(),'Refusing to overwrite output')
    with source.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mm:
        require(mm[4:8]==b'TFL3','Not a LiteRT FlatBuffer')
        model=copy.deepcopy(s.ModelT.InitFromObj(s.Model.GetRootAsModel(mm,0)))
        source_size=len(mm)
        plans=candidates(model)
        require(plans,'No eligible constant 2D RHS matmuls')
        for plan in plans: require(plan['source_offset']+plan['weight_bytes']<=source_size,'Weight exceeds source file')
        report={'source_bytes':source_size,'selected_matmuls':len(plans),'plans':plans,
                'preserves':'Original tensor IDs, signatures, buffers, ADD nodes, FP16 bits and all non-selected operations',
                'status':'dry_run_only' if output is None else 'written_unqualified',
                'warning':'Equivalent real-arithmetic representation; floating-point accumulation/kernel selection may differ. Not a qualified model.'}
        if output is None:return report
        original_tensors=len(model.subgraphs[0].tensors)
        original_buffers=len(model.buffers)
        external=[(i,int(b.offset),int(b.size)) for i,b in enumerate(model.buffers) if b.offset]
        require(external,'This variant requires external source buffers')
        old_base=min(o for _,o,_ in external)
        require(all(o+size<=source_size for _,o,size in external),'External source buffer out of bounds')
        signatures=copy.deepcopy(model.signatureDefs)
        graph_inputs=arr(model.subgraphs[0].inputs); graph_outputs=arr(model.subgraphs[0].outputs)
        mutate(model,plans)
        provisional=pack(model)
        new_base=align64(len(provisional))
        delta=new_base-old_base
        for i,offset,size in external:model.buffers[i].offset=offset+delta
        cursor=align64(source_size+delta)
        for plan in plans:
            model.buffers[plan['new_buffer']].offset=cursor
            plan['new_offset']=cursor
            cursor=align64(cursor+plan['weight_bytes'])
        header=pack(model)
        require(len(header)==len(provisional),'FlatBuffer size changed during offset relocation')
        require(arr(model.subgraphs[0].inputs)==graph_inputs and arr(model.subgraphs[0].outputs)==graph_outputs,'Graph I/O changed')
        # Original objects were neither altered nor dropped; only new objects appended.
        for i in range(original_tensors):
            original=s.Model.GetRootAsModel(mm,0).Subgraphs(0).Tensors(i)
            t=model.subgraphs[0].tensors[i]
            require(arr(t.shape)==[original.Shape(j) for j in range(original.ShapeLength())] and t.type==original.Type() and t.buffer==original.Buffer(),'Original tensor metadata changed')
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('xb') as dst:
            dst.write(header);dst.write(bytes(new_base-len(header)))
            f.seek(old_base);shutil.copyfileobj(f,dst,length=1024*1024)
            for plan in plans:
                require(dst.tell()<=plan['new_offset'],'Overlapping appended weight')
                dst.write(bytes(plan['new_offset']-dst.tell()))
                bits=np.ndarray((plan['k'],plan['n']),dtype='<u2',buffer=mm,offset=plan['source_offset'])
                # Output is [N,K]. Small column stripes bound temporary allocations.
                for col in range(0,plan['n'],128):
                    dst.write(np.ascontiguousarray(bits[:,col:col+128].T).tobytes())
                del bits
        report.update({'output_bytes':output.stat().st_size,'original_tensors':original_tensors,
                       'new_tensors':len(model.subgraphs[0].tensors),'original_buffers':original_buffers,
                       'new_buffers':len(model.buffers),'new_operators':len(model.subgraphs[0].operators)})
    report['source_sha256']=sha(source);report['output_sha256']=sha(output)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=pathlib.Path,required=True)
    p.add_argument('--output',type=pathlib.Path)
    p.add_argument('--report',type=pathlib.Path,required=True)
    p.add_argument('--write',action='store_true')
    a=p.parse_args()
    require(not a.report.exists(),'Refusing to overwrite report')
    require(a.write==bool(a.output),'--write and --output are required together')
    result=transform(a.source,a.output if a.write else None)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='plans'},indent=2))

if __name__=='__main__':main()
