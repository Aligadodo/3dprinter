from pathlib import Path
p=Path(__file__).parent
s=(p/'verify_v12.py').read_text(encoding='utf8').replace('床头夹具_A_V1.2_等宽轻量_M4x12_十九盘','床头夹具_A_V1.3_斜面防滑_多长度螺杆_二十盘').replace('床头夹具_A_V1.2_十九盘_P1S_PETG','床头夹具_A_V1.3_二十盘_P1S_PETG').replace("len(cfg.findall('plate'))==19","len(cfg.findall('plate'))==20")
s=s.replace("((-8,-w/2,-40),(-2,w/2,-35))","((-8,-w/2,-30),(-2,w/2,-25))")
a=s.index("(ROOT/'技术资料/最终文件独立核验.json')")
s=s[:a]+'''grip_checks=[]
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
'''
(p/'verify_v13.py').write_text(s,encoding='utf8')
