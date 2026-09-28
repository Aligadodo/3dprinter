from pathlib import Path
import ast,json,math
import numpy as np,trimesh,manifold3d as md
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).parent;ROOT=BASE/'releases/床头夹具_A_V1.3_斜面防滑_多长度螺杆_二十盘'
report=json.loads((ROOT/'技术资料/几何装配验证.json').read_text(encoding='utf8'));meta=report['meshes']
tree=ast.parse((BASE/'revision-a/build_examples.py').read_text(encoding='utf8'));exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render'][-1:],type_ignores=[]),'render','exec'))
def restored(name):
 m=trimesh.load(ROOT/'单件STL'/(name+'.stl'));m.apply_translation(-np.array(meta[name]['print_translation']));m.apply_transform(np.linalg.inv(meta[name]['assembly_to_print_rotation']));return m
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
def text(x,y,s,n=26,c='#20374c'):d.text((x,y),s,font=font(n),fill=c)
im=Image.new('RGB',(1900,1150),'#f5f8fb');d=ImageDraw.Draw(im)
text(40,25,'V1.3｜固定夹板微倾、圆底齿槽、圆润自由端',39)
text(40,90,'内接触面向夹口倾1.5°，外侧孔位保持；沿侧面轮廓圆角，左右宽度不变。',27)
m=restored('床头夹具_螺丝S_夹35-55_宽36')
render(d,[(m,(56,143,178))],(40,190,900,620),view=(1,-1,.65))
s=md.Manifold(md.Mesh(np.asarray(m.vertices,np.float32),np.asarray(m.faces,np.uint32)))
cut=s^md.Manifold.cube((20,40,60)).translate((-15,-20,-46));mm=cut.to_mesh64();close=trimesh.Trimesh(np.asarray(mm.vert_properties)[:,:3],np.asarray(mm.tri_verts),process=True)
render(d,[(close,(56,143,178))],(1030,190,760,620),view=(1,-1,.25))
text(50,850,'整体：保持等宽轻量主体',28)
text(1040,850,'局部：短5 mm＋14道浅槽＋R3.3',27)
text(50,930,'齿槽节距2.5 mm，圆底R0.6，名义深度0.35 mm；不做尖锐咬齿。',28)
text(50,995,'自由端名义内收约1.01 mm；三档原夹持范围已按剩余开口复核。',27)
text(50,1060,'齿槽为增加摩擦的设计意图，尚未实测；漆面家具仍建议使用薄保护垫。',25,'#94642b')
im.save(ROOT/'图解/01_斜面齿槽与圆角.png')
im=Image.new('RGB',(1900,1230),'#f5f8fb');d=ImageDraw.Draw(im)
text(40,25,'第20盘｜P10 / P20 / P30 / P40 / P50 五种粗螺杆',38)
text(40,91,'P＝最大工作伸入量：从后夹臂内侧量至杆端，且手轮离后臂至少2 mm。',27)
scene=[]
for i,info in enumerate(report['assembly']['extra_screws']):
 m=trimesh.load(ROOT/'单件STL'/(info['name']+'.stl'));m.apply_translation((-12.5+i*40,-12.41,0));scene.append((m,(213,146,73)))
render(d,scene,(50,170,1800,620),view=(0,-1,.1))
for i,info in enumerate(report['assembly']['extra_screws']):
 x=60+i*370;text(x,845,info['engraved'],34);text(x,905,f'伸入上限 {info["max_working_projection_mm"]} mm',25)
 text(x,950,f'杆身 {info["shaft_mm"]:.1f} mm',25);text(x,995,f'总长 {info["total_mm"]:.1f} mm',25)
text(45,1080,'每件独立命名，旋钮底面刻P编号；现有35 mm杆身粗螺杆继续保留。',27)
text(45,1140,'P不是可夹板厚，也不是机械止挡。短夹口用长杆时，先确认杆端不会顶到固定夹板。',24,'#94642b')
im.save(ROOT/'图解/02_五种螺杆尺寸.png')
# Actual underside marking, rendered from the exported mesh.
im=Image.new('RGB',(850,800),'#f5f8fb');d=ImageDraw.Draw(im)
info=report['assembly']['extra_screws'][0];m=trimesh.load(ROOT/'单件STL'/(info['name']+'.stl'))
text(35,20,'旋钮底面刻字：P10',32)
m.apply_transform(trimesh.transformations.rotation_matrix(math.pi,[0,0,1],point=m.centroid))
render(d,[(m,(213,146,73))],(60,100,730,640),view=(.05,-.45,-1))
im.save(ROOT/'图解/03_旋钮底面编号.png')
print('Rendered jaws, five lengths and actual engraving.')
