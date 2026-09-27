from pathlib import Path
import math,json,hashlib,zipfile
import xml.etree.ElementTree as E
import numpy as np,trimesh,manifold3d as md
BASE=Path(__file__).parent;ROOT=BASE/'releases'/'床头夹具_A_V1.1_左右斜坡螺母入口_十九盘';OLD=BASE/'releases'/'床头夹具_A_V1_双接口_三档三宽_十九盘'
def solid(m):return md.Manifold(md.Mesh(np.asarray(m.vertices,np.float32),np.asarray(m.faces,np.uint32)))
def restore(m,w):
 m.apply_translation((-20.4,-15,-max(w,44)/2));m.apply_transform(np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]));return m
h=[[7/math.sqrt(3)*math.cos(math.radians(i*60)),7/math.sqrt(3)*math.sin(math.radians(i*60))] for i in range(6)]
nut=md.CrossSection([h]).extrude(3.2).transform([[0,0,1,-17.2],[1,0,0,0],[0,1,0,0]])
def test(m,w):
 assert m.is_watertight and len(m.split())==1
 s=solid(restore(m,w));vals=[]
 for sign in [-1,1]:
  for y in np.linspace(max(w,44)/2+6,12.5,81):vals.append((s^nut.translate((0,sign*y,-1+math.tan(math.radians(15))*(y-12.5)))).volume())
 assert max(vals)<1e-5,max(vals)
 return max(vals)
unchanged=[];changed=[]
for p in (ROOT/'单件STL').glob('*.stl'):
 if '螺丝S' in p.name:
  changed.append({'file':p.name,'max_overlap_mm3':test(trimesh.load(p),int(p.stem.split('宽')[-1]))})
 elif '左右斜坡' not in p.name:
  assert p.read_bytes()==(OLD/'单件STL'/p.name).read_bytes(),p.name
  unchanged.append(p.name)
assert len(changed)==9 and len(unchanged)==12
ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
with zipfile.ZipFile(ROOT/'床头夹具_A_V1.1_十九盘_P1S_PETG.3mf') as z:
 cfg=E.fromstring(z.read('Metadata/model_settings.config'));objects=cfg.findall('object');assert len(objects)==76
 count=0
 for o in objects:
  name=o.find("metadata[@key='name']").get('value')
  if '螺丝S' not in name or not name.endswith('_01'):continue
  cid=o.find('part').get('id');r=E.fromstring(z.read('3D/Objects/object_'+cid+'.model'))
  vv=np.array([[float(v.get(k)) for k in ('x','y','z')] for v in r.findall('.//m:vertex',ns)])-np.array([25,25,0])
  ff=np.array([[int(v.get(k)) for k in ('v1','v2','v3')] for v in r.findall('.//m:triangle',ns)])
  test(trimesh.Trimesh(vv,ff,process=False),int(name.split('宽')[-1].split('_')[0]));count+=1
 assert count==9
(ROOT/'技术资料'/'最终文件独立核验.json').write_text(json.dumps({'unchanged_from_v1_byte_identical':unchanged,'updated_stl_paths':changed,'main_3mf_S_variants_pass':count,'main_3mf_objects':76},ensure_ascii=False,indent=2),encoding='utf8')
print('PASS: nine exported STL and nine 3MF variants, 12 unchanged STL byte-identical.')
