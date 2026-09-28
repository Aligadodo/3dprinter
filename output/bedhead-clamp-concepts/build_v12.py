"""Bedhead clamp A V1: all 18 variants, rounded H4 hooks and ModelB M4 seat."""
from pathlib import Path
import ast,copy,json,math,zipfile,shutil,hashlib
import xml.etree.ElementTree as E
import numpy as np,trimesh,manifold3d as md
from shapely.geometry import Polygon,Point,box as sb,LineString
from shapely.ops import unary_union
from shapely.geometry.polygon import orient

BASE=Path(__file__).parent
ROOT=BASE/'releases'/'床头夹具_A_V1.2_等宽轻量_M4x12_十九盘'
for p in ['单件STL','单盘工程','技术资料','图解','来源']:(ROOT/p).mkdir(parents=True,exist_ok=True)
source=BASE/'revision-a'
def solid(m):return md.Manifold(md.Mesh(np.asarray(m.vertices,np.float32),np.asarray(m.faces,np.uint32)))
def mesh(s):
 m=s.simplify(.006).to_mesh64();q=trimesh.Trimesh(np.asarray(m.vert_properties)[:,:3],np.asarray(m.tri_verts),process=True)
 q.update_faces(q.nondegenerate_faces());q.remove_unreferenced_vertices();return q
def cube(a,b):return md.Manifold.cube(np.subtract(b,a)).translate(a)
def cyl(r,h,n=64):return md.Manifold.cylinder(h,r,r,n)
def extrude(poly,depth):
 p=orient(poly,sign=1);rings=[list(p.exterior.coords)[:-1]]+[list(x.coords)[:-1] for x in p.interiors]
 return md.CrossSection(rings).extrude(depth)
def xz(poly,w):return extrude(poly,w).transform([[1,0,0,0],[0,0,1,-w/2],[0,-1,0,0]])
def yz(poly,x0,th):return extrude(poly,th).transform([[0,0,1,x0],[1,0,0,0],[0,1,0,0]])
def bore(x0,L,y,z,d):return cyl(d/2,L,48).rotate((0,90,0)).translate((x0,y,z))
def normalize(m):m=m.copy();m.apply_translation(-m.bounds[0]);return m
PARTS={};SOLIDS={};REPORT={};CHECKS={};RANGES=[(20,40),(35,55),(50,70)];WIDTHS={"挂钩H4":[48,50,54],"螺丝S":[36,40,44]}
def save(name,s,rotation=None):
 m=mesh(s);assert m.is_watertight and m.volume>0 and s.status()==md.Error.NoError,name
 assembly_bounds=m.bounds.copy()
 if rotation is not None:m.apply_transform(rotation)
 print_min=m.bounds[0].copy()
 m=normalize(m);dest=ROOT/'单件STL'/(name+'.stl');m.export(dest)
 back=trimesh.load(dest)
 back.update_faces(back.nondegenerate_faces());back.update_faces(back.unique_faces());back.remove_unreferenced_vertices()
 back.export(dest);back=trimesh.load(dest)
 assert back.is_watertight and back.is_winding_consistent and len(back.split())==1,name
 PARTS[name]=back;SOLIDS[name]=s;REPORT[name]={'dimensions_mm':np.round(back.extents,3).tolist(),'volume_mm3':round(float(back.volume),2),'faces':len(back.faces),'watertight_single_solid':True,'assembly_bounds':assembly_bounds.tolist(),'print_translation':(-print_min).tolist(),'assembly_to_print_rotation':(np.eye(4) if rotation is None else rotation).tolist()}

ms=solid(trimesh.load(source/'reference-screw.stl'))
mc=solid(trimesh.load(source/'reference-clamp.stl'))
shaft=ms^cube((-30,-30,-7.5),(30,30,28));knob=(ms^cube((-30,-30,-27.5),(30,30,-17.5))).translate((0,0,10))
SCREW=shaft+knob
SCREW_NAME='共用粗螺杆_杆35_旋钮10_总长45'
save(SCREW_NAME,SCREW)
rear=9.4;axis=13.65
FEMALE=mc^cyl(11.7,rear).translate((axis,0,-19.35-rear))
FEMALE_CENTER=FEMALE.translate((-axis,0,0))
FRAME_ROT=np.array([[1,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,1]],float)
# Rounded J section; the silhouette is rounded before extrusion.
j=Polygon([(-13.5,5),(-22.8,5),(-22.8,15),(-19.8,15),(-19.8,9),(-13.5,9)])
j=j.buffer(-.55,join_style=1).buffer(.55,join_style=1)
# Exact tip reaches 15 mm at centre; round lateral ends by a capsule intersection.
j=unary_union([j,sb(-22.25,13.8,-20.35,15)]).buffer(0)
HOOK=xz(Polygon([(x,-z) for x,z in j.exterior.coords]),4.4)
capsule=LineString([(0,7.2),(0,12.8)]).buffer(2.2,quad_segs=24)
HOOK=HOOK^yz(capsule,-24,12)
# Slight top edge roundover on the tip through profile construction.
def make_hooks():
 a=[]
 for y in [-20,20]:
  for dz in [0,-40]:a.append(HOOK.translate((0,y,dz)))
 return md.Manifold.batch_boolean(a,md.OpType.Add)
HOOKS=make_hooks().translate((4.6,0,0))

SLOPE=math.tan(math.radians(15))
def nut_outline(af):
 return Polygon([(af/math.sqrt(3)*math.cos(math.radians(60*i)),af/math.sqrt(3)*math.sin(math.radians(60*i))) for i in range(6)])
def m4_cuts(s,fw=44):
 from shapely.affinity import translate
 for sign in [-1,1]:
  y=sign*12.5
  s=s-bore(-13.7,9.1,y,-1,4.4)
  # Two isolated sloping channels. A closed inner hex profile stops each nut.
  end=fw/2+6
  inner=translate(nut_outline(7.6),xoff=y,yoff=-1)
  outer=translate(nut_outline(7.6),xoff=sign*end,yoff=-1+SLOPE*(end-12.5))
  channel=unary_union([inner,outer]).convex_hull
  s=s-yz(channel,-11.2,4.0)
  # A short flared entry eases both nut thickness and in-plane alignment.
  points=[]
  for yy,xa,xb,half in [(fw/2-2,-11.2,-7.2,3.8),(fw/2+.5,-11.6,-6.8,4.5)]:
   zz=-1+SLOPE*(yy-12.5)
   for xx in [xa,xb]:
    for z in [zz-half,zz+half]:points.append([xx,sign*yy,z])
  funnel=solid(trimesh.convex.convex_hull(np.asarray(points)))
  s=s-funnel
 return s

names=[];ALL_ASSEMBLY={}
for kind in ['挂钩H4','螺丝S']:
 for w in WIDTHS[kind]:
  for lo,hi in RANGES:
   G=hi+3
   # X/Z outline with 2 mm outside rounding and 2 mm inside corner fillets.
   poly=unary_union([sb(-9.4,-10.4,G+rear,-1),sb(-9.4,-10.4,0,45),sb(G,-10.4,G+rear,45)])
   poly=poly.buffer(-1.5,join_style=1).buffer(1.5,join_style=1)
   frame=xz(poly,w)
   sleeve=FEMALE.transform([[0,0,-1,G-19.35],[0,1,0,0],[1,0,0,-23-axis]])
   frame=(frame-bore(G-1,rear+2,0,-23,23.4))+sleeve
   if kind=='挂钩H4':
    fw=w
    front=frame
    s=frame+HOOKS
   else:
    fw=w
    boss=xz(sb(-13.6,-10.4,0,17).buffer(-.7,join_style=1).buffer(.7,join_style=1),fw)
    s=m4_cuts(frame+boss,fw)
   name=f'床头夹具_{kind}_夹{lo}-{hi}_宽{w}'
   save(name,s,FRAME_ROT);names.append((kind,w,lo,hi,name));ALL_ASSEMBLY[name]=s
   CHECKS[name]={'board_range_mm':[lo,hi],'effective_opening_mm':hi+2,'raw_opening_mm':G,'body_width_mm':w,'interface_width_mm':fw,'front_arm_mm':9.4,'top_beam_mm':9.4,'rear_arm_mm':9.4,'front_seat_mm':9.4 if kind=='挂钩H4' else 13.6,'min_knob_gap_mm':3.6,'max_knob_gap_mm':23.6,'rear_overhang_mm':45}
   print('built',name,flush=True)

# Equal-width body contact at the first printable layer; no widened floating head.
comparisons=[]
previous=BASE/'releases'/'床头夹具_A_V1.1_左右斜坡螺母入口_十九盘'/'单件STL'
for kind,w,lo,hi,name in names:
 oldw=[36,44,60][WIDTHS[kind].index(w)]
 old=trimesh.load(previous/f'床头夹具_{kind}_夹{lo}-{hi}_宽{oldw}.stl')
 current=PARTS[name]
 sec=current.section([0,0,1],[0,0,.2]);assert sec is not None
 # x=10 lies inside the top beam, well away from front head and thread sleeve.
 cross=ALL_ASSEMBLY[name]^cube((10,-w/2,2),(11,w/2,9))
 assert abs(cross.volume()-w*7)<1e-4,(name,'non-uniform bridge width')
 comparisons.append({'new':name,'old_width':oldw,'new_width':w,'old_volume_mm3':float(old.volume),'new_volume_mm3':float(current.volume),'solid_volume_reduction_percent':round(100*(1-current.volume/old.volume),1),'equal_width_bridge_pass':True})
CHECKS['comparison']=comparisons

# Full-range helical sweep: same pitch/phase on both preserved meshes.
thread=[]
for gap in np.linspace(2,22,81):
 delta=gap-46.85;angle=180+90*(delta+37.5)
 bolt=SCREW.rotate((0,0,angle)).translate((0,0,delta))
 vol=(FEMALE_CENTER^bolt).volume();assert vol<1e-5,('thread interference',gap,vol)
 thread.append([round(float(gap),3),float(vol)])
CHECKS['thread']={'pitch_mm':4,'phase_at_delta_minus37_5_deg':180,'sample_count':len(thread),'max_overlap_mm3':max(x[1] for x in thread),'shaft_travel_mm':20}

# Reference holes: 5.2 x 15.2 capsules in a 5 mm plate, 40 mm in both directions.
def pegboard(back=-9.7,zc=10):
 p=cube((back-5,-50,-65+zc),(back,50,20+zc))
 for y in [-20,20]:
  for z in [zc,zc-40]:
   cap=LineString([(y,z-5),(y,z+5)]).buffer(2.6,quad_segs=32)
   p=p-yz(cap,back-5.1,5.2)
 return p
hook_model=ALL_ASSEMBLY['床头夹具_挂钩H4_夹20-40_宽48']
hookpath=[]
for back in np.linspace(-23.4,-9.7,36):
 v=(hook_model^pegboard(back,10)).volume();assert v<1e-5,('hook approach',back,v);hookpath.append(v)
for zz in np.linspace(10,2.8,37):
 v=(hook_model^pegboard(-9.7,zz)).volume();assert v<1e-5,('hook lower',zz,v);hookpath.append(v)
pull=(hook_model^pegboard(-11.9,2.8)).volume();assert pull>1
CHECKS['hooks']={'slot_width_mm':5.2,'slot_height_mm':15.2,'board_mm':5,'pitch_yz_mm':[40,40],'hook_width_mm':4.4,'side_clearance_each_mm':.4,'throat_mm':5.8,'round_tip_radius_mm':2.2,'side_profile_radius_mm':.55,'lowering_mm':7.2,'path_samples':len(hookpath),'max_overlap_mm3':max(hookpath),'seated_pullout_collision_mm3':float(pull),'anti_lift_lock':False}

# Recheck every final S variant: both sloping insertion paths and closed bottom.
nut=yz(nut_outline(7),-10.8,3.2)
m4_paths=[]
for kind,w,lo,hi,name in names:
 if kind!='螺丝S':continue
 s=ALL_ASSEMBLY[name];fw=w;worst=0
 for sign in [-1,1]:
  for yy in np.linspace(fw/2+6,12.5,81):
   zz=-1+SLOPE*(yy-12.5)
   v=(s^nut.translate((0,sign*yy,zz))).volume()
   assert v<1e-5,('side nut path',name,sign,yy,v);worst=max(worst,v)
 # Exact remaining material where the old bottom T entrance used to be.
 plug=cube((-10.8,-3,-16),(-7.6,3,-6))
 assert abs((s^plug).volume()-plug.volume())<1e-5,('bottom entry not closed',name)
 # Inner-end walls separate the two channels and prevent overshooting inward.
 for sign in [-1,1]:assert (s^nut.translate((0,sign*10.5,-1))).volume()>1
 for length in [12]:
  for yy in [-12.5,12.5]:assert (s^bore(-18.6,length,yy,-1,4)).volume()<1e-5
 m4_paths.append({'name':name,'face_width_mm':fw,'paths':2,'samples_per_path':81,'maximum_overlap_mm3':worst,'entry_center_above_seat_mm':round(SLOPE*(fw/2-12.5),3),'closed_bottom_pass':True,'inner_stop_pass':True})
CHECKS['m4']={'hole_mm':4.4,'pitch_mm':25,'nut_AF_mm':7,'nut_thickness_mm':3.2,'channel_AF_mm':7.6,'channel_thickness_mm':4.0,'entry_mouth_thickness_mm':4.8,'entry_mouth_height_mm':9.0,'slope_deg':15,'flare_length_mm':2,'front_skin_min_channel_mm':2.4,'front_skin_min_mouth_mm':2.0,'central_web_between_channels_min_mm':round(25-2*7.6/math.sqrt(3),3),'nut_path_pass':True,'bottom_T_removed':True,'all_variants':m4_paths,'bolts_mm':[12],'board_mm':5,'blind_depth_mm':9,'tail_clearance_mm':2,'nominal_nut_depth_range_mm':[2.8,6.0],'minimum_full_nut_exit_mm':0.6}

# Small first-print samples exercise exactly the production interfaces.
HCOUPON='试配件_H4四钩_孔距40_板厚5'
save(HCOUPON,cube((-9.4,-24,-44),(-5.4,24,10.4))+HOOKS,FRAME_ROT)
NCOUPON='试配件_M4左右斜坡入口_孔距25'
save(NCOUPON,m4_cuts(cube((-13.6,-18,-17),(0,18,10.4)),36),FRAME_ROT)
FCOUPON='试配件_原牙型母螺口'
save(FCOUPON,FEMALE_CENTER)

# Bambu project serialization reuses the proven local project writer only.
OLD=Path('output/skadis-corner-support/print-kit-v1')
SET=json.loads((OLD/'P1S-PETG-settings.json').read_text(encoding='utf8'))
SET.update({'print_settings_id':'床头A_V1.2_PETG_020_4墙_30填充_自动支撑','enable_support':'1','support_type':'normal(auto)','support_on_build_plate_only':'0','support_threshold_angle':'30','wall_loops':'4','sparse_infill_density':'30%'})
C='http://schemas.microsoft.com/3dmanufacturing/core/2015/02';P='http://schemas.microsoft.com/3dmanufacturing/production/2015/06';B='http://schemas.bambulab.com/package/2021'
E.register_namespace('',C);E.register_namespace('p',P);T=lambda s:'{'+C+'}'+s;I='1 0 0 0 1 0 0 0 1 0 0 0'
def meta(o,k,v):E.SubElement(o,'metadata',key=k,value=str(v))
def xml(o):return E.tostring(o,encoding='utf-8',xml_declaration=True)
writer=Path('output/skadis-corner-support/build_release_v1.py').read_text(encoding='utf8').replace('洞洞板挂架 V1.0 独立零件','床头夹具 A V1.2 等宽轻量 M4x12').replace('(pi%3)','(pi%5)').replace('(pi//3)','(pi//5)')
tree=ast.parse(writer);exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='project'],type_ignores=[]),'project-writer','exec'))
def part(name,x,y,n=1):
 m=PARTS[name].copy();m.apply_translation((x,y,0));return {'name':name+f'_{n:02d}','key':name,'mesh':m,'profile':'P2' if name==SCREW_NAME else 'P1'}
plates=[('第01盘_先试配_四钩螺口M4',[part(HCOUPON,25,35),part(NCOUPON,70,35),part(FCOUPON,115,35),part(SCREW_NAME,155,35)])]
for kind,w,lo,hi,name in names:
 pp=[part(name,25,25,1),part(name,25,112,2),part(SCREW_NAME,180,48,1),part(SCREW_NAME,180,138,2)]
 plates.append((f'第{len(plates)+1:02d}盘_{kind}_夹{lo}-{hi}_宽{w}_一对含螺杆',pp))
validation=[]
for title,ps in plates:
 bounds=[sb(*p['mesh'].bounds[0,:2],*p['mesh'].bounds[1,:2]) for p in ps]
 for b in bounds:assert sb(5,5,251,251).covers(b) and not sb(0,0,18,28).intersects(b),(title,b.bounds)
 distances=[bounds[i].distance(bounds[j]) for i in range(len(bounds)) for j in range(i)];assert min(distances)>6,(title,distances)
 validation.append({'name':title,'objects':len(ps),'min_bounding_box_gap_mm':min(distances),'within_P1S_bed':True})
 project(ROOT/'单盘工程'/(title+'.3mf'),[(title,ps)])
project(ROOT/'床头夹具_A_V1.2_十九盘_P1S_PETG.3mf',plates)
(ROOT/'技术资料'/'几何装配验证.json').write_text(json.dumps({'meshes':REPORT,'assembly':CHECKS,'plates':validation},ensure_ascii=False,indent=2),encoding='utf8')
(ROOT/'技术资料'/'清单.json').write_text(json.dumps([{'plate':t,'objects':[p['name'] for p in ps]} for t,ps in plates],ensure_ascii=False,indent=2),encoding='utf8')
(ROOT/'技术资料'/'P1S_PETG参数.json').write_text(json.dumps(SET,ensure_ascii=False,indent=2),encoding='utf8')
for n in ['reference-screw.stl','reference-clamp.stl']:shutil.copy2(source/n,ROOT/'来源'/n)
shutil.copy2(__file__,ROOT/'技术资料'/Path(__file__).name)
print(ROOT,flush=True)
print(json.dumps(CHECKS['hooks'],ensure_ascii=False),flush=True)

