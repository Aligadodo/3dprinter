from pathlib import Path
import ast,json
import numpy as np,trimesh
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).parent;ROOT=BASE/'releases/床头夹具_A_V1.2_等宽轻量_M4x12_十九盘';OLD=BASE/'releases/床头夹具_A_V1.1_左右斜坡螺母入口_十九盘'
meta=json.loads((ROOT/'技术资料/几何装配验证.json').read_text(encoding='utf8'))['meshes']
tree=ast.parse((BASE/'revision-a/build_examples.py').read_text(encoding='utf8'));exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='render'][-1:],type_ignores=[]),'render','exec'))
def restored(name):
 m=trimesh.load(ROOT/'单件STL'/(name+'.stl'));m.apply_translation(-np.array(meta[name]['print_translation']));m.apply_transform(np.linalg.inv(meta[name]['assembly_to_print_rotation']));return m
name='床头夹具_螺丝S_夹35-55_宽36';new=restored(name)
old=trimesh.load(OLD/'单件STL'/(name+'.stl'));old.apply_translation((-20.4,-15,-22));old.apply_transform(np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]))
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
im=Image.new('RGB',(1900,1300),'#f5f8fb');d=ImageDraw.Draw(im)
def text(x,y,s,n=26,c='#20374c'):d.text((x,y),s,font=font(n),fill=c)
text(40,25,'床头夹具 V1.2｜等宽轻量版',42)
text(40,90,'保留接口孔距与竖向孔位，消除前头加宽造成的主体悬空。',28)
text(50,175,'旧 V1.1：主体36 / 前头44',30)
text(995,175,'新 V1.2：前后全宽36',30)
render(d,[(old,(143,155,166))],(40,240,860,540),view=(-1,-1,.65))
render(d,[(new,(57,145,180))],(995,240,860,540),view=(-1,-1,.65))
text(65,815,'前臂14 · 前座20.4 · 顶梁14 mm',27)
text(1000,815,'前臂9.4 · 前座13.6 · 顶梁9.4 mm',27)
d.line((40,890,1855,890),fill='#c5d2dc',width=2)
text(50,925,'S 螺丝款：等宽36 / 40 / 44 mm；双孔间距25 mm保持。',29)
text(50,987,'H4 挂钩款：等宽48 / 50 / 54 mm；四钩40×40 mm保持。',29)
text(50,1049,'三档夹厚不变：20–40 / 35–55 / 50–70 mm；粗螺杆沿用原件。',28)
text(50,1111,'S款仅按M4×12设计：5 mm板、普通M4螺母、平底头、不加垫片。',28)
text(50,1180,'主体平侧面贴床；局部挂钩与内部孔槽仍保留自动支撑。',27)
text(50,1235,'几何减薄不等于已验证承重；新版需先打印小样并实物试装。',25,'#94642b')
im.save(ROOT/'图解/01_等宽轻量新旧对比.png')
im=Image.new('RGB',(1900,1100),'#f5f8fb');d=ImageDraw.Draw(im)
text(40,25,'V1.2 双接口｜孔距保持，边缘收窄',40)
h=restored('床头夹具_挂钩H4_夹35-55_宽48')
render(d,[(h,(57,145,180))],(40,155,840,580),view=(-1,-1,.5))
render(d,[(new,(57,145,180))],(1000,155,840,580),view=(-.5,-1,.25))
text(60,780,'H4：40×40孔位，圆角挂钩保留',29)
text(990,780,'S：左右侧入螺母槽保留',29)
text(60,845,'挂钩外侧至48 mm主体边缘约1.8 mm',25)
text(990,845,'M4×12尾端净余量2 mm',25)
text(60,920,'顶梁减薄后钩尖高出顶梁约4.6 mm；孔位相对家具顶面不下移。',27)
text(60,980,'板背距离随前部减薄而缩小；旧20.4 mm背部支撑块不能直接混配。',27)
im.save(ROOT/'图解/02_双接口与安装注意.png')
print('Rendered final STL comparisons.')
