from pathlib import Path
import ast,math
import numpy as np,trimesh,manifold3d as md
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).parent;ROOT=BASE/'releases'/'床头夹具_A_V1.1_左右斜坡螺母入口_十九盘'
tree=ast.parse((BASE/'revision-a/build_examples.py').read_text(encoding='utf8'))
exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render'][-1:],type_ignores=[]),'render','exec'))
m=trimesh.load(ROOT/'单件STL'/'床头夹具_螺丝S_夹35-55_宽44.stl')
m.apply_translation((-20.4,-15,-22));m.apply_transform(np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]))
solid=md.Manifold(md.Mesh(np.asarray(m.vertices,np.float32),np.asarray(m.faces,np.uint32)))
cut=solid^md.Manifold.cube((21,48,33)).translate((-21,-24,-17))
mm=cut.to_mesh();close=trimesh.Trimesh(np.asarray(mm.vert_properties)[:,:3],np.asarray(mm.tri_verts),process=True)
im=Image.new('RGB',(1900,1150),'#f6f8fb');d=ImageDraw.Draw(im)
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
def text(x,y,s,n=26,c='#20374c'):d.text((x,y),s,font=font(n),fill=c)
text(40,25,'V1.1｜左右侧斜坡入口 · 两颗螺母分别入位',40)
text(40,93,'全部9种螺丝款及M4试配件已更新；下方中央T形入口封闭。',27)
text(50,170,'最终模型：前座局部',28)
render(d,[(close,(58,141,182))],(45,235,780,570),view=(-1,-1,.5))
text(970,170,'螺母层剖面：左右各一条向内下倾的导槽',27)
ox,oy,k=1390,450,16
def pos(y,z):return (ox+y*k,oy-z*k)
for curve in m.section([1,0,0],[-15.6,0,0]).discrete:
 d.line([pos(v[1],v[2]) for v in curve],fill='#287ba4',width=4)
def arrow(a,b):
 d.line([a,b],fill='#e0872a',width=5);v=np.array(a)-np.array(b);v=v/np.linalg.norm(v);p=np.array([-v[1],v[0]])
 d.polygon([b,tuple(np.array(b)+v*20+p*10),tuple(np.array(b)+v*20-p*10)],fill='#e0872a')
for sign in [-1,1]:
 arrow(pos(sign*29,-1+math.tan(math.radians(15))*(29-12.5)),pos(sign*13,-1))
 pts=[pos(sign*12.5+7/math.sqrt(3)*math.cos(math.radians(60*i)),-1+7/math.sqrt(3)*math.sin(math.radians(60*i))) for i in range(7)]
 d.line(pts,fill='#e0872a',width=3)
text(1220,740,'内端止挡 / 中央隔开',25)
text(990,775,'橙色：螺母最终位置与装入方向',25,'#a35e1e')
text(50,875,'15°浅坡导向',30);text(660,875,'导槽厚4.0 mm',30);text(1250,875,'入口扩口约4.8 × 9 mm',30)
text(50,940,'普通M4：对边7 mm、厚约3.2 mm。先从左右侧装入，再对齐孔位拧入螺丝。',28)
text(50,1003,'浅坡便于轻推定位；能否自重滑入取决于摩擦，不承诺自动滑到底。',26)
text(50,1065,'保持工程内侧放方向及自动支撑，清理导槽后先打印试配；尚未实物验证。',25,'#826132')
im.save(ROOT/'图解'/'03_左右斜坡螺母入口.png')
