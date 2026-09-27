from pathlib import Path
import json,zipfile,xml.etree.ElementTree as E,hashlib,shutil,datetime
B=Path(__file__).parent;R=B/'releases'/'MSkadis洞洞板柜顶挂架_V1.0_20260926';C='{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}';P='{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}'
reports=[]
for filename,folder,counts in [('V1_主工程_五盘_按尺寸成套_零件可独立打印.3mf','slice-release-v1',[3,12,12,12,10]),('V1_额外补打_S与L主架各一对_两盘.3mf','slice-release-extra',[2,2])]:
 raw=json.loads((B/folder/'result.json').read_text(encoding='utf8'));assert raw['return_code']==0 and len(raw['sliced_plates'])==len(counts)
 with zipfile.ZipFile(R/filename) as z:
  cfg=E.fromstring(z.read('Metadata/model_settings.config'));root=E.fromstring(z.read('3D/3dmodel.model'))
  objs=cfg.findall('object');assert len(objs)==sum(counts);assert all(len(o.findall('part'))==1 for o in objs)
  expected={}
  for o in root.find(C+'resources'):
   comp=o.find(C+'components')[0];sub=E.fromstring(z.read(comp.get(P+'path').lstrip('/')));vv=sub.findall('.//'+C+'vertex');axis=[[float(v.get(a)) for v in vv] for a in 'xyz'];expected[o.get('name')]=[min(v) for v in axis]+[max(v)-min(v) for v in axis]
  p2=[o for o in objs if any(m.get('key')=='sparse_infill_density' and m.get('value')=='100%' for m in o.findall('metadata'))]
  assert len(p2)==(23 if len(counts)==5 else 0),len(p2)
  for i,pl in enumerate(raw['sliced_plates']):
   assert len(pl['objects'])==counts[i];assert not pl['warning_message'],pl['warning_message']
   for o in pl['objects']:
    bb=o['bbox'];actual=[bb[k] for k in ['x','y','z','width','depth','height']];target=list(expected[o['name']]);target[0]+=(i%3)*307.2;target[1]-=(i//3)*307.2
    # Slicer reports local plate coordinates.
    assert max(abs(a-b) for a,b in zip(actual,target))<0.02,(o['name'],actual,target)
   reports.append({'project':filename,'plate_index':i+1,'objects':len(pl['objects']),'estimated_hours':round(pl['total_predication']/3600,2),'estimated_PETG_g':round(sum(f['total_used_g'] for f in pl['filaments']),1),'warnings':pl['warning_message'],'layout_unchanged':True})
 shutil.copy2(B/folder/'result.json',R/'技术资料'/(folder+'_切片原始结果.json'))
(R/'技术资料'/'切片验证.json').write_text(json.dumps({'slicer':'Bambu Studio installed CLI','command_options':['--slice','0','--arrange','0','--orient','0'],'success':True,'independent_objects':True,'p2_override_object_count':23,'plates':reports,'limitations':'软件切片验证；尚未进行实物打印或承重测试。'},ensure_ascii=False,indent=2),encoding='utf8')
readme=R/'先读我_选盘装配与螺丝规格.md'
s=readme.read_text(encoding='utf8')+'\n## 本机切片估算\n\n时间包含切片器估计的准备过程；不含洞洞板本体。\n\n| 工程 / 盘 | 预计小时 | PETG 克 |\n|---|---:|---:|\n'
for r in reports:s+=f'| {"主工程" if "主工程" in r["project"] else "额外补打"} / {r["plate_index"]} | {r["estimated_hours"]} | {r["estimated_PETG_g"]} |\n'
readme.write_text(s,encoding='utf8')
# Preserve source geometry and provenance alongside version snapshot.
for f in ['build_print_kit.py','localize_kit.py'] :shutil.copy2(B/f,R/'技术资料'/f)
shutil.copy2(B/'print-kit-v1'/'source-board-measurements.json',R/'技术资料'/'原始洞洞板测量.json')
(R/'技术资料'/'源码说明.txt').write_text('源码用于追溯本地生成过程，含原工作区路径。重新运行需调整 ROOT、OLD、BASE 等路径；不要在冻结发布目录直接重建。用户打印入口为根目录 V1 主工程。\nSTL 几何未在本次摆盘中修改。',encoding='utf8')
# Verify every delivered STL remains byte-identical to its original.
oldhash={hashlib.sha256(p.read_bytes()).hexdigest() for p in (B/'print-kit-v1'/'STL').glob('*.stl')}
assert {hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'单件STL').glob('*.stl')}==oldhash
(R/'版本信息.json').write_text(json.dumps({'version':'1.0','frozen_date':'2026-09-26','main_plates':5,'main_individual_objects':49,'extra_plates':2,'extra_objects':4,'unique_STLs':14,'geometry_changed':False,'sliced_all_7_plates':True,'physical_load_test':False,'notes':'按尺寸完整套装摆盘、独立中文对象、P1/P2打印参数、尺寸螺丝对照、11张中文图解。'},ensure_ascii=False,indent=2),encoding='utf8')
checks={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(R.rglob('*')) if p.is_file() and p.name!='SHA256文件清单.json'}
(R/'SHA256文件清单.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf8')
DEST=Path(r'E:\3dprint\自己设计合集\实用组件')/R.name
shutil.copytree(R,DEST,dirs_exist_ok=True)
for p in R.rglob('*'):
 if p.is_file():assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((DEST/p.relative_to(R)).read_bytes()).digest()
archive=R.parent/(R.name+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(R.rglob('*')):
  if p.is_file():z.write(p,R.name+'/'+p.relative_to(R).as_posix())
shutil.copy2(archive,DEST.parent/archive.name)
assert hashlib.sha256(archive.read_bytes()).digest()==hashlib.sha256((DEST.parent/archive.name).read_bytes()).digest()
(DEST.parent/'先看这里_洞洞板挂架V1.txt').write_text('新版冻结目录：'+R.name+'\n先打开目录内「打开这里_选盘与螺丝对照.html」。\n打印打开「V1_主工程_五盘_按尺寸成套_零件可独立打印.3mf」。\n原根目录中文分盘3MF是前版，已保留；本次请使用 V1 目录中的工程。\nS/M/L 各自单板套装：M4×25 六颗、M4×16 两颗；平底头，不是锥形沉头。\n',encoding='utf8')
print(json.dumps({'synced_files':len(checks)+1,'destination':str(DEST),'zip_bytes':archive.stat().st_size,'slice':reports},ensure_ascii=True))

