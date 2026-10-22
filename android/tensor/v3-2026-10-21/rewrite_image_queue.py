"""Unqualified V3 layout experiment: preserve image history SLICE/CONCAT as native 4D.

The source remains untouched. No arithmetic, graph signature, weight bytes or
precision changes. This is unqualified until CPU and compiled-device parity pass.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,mmap,pathlib,shutil
import flatbuffers
import numpy as np
from ai_edge_litert import schema_py_generated as s

SOURCE_SHA256='a60ff14e699827da4f2416c9853f5018403d1b8b5700b7dae5fbdfba065d721a'
def need(ok,msg):
    if not ok:raise ValueError(msg)
def arr(x):return [] if x is None else [int(v) for v in x]
def sha(path):
    with pathlib.Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pack(model):
    b=flatbuffers.Builder(1024*1024);root=model.Pack(b);b.Finish(root,file_identifier=b'TFL3');return bytes(b.Output())
def align64(n):return (n+63)&~63
def code(m,op):
    c=m.operatorCodes[op.opcodeIndex];return max(c.builtinCode,c.deprecatedBuiltinCode)
def identify(m):
    need(len(m.subgraphs)==1,'Expected single subgraph')
    g=m.subgraphs[0];names={t.name.decode():i for i,t in enumerate(g.tensors)}
    def named(n,shape,ty=s.TensorType.UINT8):
        need(n in names,f'Missing tensor {n}');i=names[n];t=g.tensors[i]
        need(arr(t.shape)==shape and t.type==ty and not t.isVariable and t.sparsity is None,f'Unexpected tensor {n}')
        need(t.shapeSignature is None or arr(t.shapeSignature)==shape,f'Dynamic tensor {n}')
        return i
    ids={
      'state':named('state_img_q',[2,30,128,256]),
      'frame':named('new_img',[2,6,128,256]),
      'old_view':named('slice_1__view',[2,5,196608]),
      'old_tail':named('slice_1__sliced',[2,4,196608]),
      'old_frame_view':named('next_state_img_q__view1',[2,1,196608]),
      'old_joined':named('next_state_img_q__joined',[2,5,196608]),
      'out':named('next_state_img_q',[2,30,128,256]),
    }
    prod={};readers={}
    for j,o in enumerate(g.operators):
        need(not getattr(o,'largeCustomOptionsSize',0),'External custom option relocation unsupported')
        for v in arr(o.outputs):need(v not in prod,'Multiple producers');prod[v]=j
        for v in arr(o.inputs):readers.setdefault(v,[]).append(j)
    sl=prod[ids['old_tail']];co=prod[ids['old_joined']];rv=prod[ids['old_view']];rf=prod[ids['old_frame_view']];ro=prod[ids['out']]
    so=g.operators[sl];jo=g.operators[co];vo=g.operators[rv];fo=g.operators[rf];oo=g.operators[ro]
    need(code(m,so)==s.BuiltinOperator.SLICE and arr(so.outputs)==[ids['old_tail']] and len(so.inputs)==3 and so.inputs[0]==ids['old_view'],'Unexpected history slice')
    need(code(m,jo)==s.BuiltinOperator.CONCATENATION and arr(jo.inputs)==[ids['old_tail'],ids['old_frame_view']] and arr(jo.outputs)==[ids['old_joined']] and jo.builtinOptions.axis==1 and jo.builtinOptions.fusedActivationFunction==0,'Unexpected history concat')
    for op,inp,out in [(vo,ids['state'],ids['old_view']),(fo,ids['frame'],ids['old_frame_view']),(oo,ids['old_joined'],ids['out'])]:
        need(code(m,op)==s.BuiltinOperator.RESHAPE and op.inputs[0]==inp and arr(op.outputs)==[out],'Unexpected queue view')
    need(readers[ids['old_tail']]==[co],'History tail has additional consumers')
    need(ids['old_tail'] not in arr(g.inputs)+arr(g.outputs),'History tail exposed in graph signature')
    def ints(tid):
        t=g.tensors[tid];b=m.buffers[t.buffer]
        need(t.type==s.TensorType.INT32 and not b.offset and b.data is not None,'Expected inline INT32 constant')
        return np.asarray(b.data,dtype=np.uint8).tobytes()
    need(list(np.frombuffer(ints(int(so.inputs[1])),dtype='<i4'))==[0,1,0],'Unexpected slice begin')
    need(list(np.frombuffer(ints(int(so.inputs[2])),dtype='<i4'))==[2,4,196608],'Unexpected slice size')
    need(list(np.frombuffer(ints(int(vo.inputs[1])),dtype='<i4'))==[2,5,196608],'Unexpected preserved 3D reshape')
    need(ids['state'] in arr(g.inputs) and ids['frame'] in arr(g.inputs) and ids['out'] in arr(g.outputs),'Unexpected graph edge ids')
    return ids,{'slice_index':sl,'concat_index':co,'view_index':rv,'frame_view_index':rf,'output_view_index':ro,'joined_consumers':readers[ids['old_joined']],'tail_consumers':readers[ids['old_tail']]}

def mutate(m,ids,plan):
    g=m.subgraphs[0]
    def tensor_like(base,name,shape,buffer=0):
        t=copy.deepcopy(g.tensors[base]);t.name=name.encode();t.shape=np.asarray(shape,np.int32);t.buffer=buffer
        if t.shapeSignature is not None:t.shapeSignature=t.shape.copy()
        tid=len(g.tensors);g.tensors.append(t);return tid
    def const(name,values):
        b=s.BufferT();b.data=np.frombuffer(np.asarray(values,dtype='<i4').tobytes(),dtype=np.uint8).copy();bi=len(m.buffers);m.buffers.append(b)
        t=s.TensorT();t.name=name.encode();t.shape=np.asarray([len(values)],np.int32);t.type=s.TensorType.INT32;t.buffer=bi
        ti=len(g.tensors);g.tensors.append(t);return ti
    tail=tensor_like(ids['old_tail'],'v3_image_tail_4d',[2,24,128,256])
    joined=tensor_like(ids['old_joined'],'v3_image_joined_4d',[2,30,128,256])
    begin=const('v3_image_tail_4d_begin',[0,6,0,0]);size=const('v3_image_tail_4d_size',[2,24,128,256])
    so=copy.deepcopy(g.operators[plan['slice_index']]);so.inputs=np.asarray([ids['state'],begin,size],np.int32);so.outputs=np.asarray([tail],np.int32)
    jo=copy.deepcopy(g.operators[plan['concat_index']]);jo.inputs=np.asarray([tail,ids['frame']],np.int32);jo.outputs=np.asarray([joined],np.int32)
    # Every existing reader of old_joined keeps exactly its original rank3
    # tensor and receives the same bytes through this explicitly inserted view.
    view=copy.deepcopy(g.operators[plan['view_index']]);view.inputs=np.asarray([joined,int(view.inputs[1])],np.int32);view.outputs=np.asarray([ids['old_joined']],np.int32)
    ops=[]
    for j,o in enumerate(g.operators):
        if j==plan['slice_index']:ops.append(so)
        elif j==plan['concat_index']:ops.extend([jo,view])
        else:ops.append(o)
    g.operators=ops
    return {'tail':tail,'joined':joined,'begin':begin,'size':size}

def transform(source,output):
    need(sha(source)==SOURCE_SHA256,'Source is not the verified original V3 conversion')
    if output:need(not output.exists(),'Refusing to overwrite output')
    with source.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mm:
        need(mm[4:8]==b'TFL3','Not a TFLite FlatBuffer')
        m=copy.deepcopy(s.ModelT.InitFromObj(s.Model.GetRootAsModel(mm,0)))
        ids,plan=identify(m)
        report={'source_sha256':SOURCE_SHA256,'source_bytes':len(mm),'plan':plan,'tensor_ids':ids,'status':'dry-run' if output is None else 'written-unqualified','rewrite':'UINT8 SLICE [2,30,128,256] begin[0,6,0,0] size[2,24,128,256], then CONCAT axis1 with new_img [2,6,128,256]; restore original rank3 joined view for existing consumers','preserves':'All original tensor metadata and signatures, every other operation, original buffers and exact weight bytes, graph I/O and precision'}
        if output is None:return report
        g=m.subgraphs[0];old_nt=len(g.tensors);old_nb=len(m.buffers);old_ops=list(g.operators);old_in=arr(g.inputs);old_out=arr(g.outputs)
        external=[(i,int(b.offset),int(b.size)) for i,b in enumerate(m.buffers) if b.offset]
        need(external,'Expected external weights');base=min(o for _,o,_ in external)
        need(all(size>0 and o+size<=len(mm) for _,o,size in external),'External buffer outside source')
        added=mutate(m,ids,plan)
        provisional=pack(m);newbase=align64(len(provisional));delta=newbase-base
        for i,o,size in external:m.buffers[i].offset=o+delta
        header=pack(m);need(len(header)==len(provisional),'Relocation changed header size')
        need(arr(g.inputs)==old_in and arr(g.outputs)==old_out,'Graph I/O changed')
        for i in range(old_nt):
            t=s.Model.GetRootAsModel(mm,0).Subgraphs(0).Tensors(i);new=g.tensors[i]
            need(arr(new.shape)==[t.Shape(j) for j in range(t.ShapeLength())] and new.type==t.Type() and new.buffer==t.Buffer() and new.name==t.Name(),'Original tensor changed')
        # Each unselected operator object is passed through, unchanged and in order.
        remaining=[o for j,o in enumerate(old_ops) if j not in (plan['slice_index'],plan['concat_index'])]
        after=[o for j,o in enumerate(g.operators) if j not in (plan['slice_index'],plan['concat_index'],plan['concat_index']+1)]
        need(len(remaining)==len(after) and all(a is b for a,b in zip(remaining,after)),'An unrelated operator changed')
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('xb') as dst:
            dst.write(header);dst.write(bytes(newbase-len(header)));f.seek(base);shutil.copyfileobj(f,dst,length=1024*1024)
        report.update(output_sha256=sha(output),output_bytes=output.stat().st_size,added_tensor_ids=added,original_tensors=old_nt,new_tensors=len(g.tensors),original_buffers=old_nb,new_buffers=len(m.buffers),operators=len(g.operators),external_weight_offset_delta=delta)
        # Read-back verifies each external buffer's content, not only offsets.
        with output.open('rb') as of,mmap.mmap(of.fileno(),0,access=mmap.ACCESS_READ) as om:
            new=s.Model.GetRootAsModel(om,0)
            for i,o,size in external:
                b=new.Buffers(i);need(b.Size()==size,'External weight size changed')
                need(hashlib.sha256(memoryview(mm)[o:o+size]).digest()==hashlib.sha256(memoryview(om)[b.Offset():b.Offset()+size]).digest(),'External weight bytes changed')
        report['all_external_weight_buffers_exact']=True
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
    need(not a.report.exists(),'Refusing to overwrite report')
    result=transform(a.source,a.output);a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
