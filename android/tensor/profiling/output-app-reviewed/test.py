"""Run reviewed output-allocation ownership fixtures locally; no device access."""
import argparse,json,pathlib,subprocess,shutil,hashlib,os,shlex
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir',type=pathlib.Path,required=True,help='JetLink tree with exactly one full reviewed patch applied')
parser.add_argument('--build-dir',type=pathlib.Path,required=True,help='New isolated local fixture output directory')
parser.add_argument('--swiftc',default=os.environ.get('SWIFTC','swiftc'))
parser.add_argument('--cc',default=os.environ.get('CC','cc'))
args=parser.parse_args()
p=pathlib.Path(__file__).resolve().parent
source=args.source_dir.resolve();b=source/'JetlinkKit/Sources/CLiteRt';run=args.build_dir.resolve()
if not (b/'jl_litert.c').is_file() or not (b/'output_ahwb.inc').is_file():parser.error('Apply one reviewed source patch first')
for protected in (source,p):
    if run.is_relative_to(protected):parser.error('--build-dir must be outside source and package directories')
run.mkdir(parents=True,exist_ok=False)
records=[]
for mode,label in [(0,'rare'),(1,'often')]:
    target=run/label
    shutil.copytree(b,target)
    text=(b/'jl_litert.c').read_text().replace('#define JL_OUTPUT_AHWB_OFTEN 1','#define JL_OUTPUT_AHWB_OFTEN 0');assert text.count('#define JL_OUTPUT_AHWB_OFTEN 0')==1
    (target/'jl_litert.c').write_text(text.replace('#define JL_OUTPUT_AHWB_OFTEN 0',f'#define JL_OUTPUT_AHWB_OFTEN {mode}'))
    shutil.copy2(b/'output_ahwb.inc',target/'output_ahwb.inc')
    binary=run/f'test-{label}'
    cmd=shlex.split(args.cc)+['-O2','-std=gnu11','-Wall','-Wextra','-Werror','-I',str(p/'mock'),'-I',str(target),'-I',str(target/'include'),'-I',str(target/'vendor'),str(p/'test_output_ahwb.c'),'-ldl','-lpthread','-o',str(binary)]
    subprocess.run(cmd,check=True)
    result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30)
    (run/f'c-{label}.log').write_text(result.stdout+result.stderr);result.check_returncode()
    records.append({'suite':'C ownership '+label,'passed':True,'source_sha256':hashlib.sha256((target/'jl_litert.c').read_bytes()).hexdigest()})
text=(source/'JetlinkKit/Sources/JetlinkLiteRT/LiteRt.swift').read_text()
start=text.index('final class LiteRtBuffer {');classes=text[start:]
assert classes.count('final class ')==1 and classes.count('extension LiteRtModel {')==1
assert 'modelOwner = output && model.importedTensorOutputs ? model : nil' in classes
assert text.count('shim.npu = 1')==1 and 'case .tensor:\n      shim.npu = 1' in text
preamble=r'''
import Foundation
import Glibc
var events=[String]()
var failure: String?=nil
func emit(_ s:String){events.append(s);print(s);fflush(stdout)}
struct LiteRtError:Error {let text:String;init(_ t:String){text=t};static func check(_ s:String?)throws{if let s {throw LiteRtError(s)}}}
final class LiteRtModel {
 let importedTensorOutputs:Bool
 let pointer=OpaquePointer(bitPattern:1)!
 init(_ imported:Bool){importedTensorOutputs=imported}
 deinit {emit("model_release")}
}
func jl_litert_buffer_create(_ p:OpaquePointer,_ o:Int32,_ i:Int,_ b:inout OpaquePointer?)->String?{if failure == "create" {return failure};b=OpaquePointer(bitPattern:2)!;return nil}
func jl_litert_buffer_wrap(_ p:OpaquePointer,_ o:Int32,_ i:Int,_ d:UnsafeMutableRawPointer,_ n:Int,_ b:inout OpaquePointer?)->String?{b=OpaquePointer(bitPattern:2)!;return nil}
func jl_litert_buffer_release(_ b:OpaquePointer){emit("buffer_release")}
func jl_litert_buffer_write(_ b:OpaquePointer,_ d:UnsafeRawPointer?,_ n:Int)->String?{return failure}
func jl_litert_buffer_read(_ b:OpaquePointer,_ d:UnsafeMutableRawPointer,_ n:Int)->String?{return failure}
func jl_litert_run(_ p:OpaquePointer,_ i:[OpaquePointer?],_ ni:Int,_ o:[OpaquePointer?],_ no:Int)->String?{return failure}
'''
tests=r'''
func lifecycle()throws {
 events=[];var model:LiteRtModel?=LiteRtModel(true);weak var observed=model
 var buffer:LiteRtBuffer?=try LiteRtBuffer(model!,output:true,index:0)
 precondition(buffer != nil);model=nil;precondition(observed != nil && events.isEmpty)
 buffer=nil;precondition(observed == nil && events == ["buffer_release","model_release"])
 events=[];model=LiteRtModel(false);observed=model
 buffer=try LiteRtBuffer(model!,output:true,index:0);model=nil
 precondition(observed == nil && events == ["model_release"]);buffer=nil
 precondition(events == ["model_release","buffer_release"])
 events=[];model=LiteRtModel(true);observed=model;failure="create"
 do {_ = try LiteRtBuffer(model!,output:true,index:0);preconditionFailure()}catch{}
 precondition(events.isEmpty);model=nil;precondition(observed == nil && events == ["model_release"]);failure=nil
 events=[];model=LiteRtModel(true);observed=model
 buffer=try LiteRtBuffer(model!,index:0);model=nil;precondition(observed==nil);buffer=nil
 events=[];model=LiteRtModel(true);observed=model
 let memory=UnsafeMutableRawPointer.allocate(byteCount:8,alignment:8);defer{memory.deallocate()}
 buffer=try LiteRtBuffer(model!,output:true,index:0,wrapping:memory,bytes:8);model=nil;precondition(observed==nil);buffer=nil
 events=[];model=LiteRtModel(false);buffer=try LiteRtBuffer(model!,output:true,index:0)
 failure="ordinary error";do{try buffer!.zero();preconditionFailure()}catch{}
 do{try model!.run(inputs:[],outputs:[]);preconditionFailure()}catch{}
 failure=nil;buffer=nil;model=nil
 print("Swift ownership and ordinary-backend error fixtures passed")
}
let scenario=CommandLine.arguments.dropFirst().first ?? "lifecycle"
if scenario == "lifecycle" {try lifecycle()} else {
 let model=LiteRtModel(true),buffer=try LiteRtBuffer(LiteRtModel(true),output:true,index:0)
 let memory=UnsafeMutableRawPointer.allocate(byteCount:8,alignment:8)
 failure="injected uncertain failure";emit("before_failure")
 switch scenario {
 case "zero":try buffer.zero()
 case "read":try buffer.read(into:memory,bytes:8)
 case "write":try buffer.write(from:memory,bytes:8)
 case "run":try model.run(inputs:[],outputs:[])
 default:fatalError("bad fixture scenario")
 }
 fatalError("failed to stop")
}
'''
fixture=run/'SwiftOwnership.swift';fixture.write_text(preamble+classes+tests)
# The generated fixture extracts the actual patched Swift implementation.
binary=run/'test-swift';subprocess.run([args.swiftc,'-O',str(fixture),'-o',str(binary)],check=True)
for scenario in ['lifecycle','zero','read','write','run']:
    result=subprocess.run([str(binary),scenario],capture_output=True,text=True,timeout=30)
    (run/f'swift-{scenario}.log').write_text(result.stdout+result.stderr)
    if scenario=='lifecycle':result.check_returncode()
    else:
        expected='diagnostic Tensor execution failed; process restart required' if scenario=='run' else 'diagnostic output mapping failed; process restart required'
        assert result.returncode<0 and expected in result.stderr and 'failed to stop' not in result.stderr and 'before_failure' in result.stdout and 'buffer_release' not in result.stdout and 'model_release' not in result.stdout,(scenario,result)
    records.append({'suite':'Swift '+scenario,'passed':True,'exit':result.returncode})
(run/'ownership-tests.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2))

