from pathlib import Path
import ast,math
import numpy as np,trimesh,manifold3d as md
from shapely.geometry import Polygon,box
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).parent
R=BASE/'releases'/'MSkadis挂架_V3.1_双侧斜坡螺母入口_十一盘'
tree=ast.parse((BASE/'build_print_kit.py').read_text(encoding='utf8'))
exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['render','mesh']],type_ignores=[]),'<render>','exec'))
m=trimesh.load_mesh(R/'单件STL'/'挂架_顶臂60_下垂90_标准版.stl');m.apply_translation([-60,-14,-22])
section=m.section(plane_origin=[15.6,0,0],plane_normal=[1,0,0])
polys=[Polygon(p[:,[2,1]]).intersection(box(-22,65,22,90)) for p in section.discrete]
polys=[p for p in polys if not p.is_empty and p.area>1e-6]
im=Image.new('RGB',(1800,1220),'#f5f7fa');d=ImageDraw.Draw(im)
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
def txt(x,y,t,n=26,c='#23374a'):d.text((x,y),t,font=font(n),fill=c)
txt(45,25,'螺母从左右两侧进入，沿缓坡滑向各自孔位',38)
txt(45,90,'六种挂架使用同一入口；普通M4螺母，对边7 mm、厚约3.2 mm。',26)
txt(70,172,'正面剖视 · 显示螺母槽内部',28)
scale=19;xy=lambda z,y:(100+(z+22)*scale,250+(y-65)*scale)
for p in sorted(polys,key=lambda p:p.area,reverse=True):
    geoms=[p] if p.geom_type=='Polygon' else list(p.geoms)
    for poly in geoms:
        d.polygon([xy(a,b) for a,b in poly.exterior.coords],fill='#e5b54e',outline='#ba8730')
        for ring in poly.interiors:d.polygon([xy(a,b) for a,b in ring.coords],fill='#f5f7fa')
for side in [-1,1]:
    a=np.array(xy(side*21,74.5));b=np.array(xy(side*12.5,77.5));delta=(b-a)/np.linalg.norm(b-a);normal=np.array([-delta[1],delta[0]])
    d.line([tuple(a),tuple(b)],fill='#227d78',width=6)
    d.polygon([tuple(b),tuple(b-delta*19+normal*10),tuple(b-delta*19-normal*10)],fill='#227d78')
    cx,cy=xy(side*12.5,77.5);d.ellipse((cx-22,cy-22,cx+22,cy+22),outline='#315f89',width=3)
    txt(80 if side<0 else 790,750,'左侧入口' if side<0 else '右侧入口',24)
txt(365,810,'底面封闭 · 中央保留实体',25)
txt(1080,172,'下部安装座 · 实际模型局部',28)
solid=md.Manifold(md.Mesh(m.vertices.astype(np.float32),m.faces.astype(np.uint32)))
cut=solid ^ md.Manifold.cube((22,27,44)).translate((0,63,-22))
cutm=mesh(cut)
vv,ff=trimesh.remesh.subdivide_to_size(cutm.vertices,cutm.faces,max_edge=2)
cutm=trimesh.Trimesh(vv,ff,process=False)
centers=cutm.triangles_center
inside=(centers[:,0]>13.59)&(centers[:,0]<17.61)&(centers[:,1]>67)&(centers[:,1]<84)&(np.abs(centers[:,2])>8)
outer=cutm.submesh([np.where(~inside)[0]],append=True)
inner=cutm.submesh([np.where(inside)[0]],append=True)
for part in [outer,inner]:part.apply_transform(np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]))
render(d,[(outer,(231,177,66)),(inner,(106,81,36))],(1030,245,690,490),view=(1,1,.55))
txt(1060,775,'槽厚 4.0 mm｜导槽对边 7.5 mm',25)
txt(1060,820,'中心导向坡度约17.5°',25)
txt(45,920,'1  对齐侧口',29);txt(620,920,'2  顺坡滑向孔位',29);txt(1210,920,'3  从板正面拧入螺丝',29)
txt(45,978,'让螺母平面与槽壁平行，',23);txt(45,1017,'左右分别装入。',23)
txt(620,978,'可轻推或稍倾斜挂架辅助；',23);txt(620,1017,'先清除打印毛刺。',23)
txt(1210,978,'对准螺母后先手拧带住，',23);txt(1210,1017,'确认板已压紧。',23)
txt(45,1110,'坡道用于辅助导向，尚未实测自行滑入效果；不用敲击硬装。',25,c='#a44828')
txt(45,1155,'M4×16优先；12／18 mm按有效板厚5 mm核对。主体宽44、臂厚14、底座厚20.4 mm。',24)
im.save(R/'图解'/'03_双侧斜坡螺母装入.png')
print('Saved nut entry diagram')
