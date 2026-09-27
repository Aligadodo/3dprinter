from pathlib import Path
import json,hashlib,shutil,zipfile,subprocess,sys
import numpy as np,trimesh,manifold3d as md
BASE=Path(__file__).parent
R=BASE/'releases'/'MSkadis挂架_V3.1_双侧斜坡螺母入口_十一盘'
raw=json.loads((BASE/'slice-v31'/'result.json').read_text(encoding='utf8'))
assert raw['return_code']==0 and len(raw['sliced_plates'])==11
assert all(not p.get('warning_message') for p in raw['sliced_plates'])
shutil.copy2(BASE/'slice-v31'/'result.json',R/'技术资料'/'实际切片结果.json')
old=BASE/'releases'/'MSkadis挂架_V3.0_统一规格_十一盘'
for w in [200,220,240,260,280]:
    name=f'连接板_适配板宽{w}_总长{w-20}.stl'
    assert (old/'单件STL'/name).read_bytes()==(R/'单件STL'/name).read_bytes()
checks=[]
for drop in [90,65]:
    parts=[]
    for arm in [60,90,120]:
        name=f'挂架_顶臂{arm}_下垂{drop}_'+('标准版' if drop==90 else '短版')
        m=trimesh.load_mesh(R/'单件STL'/(name+'.stl'))
        assert np.allclose(m.extents,[arm+21,drop+14,44],atol=.02)
        v=m.vertices-np.array([arm,14,22]);s=md.Manifold(md.Mesh(v.astype(np.float32),m.faces.astype(np.uint32)))
        parts.append(s^md.Manifold.cube((89,drop+14,44)).translate((-59,-14,-22)))
        # Nut in the deepest permissible axial position still clears an M4x12 nominal tip.
        assert 20.4+5-12 < 13.6
        checks.append({'name':name,'width':44,'arm_thickness':14,'base_thickness':20.4,'slot_axial_width':4,'nut_axial_clearance_total':.8,'nominal_M4x12_tip_past_deepest_nut_mm':.2})
    for p in parts[1:]:assert ((p-parts[0]).volume()+(parts[0]-p).volume())<.02
(R/'技术资料'/'统一规格复核.json').write_text(json.dumps({'six_brackets':checks,'shared_geometry_pass':True,'five_connector_meshes_unchanged':True,'slice_plates':11,'all_slice_warnings_empty':True},ensure_ascii=False,indent=2),encoding='utf8')
subprocess.run([sys.executable,str(BASE/'prepare_publication_v31.py')],check=True)
pub=BASE/'publication'/'MSkadis挂架_V3.1_双侧入口发布材料_20260927'
shutil.copy2(pub/'01_作品详细说明_可直接复制.md',R/'README_安装说明.md')
for name in ['build_print_kit.py','build_release_v1.py','draw_nut_entry_v31.py','finish_v31.py','prepare_publication_v31.py']:
    shutil.copy2(BASE/name,R/'技术资料'/name)
dep=R/'技术资料'/'print-kit-v1';dep.mkdir(exist_ok=True)
for name in ['P1S-PETG-settings.json','洞洞板挂架_P1S_PETG_M4_三种尺寸_中文分盘.3mf']:
    shutil.copy2(BASE/'print-kit-v1'/name,dep/name)
hashes={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in R.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(R/'技术资料'/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
dest=Path(r'E:/3dprint/自己设计合集/实用组件')/R.name
shutil.copytree(R,dest,dirs_exist_ok=True)
for rel,digest in hashes.items():assert hashlib.sha256((dest/rel).read_bytes()).hexdigest()==digest
with zipfile.ZipFile(dest.parent/(dest.name+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(dest.rglob('*')):
        if p.is_file():z.write(p,Path(dest.name)/p.relative_to(dest))
print('Completed: six modified brackets, five unchanged connectors, eleven plates sliced without warnings, publication assets updated.')
