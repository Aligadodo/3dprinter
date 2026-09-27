from pathlib import Path
p=Path(__file__).parent
s=(p/'build_v1.py').read_text(encoding='utf-8-sig')
s=s.replace('床头夹具_A_V1_双接口_三档三宽_十九盘','床头夹具_A_V1.1_左右斜坡螺母入口_十九盘').replace('床头夹具_A_V1_十九盘_P1S_PETG','床头夹具_A_V1.1_十九盘_P1S_PETG').replace('床头A_V1_PETG','床头A_V1.1_PETG').replace('床头夹具 A V1 十八规格','床头夹具 A V1.1 左右斜坡螺母入口')
a=s.index('def m4_cuts(s):');b=s.index('\nnames=[];',a)
s=s[:a]+'''SLOPE=math.tan(math.radians(15))
def nut_outline(af):
 return Polygon([(af/math.sqrt(3)*math.cos(math.radians(60*i)),af/math.sqrt(3)*math.sin(math.radians(60*i))) for i in range(6)])
def m4_cuts(s,fw=44):
 from shapely.affinity import translate
 for sign in [-1,1]:
  y=sign*12.5
  s=s-bore(-20.5,16.1,y,-1,4.4)
  # Two isolated sloping channels. A closed inner hex profile stops each nut.
  end=fw/2+6
  inner=translate(nut_outline(7.6),xoff=y,yoff=-1)
  outer=translate(nut_outline(7.6),xoff=sign*end,yoff=-1+SLOPE*(end-12.5))
  channel=unary_union([inner,outer]).convex_hull
  s=s-yz(channel,-17.6,4.0)
  # A short flared entry eases both nut thickness and in-plane alignment.
  points=[]
  for yy,xa,xb,half in [(fw/2-2,-17.6,-13.6,3.8),(fw/2+.5,-18,-13.2,4.5)]:
   zz=-1+SLOPE*(yy-12.5)
   for xx in [xa,xb]:
    for z in [zz-half,zz+half]:points.append([xx,sign*yy,z])
  funnel=solid(trimesh.convex.convex_hull(np.asarray(points)))
  s=s-funnel
 return s
''' +s[b:]
s=s.replace('s=m4_cuts(frame+boss)','s=m4_cuts(frame+boss,fw)')
a=s.index('# M4 hardware sweep');b=s.index('# Small first-print',a)
s=s[:a]+'''# Recheck every final S variant: both sloping insertion paths and closed bottom.
nut=yz(nut_outline(7),-17.2,3.2)
m4_paths=[]
for kind,w,lo,hi,name in names:
 if kind!='螺丝S':continue
 s=ALL_ASSEMBLY[name];fw=max(44,w);worst=0
 for sign in [-1,1]:
  for yy in np.linspace(fw/2+6,12.5,81):
   zz=-1+SLOPE*(yy-12.5)
   v=(s^nut.translate((0,sign*yy,zz))).volume()
   assert v<1e-5,('side nut path',name,sign,yy,v);worst=max(worst,v)
 # Exact remaining material where the old bottom T entrance used to be.
 plug=cube((-17.3,-3,-16),(-14.1,3,-6))
 assert abs((s^plug).volume()-plug.volume())<1e-5,('bottom entry not closed',name)
 # Inner-end walls separate the two channels and prevent overshooting inward.
 for sign in [-1,1]:assert (s^nut.translate((0,sign*10.5,-1))).volume()>1
 for length in [12,16,18]:
  for yy in [-12.5,12.5]:assert (s^bore(-25.4,length,yy,-1,4)).volume()<1e-5
 m4_paths.append({'name':name,'face_width_mm':fw,'paths':2,'samples_per_path':81,'maximum_overlap_mm3':worst,'entry_center_above_seat_mm':round(SLOPE*(fw/2-12.5),3),'closed_bottom_pass':True,'inner_stop_pass':True})
CHECKS['m4']={'hole_mm':4.4,'pitch_mm':25,'nut_AF_mm':7,'nut_thickness_mm':3.2,'channel_AF_mm':7.6,'channel_thickness_mm':4.0,'entry_mouth_thickness_mm':4.8,'entry_mouth_height_mm':9.0,'slope_deg':15,'flare_length_mm':2,'front_skin_min_channel_mm':2.8,'front_skin_min_mouth_mm':2.4,'central_web_between_channels_min_mm':round(25-2*7.6/math.sqrt(3),3),'nut_path_pass':True,'bottom_T_removed':True,'all_variants':m4_paths,'bolts_mm':[12,16,18],'board_mm':5}

''' +s[b:]
s=s.replace("试配件_M4双孔螺母座_孔距25","试配件_M4左右斜坡入口_孔距25")
# Keep the derived builder explicit and reproducible instead of eval-based patching at runtime.
(p/'build_v11.py').write_text(s,encoding='utf8')
print(p/'build_v11.py')
