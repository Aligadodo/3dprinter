from pathlib import Path
import ast,json,math,hashlib
import numpy as np
import trimesh
import manifold3d as md
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).parent
OUT=ROOT/'概念网格_未定型';OUT.mkdir(exist_ok=True)
def manifold(m):return md.Manifold(md.Mesh(np.asarray(m.vertices,dtype=np.float32),np.asarray(m.faces,dtype=np.uint32)))
def mesh(s):
 m=s.simplify(.002).to_mesh64();out=trimesh.Trimesh(np.asarray(m.vert_properties)[:,:3],np.asarray(m.tri_verts),process=True);out.update_faces(out.nondegenerate_faces());out.remove_unreferenced_vertices();return out
def box(a,b):return md.Manifold.cube(np.subtract(b,a)).translate(a)
def cyl(r,h):return md.Manifold.cylinder(h,r,r,64)
source_screw=trimesh.load(ROOT/'reference-screw.stl')
source_clamp=trimesh.load(ROOT/'reference-clamp.stl')
ms=manifold(source_screw);mc=manifold(source_clamp)
# Keep the actual original thread flank geometry. Remove 5 mm at the shaft root.
# A 10 mm section of the original knob is translated to meet that shorter shaft.
shaft=ms^box((-30,-30,-7.5),(30,30,28))
knob=(ms^box((-30,-30,-27.5),(30,30,-17.5))).translate((0,0,10))
short_screw=shaft+knob
assert short_screw.status()==md.Error.NoError
sm=mesh(short_screw);sm.export(OUT/'共用粗螺杆_总长45_杆身35_旋钮10_概念.stl')
assert sm.is_watertight and abs(sm.extents[2]-45)<.01
# Extract the female thread along with its original surrounding material.
# Its axis is approximately (13.65,0), based on sections of the actual archive mesh.
axis=13.65;rear=10.65
female=mc^cyl(11.7,rear).translate((axis,0,-30))
fm=mesh(female);fm.export(ROOT/'extracted-female-thread.stl')
assert fm.is_watertight
W=44;variants=[('A20-40',20,40,30),('A35-55',35,55,45),('A50-70',50,70,60)]
assemblies={};report=[]
for name,tmin,tmax,t in variants:
 G=tmax+3 # 1 mm front pad + tmax + 2 mm insertion margin
 frame=box((-14,-W/2,-45),(0,W/2,15))+box((-14,-W/2,1),(G+rear,W/2,15))+box((G,-W/2,-45),(G+rear,W/2,15))
 hole=cyl(11.7,rear+2).rotate((0,90,0)).translate((G-1,0,-23))
 # z_old -> -x_new; x_old -> z_new. Preserve the female flank mesh.
 sleeve=female.transform([[0,0,-1,G-19.35],[0,1,0,0],[1,0,0,-23-axis]])
 frame=(frame-hole)+sleeve
 # Front cheek remains 14 mm. Only the hook region widens to fit the illustrative grid.
 front=box((-14,-27,-45),(0,27,15))
 hooked=frame+front
 for y in [-20,20]:
  for tip in [15,-25]:
   hooked=hooked+box((-23,y-2.6,tip-10),(-13.5,y+2.6,tip-6))+box((-23,y-2.6,tip-10),(-19.5,y+2.6,tip))
 # Screw-interface version uses the previous 20.4 mm total front thickness.
 screwface=frame+box((-20.4,-22,-17),(0,22,15))
 for y in [-12.5,12.5]:
  bore=md.Manifold.cylinder(18,2.2,2.2,32).rotate((0,90,0)).translate((-21,y,-1))
  pocket=md.Manifold.cylinder(3.6,7.3/math.sqrt(3),7.3/math.sqrt(3),6).rotate((0,90,0)).translate((-17.4,y,-1))
  entry=box((-17.4,min(0,y)-3.8,-4.8),(-13.8,max(0,y)+3.8,2.8))
  screwface=screwface-bore-pocket-entry
 screwface=screwface-box((-17.4,-4.3,-17.1),(-13.8,4.3,2.8))
 models={}
 for suffix,s in [('H4',hooked),('S',screwface)]:
  m=mesh(s);assert m.is_watertight and s.status()==md.Error.NoError,(name,suffix,s.status())
  m.export(OUT/(name+'_'+suffix+'_概念.stl'));models[suffix]=m
 wood=mesh(box((1,-54,-104),(1+t,54,0)))
 pad=mesh(box((0,-21,-44),(1,21,0))+box((0,-21,0),(15,21,1)))
 tipx=1+t
 bolt=mesh(short_screw.transform([[0,0,-1,tipx+27.5],[1,0,0,0],[0,-1,0,-23]]))
 assemblies[name]=(models,bolt,wood,pad,G,t)
 for tt in [tmin,tmax]:
  gap=tmax-tt+2
  clearance=35-gap-rear
  assert clearance>=2.3
  report.append({'variant':name,'board_thickness':tt,'gap_to_rear_cheek':gap,'female_thread_axial_depth':rear,'knob_clearance':round(clearance,3),'board_back_to_knob_end':45,'effective_opening':G-1})

meta={'source_screw_total':55,'source_shaft':40,'source_knob':15,'measured_major_diameter_approx':15.38,'source_pitch_approx':4,'compact_screw_total':45,'compact_shaft':35,'compact_knob':10,'front_arm_thickness':14,'screw_interface_total_thickness':20.4,'frame_width':44,'hook_interface_width_illustrative':54,'hook_tip_top_z':15,'beam_top_z':15,'thread_pair_fit':'original female and male geometry reused; shortened shaft phase fit and print tolerances not yet validated','endpoint_clearance_checks':report}
(ROOT/'geometry-measurements.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf8')

# Engineering drawings from the generated meshes; no image synthesis or source-photo edits.
tree=ast.parse(Path('output/skadis-corner-support/build_print_kit.py').read_text(encoding='utf8'))
exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render'],type_ignores=[]),'render-helper','exec'))
# Exact per-pixel depth buffering avoids painter-order artifacts on large frame faces.
def render(d,objects,rect,view=(1,-.6,.8)):
 forward=np.asarray(view,float);forward/=np.linalg.norm(forward)
 right=np.cross([0,0,1],forward);right/=np.linalg.norm(right)
 up=np.cross(forward,right);basis=np.array([right,-up,forward])
 allp=[m.vertices@basis.T for m,c in objects];pp=np.vstack(allp);mi=pp[:,:2].min(0);ma=pp[:,:2].max(0)
 x0,y0,w,h=map(int,rect);scale=min((w-2)/(ma[0]-mi[0]),(h-2)/(ma[1]-mi[1]));offset=(np.array([w,h])-(ma-mi)*scale)/2-mi*scale
 canvas=np.empty((h,w,3),dtype=np.uint8);canvas[:]=(246,248,251);depth=np.full((h,w),-np.inf)
 for (m,color),p in zip(objects,allp):
  screen=p[:,:2]*scale+offset
  for f,n in zip(m.faces,m.face_normals):
   if n@forward<=1e-7:continue
   a,b,c=screen[f];z=p[f,2]
   xmin=max(0,int(np.floor(min(a[0],b[0],c[0]))));xmax=min(w-1,int(np.ceil(max(a[0],b[0],c[0]))))
   ymin=max(0,int(np.floor(min(a[1],b[1],c[1]))));ymax=min(h-1,int(np.ceil(max(a[1],b[1],c[1]))))
   if xmax<xmin or ymax<ymin:continue
   den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
   if abs(den)<1e-10:continue
   yy,xx=np.mgrid[ymin:ymax+1,xmin:xmax+1];xx=xx+.5;yy=yy+.5
   u=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
   v=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;wgt=1-u-v
   zz=u*z[0]+v*z[1]+wgt*z[2];region=depth[ymin:ymax+1,xmin:xmax+1]
   mask=(u>=-1e-7)&(v>=-1e-7)&(wgt>=-1e-7)&(zz>region)
   region[mask]=zz[mask]
   shade=.63+.25*max(0,float(n@forward))+.12*max(0,float(n[2]));col=np.clip(np.asarray(color)*shade,0,255).astype(np.uint8)
   canvas[ymin:ymax+1,xmin:xmax+1][mask]=col
 im.paste(Image.fromarray(canvas),(x0,y0))
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
im=Image.new('RGB',(2100,1570),'#f6f8fb');d=ImageDraw.Draw(im)
def txt(x,y,s,n=24,c='#203249'):d.text((x,y),s,font=font(n),fill=c)
txt(48,30,'A 改进示例：高位挂口 · 薄前臂 · 分档夹体 · 共用粗螺杆',39)
txt(48,95,'前臂 14 mm ｜ 螺丝座总厚 20.4 mm ｜ 取消独立压板及防退件 ｜ 蓝色为夹体，橙色为螺杆',25,'#52677d')
for i,(name,lo,hi,t) in enumerate(variants):
 x=42+i*694
 txt(x,161,f'{name}  /  {lo}–{hi} mm',30)
 txt(x,207,f'图示板厚 {t} mm · 有效净口 {hi+2} mm',24,'#52677d')
 models,bolt,wood,pad,G,_=assemblies[name]
 render(d,[(wood,(220,205,180)),(models['H4'],(54,137,182)),(bolt,(230,151,63)),(pad,(92,145,119))],(x+8,258,615,475),view=(-1,-1,.75))
 txt(x,750,'上排钩尖与顶梁上表面齐平',23)
 # Side section with a constant scale across all variants.
 k=3.6;ox=x+155;oy=875
 def pt(xp,z):return (ox+xp*k,oy-z*k)
 def rect(a,b,fill):d.rectangle([pt(a[0],b[1]),pt(b[0],a[1])],fill=fill)
 rect((1,-75),(1+t,0),'#d9c9ad')
 rect((-14,-45),(0,15),'#358abc');rect((-14,1),(G+rear,15),'#358abc');rect((G,-45),(G+rear,1),'#358abc')
 rect((0,-44),(1,0),'#668c75')
 rect((1,0),(15,1),'#668c75')
 for tip in [15,-25]:rect((-23,tip-10),(-13.5,tip-6),'#358abc');rect((-23,tip-10),(-19.5,tip),'#358abc')
 rect((1+t,-30.7),(1+t+35,-15.3),'#df953d');rect((1+t+35,-35.5),(1+t+45,-10.5),'#d77f28')
 for xx in np.arange(1+t+1,1+t+35,4):d.line([pt(xx,-30.7),pt(xx-1.5,-15.3)],fill='#aa601f',width=2)
 d.line([pt(-26,15),pt(G+rear+8,15)],fill='#8fa3b4',width=2)
 a,b=pt(1+t,-58),pt(1+t+45,-58);d.line([a,b],fill='#354b60',width=2)
 for p in [a,b]:d.line([(p[0],p[1]-6),(p[0],p[1]+6)],fill='#354b60',width=2)
 txt((a[0]+b[0])/2-78,a[1]+7,'背后占用 45 mm',22)
 txt(x+44,1200,f'前后开口按板厚分档；螺杆不随型号加长',22,'#52677d')
txt(48,1280,'同一夹体保留两种前接口：H4 四挂钩 / S 螺丝定位',31)
txt(48,1330,'H4：挂钩直接靠近顶梁，取消长下垂连接段；孔距仅示意，后续按实际洞洞板匹配。',25)
txt(48,1376,'S：连接孔同步上移，局部安装座沿用 20.4 mm 总厚；未增加整体前部厚度。',25)
txt(48,1430,'共用短杆：原牙型保留，杆身 40→35 mm，旋钮 15→10 mm，总长 55→45 mm。',25)
txt(48,1502,'概念网格示例 · 已检查封闭网格与端点旋钮间隙 · 尚未验证螺纹试配、打印和承重',22,'#90652c')
im.save(ROOT/'A改进_三档整体示例.png')

im=Image.new('RGB',(1800,1050),'#f6f8fb');d=ImageDraw.Draw(im)
txt(40,25,'前接口与粗螺杆复用方式',38)
models,bolt,wood,pad,G,t=assemblies['A35-55']
txt(40,90,'H4 / 单夹具四挂钩',28);render(d,[(models['H4'],(54,137,182)),(bolt,(230,151,63))],(30,155,580,560),view=(-1,-1,.55))
txt(625,90,'S / 高位双孔定位',28);render(d,[(models['S'],(54,137,182)),(bolt,(230,151,63))],(625,155,580,560),view=(-1,-1,.55))
txt(1230,90,'原杆 55 / 共用短杆 45 mm',26)
render(d,[(source_screw,(130,150,166))],(1240,170,200,490),view=(1,-1,.4))
render(d,[(sm,(230,151,63))],(1480,270,220,390),view=(1,-1,.4))
txt(40,765,'上排挂口直接并入顶部区域；前臂14 mm，螺丝接口局部总厚20.4 mm。',26)
txt(40,815,'螺杆和旋钮取自样例网格；配套内螺纹整段提取后并入后夹臂，保留原牙型。',26)
txt(40,865,'短杆只是统一缩短，不按夹体型号另配长度。粗螺杆端面直接顶板，不再有活动挡板。',26)
txt(40,927,'样例杆实测：牙顶直径约15.38 mm，螺距约4 mm；不把它当作标准M16螺纹。',23,'#52677d')
txt(40,982,'孔位及挂钩装配路径未定型；缩短后的螺纹配合还需验证。',22,'#90652c')
im.save(ROOT/'A改进_双接口与原件复用.png')
print(json.dumps(meta,ensure_ascii=False))
