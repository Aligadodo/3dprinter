from pathlib import Path
import ast,math,json
import numpy as np,trimesh,manifold3d as md
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).parent;ROOT=BASE/'releases'/'床头夹具_A_V1.1_左右斜坡螺母入口_十九盘'
tree=ast.parse((BASE/'revision-a'/'build_examples.py').read_text(encoding='utf8'))
fn=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render'][-1:]
exec(compile(ast.Module(fn,type_ignores=[]),'render','exec'))
def restored(kind,w=44):
 m=trimesh.load(ROOT/'单件STL'/f'床头夹具_{kind}_夹35-55_宽{w}.stl')
 m.apply_translation((-22.8 if kind=='挂钩H4' else -20.4,-15,-max(w,54 if kind=='挂钩H4' else 44)/2))
 m.apply_transform(np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]));return m
def screw(t=45):
 m=trimesh.load(ROOT/'单件STL'/'共用粗螺杆_杆35_旋钮10_总长45.stl');m.apply_translation((-12.5,-12.4099998,-17.5))
 G=58;gap=G-(1+t);delta=gap-46.85;angle=180+90*(delta+37.5)
 m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(angle),[0,0,1]));m.apply_translation((0,0,delta))
 m.apply_transform(np.array([[0,0,-1,G-19.35],[0,1,0,0],[1,0,0,-23],[0,0,0,1]]));return m
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
im=Image.new('RGB',(2000,1450),'#f6f8fb');d=ImageDraw.Draw(im)
def text(x,y,s,n=25,c='#20374c'):d.text((x,y),s,font=font(n),fill=c)
text(45,30,'床头夹具 A V1.1｜双接口 · 三档厚度 · 三种宽度',42)
text(45,94,'18 种主体，一对夹具＋两根共用粗螺杆各自成盘；另有一盘接口试配件。',28,'#52677d')
text(60,170,'H4 挂钩款：四钩圆角导入',32)
text(1040,170,'S 螺丝款：高位双孔＋内置螺母槽',32)
h=restored('挂钩H4');s=restored('螺丝S');b=screw()
render(d,[(h,(58,141,182)),(b,(231,149,63))],(55,240,860,615),view=(-1,-1,.58))
render(d,[(s,(58,141,182)),(b,(231,149,63))],(1040,240,860,615),view=(-1,-1,.58))
text(65,900,'挂钩宽 4.4 mm / 孔位 40×40 mm',26)
text(65,945,'钩尖横向 R2.2，侧面轮廓 R0.55',26)
text(65,990,'适配样例 5 mm 板；套入后下落约7.2 mm',25)
text(1050,900,'孔径 4.4 mm / 孔距25 mm / 座厚20.4 mm',26)
text(1050,945,'左右侧分别装入M4螺母，沿15°坡轻推定位',26)
text(1050,990,'5 mm板优先M4×16；也验证了12/18 mm',25)
d.line((45,1065,1940,1065),fill='#c4cfd7',width=2)
text(60,1100,'夹持范围：20–40 / 35–55 / 50–70 mm',30)
text(60,1155,'主体宽度：36 / 44 / 60 mm（接口局部可加宽）',28)
text(60,1210,'统一：前臂14 mm，共用螺杆总长45 mm；原牙型螺距4 mm。',28)
text(60,1265,'打印：P1S / PETG / 0.20 mm / 6墙 / 50%填充；螺杆100%填充。',26)
text(60,1317,'主体侧放，已启用自动支撑；先打印第01盘，清理挂钩与螺口毛刺后试装。',26)
text(60,1388,'无防上抬锁扣、无螺杆防退锁；尚无实物承重及长期夹紧验证。',23,'#986d34')
im.save(ROOT/'图解'/'01_双接口与全尺寸.png')

# Hook close-up is rendered from the final exported part, not a conceptual redraw.
mh=md.Manifold(md.Mesh(np.asarray(h.vertices,np.float32),np.asarray(h.faces,np.uint32)))
cut=mh^md.Manifold.cube((12,12,16)).translate((-24,14,2))
mm=cut.to_mesh();close=trimesh.Trimesh(np.asarray(mm.vert_properties)[:,:3],np.asarray(mm.tri_verts),process=True)
im=Image.new('RGB',(1400,900),'#f6f8fb');d=ImageDraw.Draw(im)
text(40,25,'挂钩圆角与安装顺序',38)
render(d,[(close,(58,141,182))],(50,130,610,560),view=(-1,-1,.6))
for j,line in enumerate(['① 对齐四个长孔，将板套入','② 洞洞板向下落约7.2 mm','③ 确认四钩都进入承托位置','④ 拆卸：先托住板，向上抬起','⑤ 再向外取下，不能直接强拉']):text(710,170+j*78,line,26)
text(45,735,'每侧约0.4 mm孔宽间隙；喉口5.8 mm，样例板厚5 mm。',27)
text(45,798,'当前按要求未设置防上抬卡扣；取放收纳件时避免把整块板向上顶起。',24,'#986d34')
im.save(ROOT/'图解'/'02_圆角挂钩与安装.png')
print(ROOT/'图解')
