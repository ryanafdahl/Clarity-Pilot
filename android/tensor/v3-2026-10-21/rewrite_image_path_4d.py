"""Private V3 full image-path 4D layout experiment; original weights stay exact."""
from __future__ import annotations
import argparse,copy,hashlib,json,mmap,pathlib,shutil
import numpy as np
from ai_edge_litert import schema_py_generated as s
import rewrite_image_queue as q
need,arr,sha,pack,align64,code=q.need,q.arr,q.sha,q.pack,q.align64,q.code

def identify(m):
    ids,plan=q.identify(m);g=m.subgraphs[0]
    names={t.name.decode():i for i,t in enumerate(g.tensors)}
    need('cat_2' in names,'Missing cat_2');cat=names['cat_2']
    need(arr(g.tensors[cat].shape)==[1,24,128,256] and g.tensors[cat].type==s.TensorType.UINT8,'Unexpected vision tensor')
    producers={int(v):i for i,o in enumerate(g.operators) for v in o.outputs};readers={}
    for i,o in enumerate(g.operators):
        for v in arr(o.inputs):readers.setdefault(v,[]).append(i)
    ci=producers[cat];co=g.operators[ci]
    need(code(m,co)==s.BuiltinOperator.CONCATENATION and arr(co.outputs)==[cat] and co.builtinOptions.axis==1 and co.builtinOptions.fusedActivationFunction==0,'Unexpected vision concat')
    need(arr(co.inputs)==[names['_unsafe_view'],names['_unsafe_view_1']],'Unexpected camera order')
    closure=set()
    def visit(t):
        if t==ids['old_joined']:return
        if t not in producers:
            need(g.tensors[t].buffer!=0,'Nonconstant extra vision input');return
        oi=producers[t]
        if oi in closure:return
        closure.add(oi)
        for i in arr(g.operators[oi].inputs):visit(i)
    for i in arr(co.inputs):visit(i)
    need(closure==set(range(427,437)),'Unexpected image-gather chain')
    expected={427:s.BuiltinOperator.RESHAPE,428:s.BuiltinOperator.SLICE,429:s.BuiltinOperator.RESHAPE,430:s.BuiltinOperator.STRIDED_SLICE,431:s.BuiltinOperator.RESHAPE,432:s.BuiltinOperator.RESHAPE,433:s.BuiltinOperator.SLICE,434:s.BuiltinOperator.RESHAPE,435:s.BuiltinOperator.STRIDED_SLICE,436:s.BuiltinOperator.RESHAPE}
    for oi,want in expected.items():need(code(m,g.operators[oi])==want,'Unexpected image-gather operator')
    def ints(tid):
        t=g.tensors[int(tid)];b=m.buffers[t.buffer]
        need(t.type==s.TensorType.INT32 and not b.offset and b.data is not None,'Expected inline shape constant')
        return list(np.frombuffer(np.asarray(b.data,np.uint8).tobytes(),dtype='<i4'))
    for oi,batch in [(428,0),(433,1)]:
        op=g.operators[oi];need(ints(op.inputs[1])==[batch,0] and ints(op.inputs[2])==[1,983040],'Unexpected camera slice')
    for oi in [430,435]:
        op=g.operators[oi];need(ints(op.inputs[1])==[0,0,0,0] and ints(op.inputs[2])==[5,6,128,256] and ints(op.inputs[3])==[4,1,1,1],'Unexpected temporal stride')
        opt=op.builtinOptions
        need(all(not getattr(opt,k) for k in ['beginMask','endMask','ellipsisMask','newAxisMask','shrinkAxisMask','offset']),'Unexpected strided-slice options')
    for oi in closure:
        for t in arr(g.operators[oi].outputs):
            need(set(readers.get(t,[]))<=closure|{ci},f'Additional consumer of image-gather tensor {t}')
            need(t not in arr(g.inputs)+arr(g.outputs),'Image gather intermediate is graph edge')
    ids['vision']=cat;plan['vision_concat_index']=ci;plan['vision_removed_operators']=sorted(closure)
    return ids,plan

def mutate(m,ids,plan):
    g=m.subgraphs[0];original=list(g.operators)
    removed={id(original[i]) for i in plan['vision_removed_operators']}
    vision_original=original[plan['vision_concat_index']]
    added=q.mutate(m,ids,plan)
    slice_template=original[plan['slice_index']]
    def tensor(name,shape,ty=s.TensorType.UINT8,values=None):
        t=s.TensorT();t.name=name.encode();t.type=ty;t.shape=np.asarray(shape,np.int32)
        if values is not None:
            b=s.BufferT();b.data=np.frombuffer(np.asarray(values,dtype='<i4').tobytes(),dtype=np.uint8).copy();t.buffer=len(m.buffers);m.buffers.append(b)
        ti=len(g.tensors);g.tensors.append(t);return ti
    size=tensor('v3_image_frame_size_4d',[4],s.TensorType.INT32,[1,6,128,256])
    fresh=[];tids=[]
    for k,(camera,channel) in enumerate([(0,0),(0,24),(1,0),(1,24)]):
        begin=tensor(f'v3_image_frame_{k}_begin_4d',[4],s.TensorType.INT32,[camera,channel,0,0])
        out=tensor(f'v3_image_frame_{k}_4d',[1,6,128,256]);tids.append(out)
        op=copy.deepcopy(slice_template);op.inputs=np.asarray([added['joined'],begin,size],np.int32);op.outputs=np.asarray([out],np.int32);fresh.append(op)
    co=copy.deepcopy(vision_original);co.inputs=np.asarray(tids,np.int32);co.outputs=np.asarray([ids['vision']],np.int32);fresh.append(co)
    new=[]
    for op in g.operators:
        if id(op) in removed:continue
        if op is vision_original:new.extend(fresh)
        else:new.append(op)
    g.operators=new;added['vision_frames']=tids
    return added

def transform(source,output):
    need(sha(source)==q.SOURCE_SHA256,'Not the verified original V3 conversion')
    if output:need(not output.exists(),'Refusing to overwrite output')
    with source.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mm:
        need(mm[4:8]==b'TFL3','Not a TFLite model');m=copy.deepcopy(s.ModelT.InitFromObj(s.Model.GetRootAsModel(mm,0)))
        ids,plan=identify(m)
        report={'source_sha256':q.SOURCE_SHA256,'source_bytes':len(mm),'plan':plan,'tensor_ids':ids,'status':'dry-run' if output is None else 'written-unqualified','rewrite':'4D image queue slice+concat; 4D ordinary slices [1,6,128,256] from updated queue at camera/channel [0,0],[0,24],[1,0],[1,24], concat axis1 into original cat_2. All graph I/O, tensor metadata and exact weight bytes preserved.'}
        if output is None:return report
        g=m.subgraphs[0];old_nt=len(g.tensors);old_nb=len(m.buffers);old_ops=list(g.operators);old_in=arr(g.inputs);old_out=arr(g.outputs)
        external=[(i,int(b.offset),int(b.size)) for i,b in enumerate(m.buffers) if b.offset]
        need(external,'Expected external weights');base=min(o for _,o,_ in external)
        need(all(size>0 and o+size<=len(mm) for _,o,size in external),'External buffer outside source')
        selected=set(plan['vision_removed_operators'])|{plan['slice_index'],plan['concat_index'],plan['vision_concat_index']}
        remaining=[o for i,o in enumerate(old_ops) if i not in selected]
        added=mutate(m,ids,plan)
        original_ids={id(o) for o in old_ops};after=[o for o in g.operators if id(o) in original_ids]
        need(len(remaining)==len(after) and all(a is b for a,b in zip(remaining,after)),'Unrelated operation changed')
        provisional=pack(m);newbase=align64(len(provisional));delta=newbase-base
        for i,o,size in external:m.buffers[i].offset=o+delta
        header=pack(m);need(len(header)==len(provisional),'Relocation changed header size')
        need(arr(g.inputs)==old_in and arr(g.outputs)==old_out,'Graph edges changed')
        for i in range(old_nt):
            t=s.Model.GetRootAsModel(mm,0).Subgraphs(0).Tensors(i);v=g.tensors[i]
            need(arr(v.shape)==[t.Shape(j) for j in range(t.ShapeLength())] and v.type==t.Type() and v.buffer==t.Buffer() and v.name==t.Name(),'Original tensor changed')
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('xb') as dst:
            dst.write(header);dst.write(bytes(newbase-len(header)));f.seek(base);shutil.copyfileobj(f,dst,length=1024*1024)
        with output.open('rb') as of,mmap.mmap(of.fileno(),0,access=mmap.ACCESS_READ) as om:
            new=s.Model.GetRootAsModel(om,0)
            for i,o,size in external:
                b=new.Buffers(i);need(b.Size()==size,'Weight size changed')
                need(hashlib.sha256(memoryview(mm)[o:o+size]).digest()==hashlib.sha256(memoryview(om)[b.Offset():b.Offset()+size]).digest(),'Weight bytes changed')
        report.update(output_sha256=sha(output),output_bytes=output.stat().st_size,added_tensor_ids=added,original_tensors=old_nt,new_tensors=len(g.tensors),original_buffers=old_nb,new_buffers=len(m.buffers),operators=len(g.operators),external_weight_offset_delta=delta,all_external_weight_buffers_exact=True)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args();need(not a.report.exists(),'Refusing to overwrite report')
    result=transform(a.source,a.output);a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
