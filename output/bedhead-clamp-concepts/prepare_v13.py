from pathlib import Path
p=Path(__file__).parent
s=(p/'build_v12.py').read_text(encoding='utf8')
s=s.replace('床头夹具_A_V1.2_等宽轻量_M4x12_十九盘','床头夹具_A_V1.3_斜面防滑_多长度螺杆_二十盘').replace('床头夹具_A_V1.2_十九盘_P1S_PETG','床头夹具_A_V1.3_二十盘_P1S_PETG').replace('床头夹具 A V1.2 等宽轻量 M4x12','床头夹具 A V1.3 斜面防滑 多长度螺杆').replace('床头A_V1.2_PETG','床头A_V1.3_PETG')
start=s.index('def mesh(s):');end=s.index('def cube(',start)
s=s[:start]+'''def clean_mesh(q):
 for digits in [None,6,5,4,3,2]:
  t=q.copy()
  if digits is not None:t.merge_vertices(digits_vertex=digits)
  t.update_faces(t.nondegenerate_faces());t.update_faces(t.unique_faces());t.remove_unreferenced_vertices()
  if t.is_watertight and t.is_winding_consistent:return t
 raise ValueError('mesh export precision cleanup failed')
def mesh(s):
 m=s.simplify(.006).to_mesh64()
 return clean_mesh(trimesh.Trimesh(np.asarray(m.vert_properties)[:,:3],np.asarray(m.tri_verts),process=True))
''' +s[end:]
s=s.replace('back.update_faces(back.nondegenerate_faces());back.update_faces(back.unique_faces());back.remove_unreferenced_vertices()','back=clean_mesh(back)')
idx=s.index('names=[];ALL_ASSEMBLY={}')
s=s[:idx]+'''# Only the inner furniture-contact face slopes. External mounts stay put.
JAW_ANGLE=1.5;JAW_TAN=math.tan(math.radians(JAW_ANGLE))
JAW_BOTTOM=-38.5;JAW_INSET=-JAW_BOTTOM*JAW_TAN
def grip_face(s,w):
 # Root z=0 stays at x=0; free end leans toward the screw.
 wedge=Polygon([(-.6,0),(0,0),(JAW_INSET,-JAW_BOTTOM),(-.6,-JAW_BOTTOM)])
 s=s+xz(wedge,w)
 # Round-bottom lateral channels, cut into the tilted plane.
 # A radius .6 circle centered .25 outside gives a .35 mm nominal recess.
 for zc in np.arange(-4,-37,-2.5):
  xc=-zc*JAW_TAN+.25
  groove=cyl(.6,w+2,32).rotate((90,0,0)).translate((xc,w/2+1,zc))
  s=s-groove
 # Round the unloaded free tip in XZ, without tapering lateral print width.
 tip_mask=xz(sb(-9.4,33,1.2,40).buffer(-3.3,join_style=1).buffer(3.3,join_style=1),w)
 remove=cube((-15,-w/2-1,-46),(2,w/2+1,-36.5))
 s=(s-remove)+(s^tip_mask)
 return s
CHECKS['grip']={'face_angle_deg':JAW_ANGLE,'contact_height_mm':-JAW_BOTTOM,'max_inward_mm':JAW_INSET,'groove_pitch_mm':2.5,'groove_depth_nominal_mm':.35,'groove_radius_mm':.6,'groove_count':14,'free_tip_radius_mm':3.3,'free_tip_rounding_below_z_mm':-36.5,'fixed_jaw_end_z_mm':-40,'fixed_jaw_shortened_mm':5,'no_sharp_teeth':True,'friction_tested':False,'angle_reference':'relative to original inner face; free end inward; external mount unchanged'}

''' +s[idx:]
s=s.replace("name=f'床头夹具_{kind}_夹{lo}-{hi}_宽{w}'","s=grip_face(s,w)\n   name=f'床头夹具_{kind}_夹{lo}-{hi}_宽{w}'")
s=s.replace("'effective_opening_mm':hi+2","'effective_opening_mm':round(hi+2-JAW_INSET,4)")
s=s.replace('np.linspace(2,22,81)','np.linspace(.8,22,86)')
idx=s.index('# Small first-print samples')
s=s[:idx]+'''# Periodic source thread, preserving the original tip and matched female.
# Shaft lengths include full female engagement plus a 2 mm knob clearance.
def engraved_label(s,text_value,zbase):
 strokes={
 'P':[[(0,0),(0,3.6),(2,3.6),(2,1.8),(0,1.8)]],
 '1':[[(.5,2.8),(1,3.6),(1,0)],[(.2,0),(1.8,0)]],
 '2':[[(0,3.6),(2,3.6),(2,1.8),(0,1.8),(0,0),(2,0)]],
 '3':[[(0,3.6),(2,3.6),(2,0),(0,0)],[(0,1.8),(2,1.8)]],
 '4':[[(0,3.6),(0,1.8),(2,1.8)],[(2,3.6),(2,0)]],
 '5':[[(2,3.6),(0,3.6),(0,1.8),(2,1.8),(2,0),(0,0)]],
 '0':[[(0,0),(0,3.6),(2,3.6),(2,0),(0,0)]]}
 for i,ch in enumerate(text_value):
  for line in strokes[ch]:
   poly=LineString([(x+i*3-4,y-8) for x,y in line]).buffer(.28,quad_segs=4)
   # Mirror X so marking is readable looking directly at the knob underside.
   from shapely.affinity import scale
   poly=scale(poly,xfact=-1,yfact=1,origin=(0,0))
   s=s-extrude(poly,.65).translate((0,0,zbase-.1))
 return s
EXTRA_SCREWS=[];screw_checks=[]
from sampled_screw_v13 import sample_profile,shaft_mesh
profile=sample_profile(trimesh.load(source/'reference-screw.stl'))
knob_template=ms^cube((-30,-30,-27.5),(30,30,-17.5))
for penetration in [10,20,30,40,50]:
 L=penetration+rear+2;rootz=28-L
 shaft_long=solid(shaft_mesh(profile,rootz-.10))
 custom=shaft_long+knob_template.translate((0,0,rootz+17.5))
 custom=engraved_label(custom,'P'+str(penetration),rootz-10)
 label=f'粗螺杆_P{penetration:02d}_最大伸入{penetration}_杆{L:.1f}_总{L+10:.1f}'
 save(label,custom);EXTRA_SCREWS.append(label)
 worst=0
 for reach in np.linspace(0,penetration,101):
  delta=reach-46.85;angle=180+90*(delta+37.5)
  moving=custom.rotate((0,0,angle)).translate((0,0,delta))
  v=(FEMALE_CENTER^moving).volume();worst=max(worst,v)
  assert v<.002,('custom thread',penetration,reach,v)
 # Minimum clearance is exactly 2 mm at the named working reach.
 assert abs(L-rear-penetration-2)<1e-8
 screw_checks.append({'name':label,'engraved':'P'+str(penetration),'shaft_mm':L,'total_mm':L+10,'max_working_projection_mm':penetration,'min_knob_gap_mm':2,'full_female_engagement_mm':rear,'thread_samples':101,'max_overlap_mm3':worst,'profile':'sampled source profile, pitch4, radial allowance0.04, bore5','not_axially_scaled':True})
 print('custom screw checked',penetration,flush=True)
CHECKS['extra_screws']=screw_checks

''' + s[idx:]
s=s.replace("save(FCOUPON,FEMALE_CENTER)","save(FCOUPON,FEMALE_CENTER)\nGCOUPON='试配件_1.5度齿槽接触面'\nsave(GCOUPON,grip_face(cube((-2,-18,-44),(0,18,0)),36),FRAME_ROT)")
s=s.replace("part(SCREW_NAME,155,35)])]","part(SCREW_NAME,155,35),part(GCOUPON,205,35)])]")
s=s.replace("p['profile']=='P2'", "p['profile']=='P2'")
s=s.replace("'P2' if name==SCREW_NAME else 'P1'","'P2' if name==SCREW_NAME or name in EXTRA_SCREWS else 'P1'")
s=s.replace('validation=[]',"plates.append(('第20盘_粗螺杆选配_P10至P50_五种长度',[part(n,25+i*45,65) for i,n in enumerate(EXTRA_SCREWS)]))\nvalidation=[]")
(p/'build_v13.py').write_text(s,encoding='utf8')
print(p/'build_v13.py')
