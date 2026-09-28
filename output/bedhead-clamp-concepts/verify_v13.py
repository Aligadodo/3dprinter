from pathlib import Path
import json,math,zipfile
import xml.etree.ElementTree as E
import numpy as np,trimesh,manifold3d as md
BASE=Path(__file__).parent;ROOT=BASE/'releases/床头夹具_A_V1.3_斜面防滑_多长度螺杆_二十盘'
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
 for lo,up in [((-8,-w/2,-30),(-2,w/2,-25)),((10,-w/2,2),(11,w/2,9)),((G+1,-w/2,-40),(G+8,w/2,-37))]:
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
with zipfile.ZipFile(ROOT/'床头夹具_A_V1.3_二十盘_P1S_PETG.3mf') as z:
 cfg=E.fromstring(z.read('Metadata/model_settings.config'));assert len(cfg.findall('plate'))==20;count=0
 for o in cfg.findall('object'):
  name=o.find("metadata[@key='name']").get('value')
  if not name.startswith('床头夹具') or not name.endswith('_01'):continue
  cid=o.find('part').get('id');r=E.fromstring(z.read(f'3D/Objects/object_{cid}.model'))
  vv=np.array([[float(v.get(k)) for k in ('x','y','z')] for v in r.findall('.//m:vertex',ns)])-[25,25,0]
  ff=np.array([[int(v.get(k)) for k in ('v1','v2','v3')] for v in r.findall('.//m:triangle',ns)])
  check(trimesh.Trimesh(vv,ff,process=False),name[:-3]);count+=1
 assert count==18
grip_checks=[]
for p in (ROOT/'单件STL').glob('床头夹具*.stl'):
 m=restore(trimesh.load(p),p.stem)
 def face_x(z):
  sec=m.section([0,0,1],[0,0,z]);v=sec.vertices
  return float(v[v[:,0]<3,0].max())
 xs=[face_x(z) for z in [-5.25,-30.25]]
 measured=math.degrees(math.atan((xs[1]-xs[0])/25))
 assert abs(measured-1.5)<.03,(p.name,measured)
 root_x=face_x(-14);expected=14*math.tan(math.radians(1.5))-.35
 assert abs(root_x-expected)<.015,(p.name,'groove depth',root_x,expected)
 # Free tip loses outer corner material while the load/mount zone stays full.
 s=solid(m);q=box((-9.2,-1,-39.7),(-8.7,1,-39.2));assert (s^q).volume()<.01
 lo,hi=map(int,p.stem.split('夹')[-1].split('_')[0].split('-'));w=int(p.stem.split('宽')[-1]);front=1+report['assembly']['grip']['max_inward_mm']
 for thickness in [lo,hi]:
  board=box((front,-w/2+.1,-40),(front+thickness,w/2-.1,0));assert (s^board).volume()<.01
 oldpath=BASE/'releases/床头夹具_A_V1.2_等宽轻量_M4x12_十九盘/单件STL'/p.name
 oldvolume=trimesh.load(oldpath).volume;newvolume=trimesh.load(p).volume
 assert newvolume<oldvolume
 grip_checks.append({'name':p.stem,'measured_face_angle_deg':measured,'groove_center_depth_pass':True,'rounded_tip_corner_removed':True,'original_board_range_endpoints_clear':True,'body_volume_reduction_vs_v12_percent':round(100*(1-newvolume/oldvolume),3)})
female=solid(restore(trimesh.load(ROOT/'单件STL/试配件_原牙型母螺口.stl'),'试配件_原牙型母螺口'))
custom_checks=[]
for info in report['assembly']['extra_screws']:
 name=info['name'];m=trimesh.load(ROOT/'单件STL'/(name+'.stl'));assert m.is_watertight and len(m.split())==1
 assert abs(m.extents[2]-info['total_mm'])<.01
 s=solid(restore(m,name));worst=0
 for reach in np.linspace(0,info['max_working_projection_mm'],41):
  delta=reach-46.85;angle=180+90*(delta+37.5)
  v=(female^s.rotate((0,0,angle)).translate((0,0,delta))).volume();worst=max(worst,v);assert v<.02,(name,reach,v)
 custom_checks.append({'name':name,'samples':41,'max_overlap_mm3':worst,'single_solid':True,'length_pass':True})
with zipfile.ZipFile(ROOT/'床头夹具_A_V1.3_二十盘_P1S_PETG.3mf') as z:
 cfg=E.fromstring(z.read('Metadata/model_settings.config'));assert len(cfg.findall('object'))==82
 custom_names=[x['name'] for x in report['assembly']['extra_screws']];seen=0
 for o in cfg.findall('object'):
  name=o.find("metadata[@key='name']").get('value')[:-3]
  if name not in custom_names:continue
  cid=o.find('part').get('id');r=E.fromstring(z.read(f'3D/Objects/object_{cid}.model'))
  vv=np.array([[float(v.get(k)) for k in ('x','y','z')] for v in r.findall('.//m:vertex',ns)])
  ff=np.array([[int(v.get(k)) for k in ('v1','v2','v3')] for v in r.findall('.//m:triangle',ns)])
  i=custom_names.index(name);m=trimesh.load(ROOT/'单件STL'/(name+'.stl'))
  assert np.array_equal(ff,m.faces) and np.allclose(vv,m.vertices+[25+i*45,65,0],atol=1e-6)
  seen+=1
 assert seen==5
files=list((ROOT/'单件STL').glob('*.stl'));assert len(files)==28,len(files)
for p in files:
 m=trimesh.load(p);assert m.is_watertight and len(m.split())==1,p.name
(ROOT/'技术资料/最终文件独立核验.json').write_text(json.dumps({'STL':rows,'main_3mf_body_variants_checked':count,'grip':grip_checks,'custom_screws':custom_checks,'all_28_STL_single_solid':True,'M4x16_confirmed_not_supported':True},ensure_ascii=False,indent=2),encoding='utf8')
print('18 bodies, 5 screw variants, 28 final STL and 20-plate main project verified.')
