"""Compare compiled LiteRT dispatch payloads without disclosing their bytes.

For two single-partition AOT models. Reports hashes, sizes, metadata and byte
span differences only. Private executable contents and weights are never copied
into the report. All model access is read-only and memory-mapped.
"""
from __future__ import annotations
import argparse, hashlib, json, mmap, pathlib
import numpy as np
from flatbuffers import flexbuffers
from ai_edge_litert import schema_py_generated as s


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(mm, offset, size):
    require(0 <= offset <= len(mm) and 0 <= size <= len(mm)-offset, 'Payload outside file')
    return hashlib.sha256(memoryview(mm)[offset:offset+size]).hexdigest()


def describe_model(mm, start=0, length=None):
    length = len(mm)-start if length is None else length
    require(length >= 8 and mm[start+4:start+8] == b'TFL3', 'Expected a LiteRT FlatBuffer')
    model=s.Model.GetRootAsModel(mm,start)
    result={'bytes':length,'buffers':[],'metadata':[],'subgraphs':[]}
    payloads=[]
    for i in range(model.BuffersLength()):
        b=model.Buffers(i)
        row={'index':i,'external_offset':int(b.Offset()),'external_bytes':int(b.Size()),'inline_bytes':b.DataLength()}
        if b.Offset() and b.Size():
            row['sha256']=digest(mm,start+b.Offset(),b.Size())
        elif b.DataLength():
            pos=b._tab.Vector(b._tab.Offset(4))
            require(start <= pos and pos+b.DataLength() <= start+length,'Inline buffer outside payload')
            row['inline_offset']=pos-start
            row['sha256']=digest(mm,pos,b.DataLength())
        result['buffers'].append(row)
    for i in range(model.MetadataLength()):
        md=model.Metadata(i)
        result['metadata'].append({'name':md.Name().decode(errors='replace'),'buffer':md.Buffer()})
    for i in range(model.SubgraphsLength()):
        g=model.Subgraphs(i)
        graph={'tensor_count':g.TensorsLength(),'inputs':[g.Inputs(j) for j in range(g.InputsLength())],
               'outputs':[g.Outputs(j) for j in range(g.OutputsLength())],'operators':[]}
        for j in range(g.OperatorsLength()):
            op=g.Operators(j);code=model.OperatorCodes(op.OpcodeIndex())
            name=code.CustomCode().decode(errors='replace') if code.CustomCode() else None
            row={'builtin_code':max(code.BuiltinCode(),code.DeprecatedBuiltinCode()),'custom_code':name,
                 'inputs':[op.Inputs(k) for k in range(op.InputsLength())],
                 'outputs':[op.Outputs(k) for k in range(op.OutputsLength())],
                 'custom_options_bytes':op.CustomOptionsLength()}
            if op.CustomOptionsLength():
                pos=op._tab.Vector(op._tab.Offset(14))
                row['custom_options_offset']=pos-start
                row['custom_options_sha256']=digest(mm,pos,op.CustomOptionsLength())
            if name=='DISPATCH_OP':
                require(0 < op.CustomOptionsLength() <= 4096,'Unexpected dispatch metadata size')
                options=flexbuffers.Loads(bytearray(op.CustomOptionsAsNumpy()))
                require(isinstance(options,dict) and 'bytecode_offset' in options and 'bytecode_size' in options,
                        'Expected public dispatch bytecode offset/size fields')
                offset=int(options['bytecode_offset']);size=int(options['bytecode_size'])
                require(0<=offset<=length and 0<=size<=length-offset,'Dispatch payload outside model')
                row['dispatch_payload']={'offset':offset,'bytes':size,'sha256':digest(mm,start+offset,size)}
                payloads.append((start+offset,size))
            graph['operators'].append(row)
        result['subgraphs'].append(graph)
    return result,payloads


def compare_regions(a,b,a_start,b_start,size,max_spans=100):
    report={'compared_bytes':size,'different_bytes':0,'different_blocks':0,'first_difference':None,
            'last_difference':None,'difference_spans':[],'span_list_truncated':False}
    for start in range(0,size,1024*1024):
        length=min(1024*1024,size-start)
        av=np.ndarray((length,),dtype=np.uint8,buffer=a,offset=a_start+start)
        bv=np.ndarray((length,),dtype=np.uint8,buffer=b,offset=b_start+start)
        different=np.flatnonzero(av!=bv)
        if len(different):
            report['different_bytes']+=len(different);report['different_blocks']+=1
            if report['first_difference'] is None:report['first_difference']=int(different[0])+start
            report['last_difference']=int(different[-1])+start
            for indices in np.split(different,np.where(np.diff(different)>1)[0]+1):
                span=[int(indices[0])+start,int(indices[-1])+start+1]
                if report['difference_spans'] and report['difference_spans'][-1][1]==span[0]:
                    report['difference_spans'][-1][1]=span[1]
                elif len(report['difference_spans'])<max_spans:report['difference_spans'].append(span)
                else:report['span_list_truncated']=True
        del av,bv,different
    return report


def compare(a_path,b_path):
    with a_path.open('rb') as af,b_path.open('rb') as bf,\
            mmap.mmap(af.fileno(),0,access=mmap.ACCESS_READ) as am,\
            mmap.mmap(bf.fileno(),0,access=mmap.ACCESS_READ) as bm:
        ar,ap=describe_model(am);br,bp=describe_model(bm)
        require(len(ap)==len(bp)==1,'Comparison requires exactly one DISPATCH_OP per model')
        result={'model_a_name':a_path.name,'model_b_name':b_path.name,'model_a':ar,'model_b':br,
                'caveat':'Equal buffers or small differences do not establish equivalent execution. Unknown custom-option fields are not interpreted.'}
        for label,mm,payload in [('nested_a',am,ap[0]),('nested_b',bm,bp[0])]:
            start,size=payload
            if size>=8 and mm[start+4:start+8]==b'TFL3':result[label]=describe_model(mm,start,size)[0]
        if ap[0][1]==bp[0][1]:
            result['payload_comparison']=compare_regions(am,bm,ap[0][0],bp[0][0],ap[0][1])
        else:
            result['payload_comparison']={'equal_size':False,'a_bytes':ap[0][1],'b_bytes':bp[0][1]}
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-a',type=pathlib.Path,required=True)
    parser.add_argument('--model-b',type=pathlib.Path,required=True)
    parser.add_argument('--output',type=pathlib.Path,required=True)
    args=parser.parse_args()
    require(not args.output.exists(),'Refusing to overwrite report')
    result=compare(args.model_a,args.model_b)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['payload_comparison'],indent=2))

if __name__=='__main__':main()
