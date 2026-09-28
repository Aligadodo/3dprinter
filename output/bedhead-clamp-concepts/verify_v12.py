from pathlib import Path
import json,math,zipfile
import xml.etree.ElementTree as E
import numpy as np,trimesh,manifold3d as md
BASE=Path(__file__).parent;ROOT=BASE/'releases/床头夹具_A_V1.2_等宽轻量_M4x12_十九盘'
report=json.loads((ROOT/'技术资料/几何装配验证.json').read_text(encoding='utf8'));meta=report['meshes']
def solid(m):return md.Manifold(md.Mesh(np.asarray(m.vertices,np.float32),np.asarray(m.faces,np.uint32)))
def restore(m,name):
 m=m.copy();m.apply_translation(-np.array(meta[name]['print_translation']));m.apply_transform(np.linalg.inv(meta[name]['assembly_to_print_rotation']));return m
def box(a,b):return md.Manifold.cube(np.subtract(b,a)).translate(a)
h=[[7/math.sqrt(3)*math.cos(math.radians(i*60)),7/math.sqrt(3)*math.sin(math.radians(i*60))] for i in range(6)]
nut=md.CrossSection([h]).extrude(3.2).transform([[0,0,1,-10.8],[1,0,0,0],[0,1,0,0]])
def check(m,name):
 assert m.is_watertight and m.is_winding_consistent,name
 a=restore(m,name);s=solid(a);assert s.status()==md.Error.NoError,name
 w=int(name.split('宽')[-1]);b=a.bounds
 assert np.allclose(b[:,1],[-w/2,w/2],atol=1e-4)
 # Full width material at front, top and rear. Side faces all reach the bed plane.
 hi=int(name.split('夹')[-1].split('_')[0].split('-')[-1]);G=hi+3
 for lo,up in [((-8,-w/2,-40),(-2,w/2,-35)),((10,-w/2,2),(11,w/2,9)),((G+1,-w/2,-40),(G+8,w/2,-37))]:
  block=box(lo,up);assert abs((s^block).volume()-block.volume())<.001,(name,'unequal body width')
 if '螺丝S' in name:
  for sign in [-1,1]:
   for y in np.linspace(w/2+6,12.5,81):assert (s^nut.translate((0,sign*y,-1+math.tan(math.radians(15))*(y-12.5)))).volume()<1e-4,name
   for length in [12,16]:
    bolt=md.Manifold.cylinder(length,2,2,48).rotate((0,90,0)).translate((-18.6,sign*12.5,-1))
    vol=(s^bolt).volume();assert vol<1e-4 if length==12 else vol>1
 return {'name':name,'equal_body_width_pass':True,'single_manifold_pass':True,'M4x12_path_pass':True if '螺丝S' in name else None}
rows=[]
for p in (ROOT/'单件STL').glob('床头夹具*.stl'):rows.append(check(trimesh.load(p),p.stem))
assert len(rows)==18
ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
with zipfile.ZipFile(ROOT/'床头夹具_A_V1.2_十九盘_P1S_PETG.3mf') as z:
 cfg=E.fromstring(z.read('Metadata/model_settings.config'));assert len(cfg.findall('plate'))==19;count=0
 for o in cfg.findall('object'):
  name=o.find("metadata[@key='name']").get('value')
  if not name.startswith('床头夹具') or not name.endswith('_01'):continue
  cid=o.find('part').get('id');r=E.fromstring(z.read(f'3D/Objects/object_{cid}.model'))
  vv=np.array([[float(v.get(k)) for k in ('x','y','z')] for v in r.findall('.//m:vertex',ns)])-[25,25,0]
  ff=np.array([[int(v.get(k)) for k in ('v1','v2','v3')] for v in r.findall('.//m:triangle',ns)])
  check(trimesh.Trimesh(vv,ff,process=False),name[:-3]);count+=1
 assert count==18
(ROOT/'技术资料/最终文件独立核验.json').write_text(json.dumps({'STL':rows,'main_3mf_body_variants_checked':count,'M4x16_confirmed_not_supported':True},ensure_ascii=False,indent=2),encoding='utf8')
print('18 STL and 18 3MF body variants checked; all equal-width bodies, M4x12 paths passed.')
