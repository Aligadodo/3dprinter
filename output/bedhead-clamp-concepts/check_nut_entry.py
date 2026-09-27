from pathlib import Path
import ast,json,math,zipfile,hashlib
import xml.etree.ElementTree as E
import numpy as np,trimesh,manifold3d as md
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import Polygon

BASE=Path(__file__).parent;OUT=BASE/'nut-entry-check';OUT.mkdir(exist_ok=True)
ROOT=Path(r'E:/3dprint/自己设计合集/实用组件/床头夹具_A_V1_双接口_三档三宽_十九盘')
def solid(m):return md.Manifold(md.Mesh(np.asarray(m.vertices,np.float32),np.asarray(m.faces,np.uint32)))
def restore(m,w):
 m=m.copy();m.apply_translation((-20.4,-15,-max(w,44)/2));m.apply_transform(np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]));return m
def box(a,b):return md.Manifold.cube(np.subtract(b,a)).translate(a)
def mesh(s):
 m=s.to_mesh64();return trimesh.Trimesh(np.asarray(m.vert_properties)[:,:3],np.asarray(m.tri_verts),process=True)
h=[[7/math.sqrt(3)*math.cos(math.radians(i*60)),7/math.sqrt(3)*math.sin(math.radians(i*60))] for i in range(6)]
nut=md.CrossSection([h]).extrude(3.2).transform([[0,0,1,-17.2],[1,0,0,0],[0,1,0,0]])
rows=[]
for p in (ROOT/'单件STL').glob('*螺丝S*.stl'):
 w=int(p.stem.split('宽')[-1]);m=restore(trimesh.load(p),w);s=solid(m);vals=[]
 for z in np.linspace(-25,-1,49):vals.append((s^nut.translate((0,0,z))).volume())
 for y in np.linspace(-12.5,12.5,51):vals.append((s^nut.translate((0,y,-1))).volume())
 assert max(vals)<1e-5,(p.name,max(vals))
 rows.append({'file':p.name,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'nut_path_max_overlap_mm3':max(vals),'samples':len(vals)})
 if '35-55_宽44' in p.stem:chosen=m
# Verify the object in the shipped 3MF, independently of the builder and loose STL.
ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
with zipfile.ZipFile(ROOT/'床头夹具_A_V1_十九盘_P1S_PETG.3mf') as z:
 config=E.fromstring(z.read('Metadata/model_settings.config'))
 for o in config.findall('object'):
  name=o.find("metadata[@key='name']").get('value')
  if name=='床头夹具_螺丝S_夹35-55_宽44_01':
   cid=o.find('part').get('id');r=E.fromstring(z.read('3D/Objects/object_'+cid+'.model'))
   vv=np.array([[float(v.get(k)) for k in ('x','y','z')] for v in r.findall('.//m:vertex',ns)])
   ff=np.array([[int(v.get(k)) for k in ('v1','v2','v3')] for v in r.findall('.//m:triangle',ns)])
   # This plate's first object is translated +25,+25 in print XY.
   vv-=np.array([25,25,0]);s=solid(restore(trimesh.Trimesh(vv,ff,process=True),44))
   for zz in [-22,-17,-12,-6,-1]:assert (s^nut.translate((0,0,zz))).volume()<1e-5
   break
 else:raise RuntimeError('3MF object missing')
(OUT/'verification.json').write_text(json.dumps({'stl_variants':rows,'shipped_3mf_entrance_pass':True},ensure_ascii=False,indent=2),encoding='utf8')

# Depth-render final shipped mesh, looking up at the underside of the raised front seat.
tree=ast.parse((BASE/'revision-a/build_examples.py').read_text(encoding='utf8'))
exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render'][-1:],type_ignores=[]),'render','exec'))
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
im=Image.new('RGB',(1800,1120),'#f6f8fb');d=ImageDraw.Draw(im)
def txt(x,y,s,n=26,c='#20374c'):d.text((x,y),s,font=font(n),fill=c)
txt(40,25,'螺母入口在前部凸台的下沿中央',39)
txt(40,86,'核对的是已交付 V1 的最终 STL 和十九盘 3MF；入口确实存在。',25,'#536a7c')
cut=mesh(solid(chosen)^box((-21,-24,-30),(1,24,16)))
rect=(40,180,790,615);view=(-1,-1,-.7)
render(d,[(cut,(57,140,182))],rect,view=view)
# Recreate the projection for a precise leader attached to the opening centre.
fw=np.array(view,float);fw/=np.linalg.norm(fw);rt=np.cross([0,0,1],fw);rt/=np.linalg.norm(rt);up=np.cross(fw,rt);basis=np.array([rt,-up,fw])
pp=cut.vertices@basis.T;mi=pp[:,:2].min(0);ma=pp[:,:2].max(0);x,y,w,hh=rect;scale=min((w-2)/(ma[0]-mi[0]),(hh-2)/(ma[1]-mi[1]));offset=np.array([x,y])+(np.array([w,hh])-(ma-mi)*scale)/2-mi*scale
q=np.array([-15.7,0,-17])@basis.T;q=q[:2]*scale+offset
d.ellipse((q[0]-16,q[1]-16,q[0]+16,q[1]+16),outline='#e58225',width=5)
d.line([(q[0],q[1]),(650,840),(800,840)],fill='#e58225',width=4);txt(310,862,'从这个下沿槽口向上装入',25,'#a35e1e')
txt(945,170,'内部剖面：从正面沿螺母层切开',28)
section=chosen.section([1,0,0],[-15.6,0,0]);ox=1320;oy=400;k=12
for curve in section.discrete:
 pts=[(ox+v[1]*k,oy-v[2]*k) for v in curve]
 d.line(pts,fill='#287ba4',width=3)
def arrow(a,b):
 d.line([a,b],fill='#df8426',width=5)
 v=np.array(a)-np.array(b);v=v/np.linalg.norm(v);per=np.array([-v[1],v[0]])
 d.polygon([tuple(b),tuple(np.array(b)+v*17+per*9),tuple(np.array(b)+v*17-per*9)],fill='#df8426')
arrow((ox,oy+24*k),(ox,oy+3*k));arrow((ox,oy+1*k),(ox-12.5*k,oy+1*k));arrow((ox,oy+1*k),(ox+12.5*k,oy+1*k))
txt(1000,770,'先向上推入，再左右滑至螺丝孔后方',25)
txt(40,960,'使用普通 M4 六角螺母：对边7 mm、厚约3.2 mm。入口在局部凸台下沿，并非整只夹具最底端。',25)
txt(40,1020,'正面只看到两个圆形螺丝孔；此前俯视图没有展示这个入口，是图解说明不够清楚。',26)
im.save(OUT/'螺母入口_最终模型核查.png')
print('All nine S STL variants and the shipped 3MF entrance checked; annotated image saved.')
