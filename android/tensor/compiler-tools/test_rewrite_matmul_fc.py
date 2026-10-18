"""Tiny CPU semantics/serialization tests; never load the driving model or phone."""
import copy, pathlib, tempfile, unittest
import numpy as np
from ai_edge_litert import schema_py_generated as s
from ai_edge_litert.interpreter import Interpreter,OpResolverType
from rewrite_matmul_fc import pack,align64,transform,candidates,sha


def tensor(name,shape,dtype,buffer=0):
    t=s.TensorT();t.name=name.encode();t.shape=np.array(shape,dtype=np.int32)
    t.type=dtype;t.buffer=buffer;t.hasRank=True
    return t


def opcode(builtin,version=1):
    c=s.OperatorCodeT();c.builtinCode=builtin;c.deprecatedBuiltinCode=min(builtin,127);c.version=version
    return c


def operator(ci,inputs,outputs,option_type,options):
    o=s.OperatorT();o.opcodeIndex=ci;o.inputs=np.array(inputs,dtype=np.int32);o.outputs=np.array(outputs,dtype=np.int32)
    o.builtinOptionsType=option_type;o.builtinOptions=options
    return o


def make_model(path,shape,k,n,external_bias=False):
    rng=np.random.default_rng(772)
    weights=rng.uniform(-0.5,0.5,(k,n)).astype('<f2')
    weights[0,0]=np.float16(-0.0)
    bias=rng.uniform(-0.25,0.25,n).astype('<f4')
    model=s.ModelT();model.version=3;model.description=b'constant matmul semantics fixture'
    model.operatorCodes=[opcode(s.BuiltinOperator.DEQUANTIZE,2),opcode(s.BuiltinOperator.BATCH_MATMUL),opcode(s.BuiltinOperator.ADD)]
    b0=s.BufferT();b1=s.BufferT();b1.offset=1;b1.size=weights.nbytes
    b2=s.BufferT()
    if external_bias:b2.offset=1;b2.size=bias.nbytes
    else:b2.data=np.frombuffer(bias.tobytes(),dtype=np.uint8).copy()
    model.buffers=[b0,b1,b2]
    g=s.SubGraphT();g.name=b'main';g.inputs=np.array([0],dtype=np.int32);g.outputs=np.array([5],dtype=np.int32)
    outshape=shape[:-1]+[n]
    g.tensors=[tensor('x',shape,s.TensorType.FLOAT32),tensor('w16',[k,n],s.TensorType.FLOAT16,1),tensor('w32',[k,n],s.TensorType.FLOAT32),tensor('matmul',outshape,s.TensorType.FLOAT32),tensor('bias',[n],s.TensorType.FLOAT32,2),tensor('y',outshape,s.TensorType.FLOAT32)]
    bm=s.BatchMatMulOptionsT();bm.adjX=False;bm.adjY=False;bm.asymmetricQuantizeInputs=False
    add=s.AddOptionsT();add.fusedActivationFunction=s.ActivationFunctionType.NONE
    g.operators=[operator(0,[1],[2],s.BuiltinOptions.DequantizeOptions,s.DequantizeOptionsT()),operator(1,[0,2],[3],s.BuiltinOptions.BatchMatMulOptions,bm),operator(2,[3,4],[5],s.BuiltinOptions.AddOptions,add)]
    model.subgraphs=[g]
    sig=s.SignatureDefT();sig.signatureKey=b'serving_default';sig.subgraphIndex=0
    tin=s.TensorMapT();tin.name=b'camera';tin.tensorIndex=0
    tout=s.TensorMapT();tout.name=b'predictions';tout.tensorIndex=5
    sig.inputs=[tin];sig.outputs=[tout];model.signatureDefs=[sig]
    header=pack(model);base=align64(len(header));b1.offset=base
    if external_bias:b2.offset=align64(base+weights.nbytes)
    final=pack(model);assert len(final)==len(header)
    contents=final+bytes(base-len(final))+weights.tobytes()
    if external_bias:contents+=bytes(b2.offset-len(contents))+bias.tobytes()
    path.write_bytes(contents)
    return model,weights,bias


def run(path,x):
    i=Interpreter(model_path=str(path),experimental_op_resolver_type=OpResolverType.BUILTIN_REF,num_threads=1)
    i.allocate_tensors();i.set_tensor(i.get_input_details()[0]['index'],x);i.invoke()
    return i.get_tensor(i.get_output_details()[0]['index'])


class Semantics(unittest.TestCase):
    def test_rank_shapes_weight_bits_signatures_and_add(self):
        for shape,k,n in [([3,8],8,7),([1,5,8],8,7),([1,2,3,16],16,11)]:
            with self.subTest(shape=shape),tempfile.TemporaryDirectory() as d:
                original=pathlib.Path(d)/'original.tflite';candidate=pathlib.Path(d)/'fc.tflite'
                _,w,b=make_model(original,shape,k,n);before=sha(original)
                report=transform(original,candidate)
                self.assertEqual(report['selected_matmuls'],1);self.assertEqual(sha(original),before)
                ob=s.Model.GetRootAsModel(original.read_bytes(),0);cb=s.Model.GetRootAsModel(candidate.read_bytes(),0)
                self.assertEqual(cb.SignatureDefs(0).SignatureKey(),ob.SignatureDefs(0).SignatureKey())
                self.assertEqual(cb.SignatureDefs(0).Inputs(0).TensorIndex(),0)
                self.assertEqual(cb.SignatureDefs(0).Outputs(0).TensorIndex(),5)
                self.assertEqual(cb.Subgraphs(0).OperatorsLength(),ob.Subgraphs(0).OperatorsLength()+1)
                add=cb.Subgraphs(0).Operators(cb.Subgraphs(0).OperatorsLength()-1)
                self.assertEqual(add.OpcodeIndex(),2);self.assertEqual([add.Inputs(i) for i in range(add.InputsLength())],[3,4])
                plan=report['plans'][0]
                candidate_bits=np.frombuffer(candidate.read_bytes(),dtype='<u2',count=k*n,offset=plan['new_offset']).reshape(n,k)
                np.testing.assert_array_equal(candidate_bits,w.view('<u2').T)
                rng=np.random.default_rng(517)
                for frame in range(32):
                    x=rng.uniform(-1,1,shape).astype(np.float32)
                    expected=np.matmul(x,w.astype(np.float32))+b
                    ref=run(original,x);fc=run(candidate,x)
                    np.testing.assert_allclose(ref,expected,rtol=1e-6,atol=1e-6)
                    np.testing.assert_allclose(fc,ref,rtol=1e-6,atol=1e-6)

    def test_rejects_adjoints_dynamic_shapes_and_nonconstant(self):
        with tempfile.TemporaryDirectory() as d:
            m,_,_=make_model(pathlib.Path(d)/'tiny.tflite',[1,2,8],8,7)
            self.assertEqual(len(candidates(m)),1)
            for mutate in [lambda q:setattr(q.subgraphs[0].operators[1].builtinOptions,'adjY',True),lambda q:setattr(q.subgraphs[0].tensors[0],'shapeSignature',np.array([1,-1,8],np.int32)),lambda q:setattr(q.buffers[1],'offset',0),lambda q:setattr(q.subgraphs[0].tensors[1],'type',s.TensorType.INT16),lambda q:setattr(q.subgraphs[0].tensors[3],'shape',np.array([1,2,9],np.int32))]:
                q=copy.deepcopy(m);mutate(q);self.assertEqual(candidates(q),[])

    def test_multiple_stripes_and_external_buffer_relocation(self):
        with tempfile.TemporaryDirectory() as d:
            source=pathlib.Path(d)/'wide.tflite';target=pathlib.Path(d)/'fc.tflite'
            _,w,_=make_model(source,[1,2,17],17,257,external_bias=True)
            report=transform(source,target)
            sb=source.read_bytes();tb=target.read_bytes()
            sm=s.Model.GetRootAsModel(sb,0);tm=s.Model.GetRootAsModel(tb,0)
            for i in (1,2):
                old=sm.Buffers(i);new=tm.Buffers(i)
                self.assertEqual(old.Size(),new.Size())
                self.assertEqual(sb[old.Offset():old.Offset()+old.Size()],tb[new.Offset():new.Offset()+new.Size()])
            plan=report['plans'][0]
            got=np.frombuffer(tb,dtype='<u2',count=17*257,offset=plan['new_offset']).reshape(257,17)
            np.testing.assert_array_equal(got,w.view('<u2').T)
            rng=np.random.default_rng(731)
            for _ in range(4):
                x=rng.uniform(-1,1,[1,2,17]).astype(np.float32)
                np.testing.assert_allclose(run(target,x),run(source,x),rtol=1e-6,atol=1e-6)
    def test_output_overwrite_refused(self):
        with tempfile.TemporaryDirectory() as d:
            source=pathlib.Path(d)/'tiny.tflite';target=pathlib.Path(d)/'existing.tflite'
            make_model(source,[1,2,8],8,7);target.write_bytes(b'preserve')
            with self.assertRaises(ValueError):transform(source,target)
            self.assertEqual(target.read_bytes(),b'preserve')

if __name__=='__main__':unittest.main()
