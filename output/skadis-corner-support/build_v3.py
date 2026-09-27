"""V2 prototype: two part families, measured ModelB interfaces. mm."""
from pathlib import Path
import ast, json, math, zipfile, copy, shutil, hashlib
import xml.etree.ElementTree as E
import numpy as np
import trimesh
import manifold3d as md
from shapely.geometry import Polygon, Point, box, LineString
from shapely.ops import unary_union
from shapely.geometry.polygon import orient
from PIL import Image, ImageDraw, ImageFont

BASE=Path(__file__).parent
ROOT=BASE/'releases'/'MSkadis挂架_V3.0_统一规格_十一盘'
STL=ROOT/'单件STL'
for p in [STL,ROOT/'单盘工程',ROOT/'技术资料',ROOT/'图解']:p.mkdir(parents=True,exist_ok=True)
PARTS={};REPORT={};ASSEMBLY={}
# Reuse only pure geometry/serialization helpers, never execute the V1 build.
tree=ast.parse((BASE/'build_print_kit.py').read_text(encoding='utf8'))
names={'solid','roundbox','bore_x','mesh','normalize','save','footprint','render'}
exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'<geometry helpers>','exec'))
W=44.;T=20.4;D=4.4;PITCH=25.
VARIANTS={'S':(60,90,14),'M':(90,90,14),'L':(120,90,14),'S短':(60,65,14),'M短':(90,65,14),'L短':(120,65,14)}
LABEL={};CHECKS={}

def cube(size,at):return md.Manifold.cube(size).translate(at)
def bore_y(y0,length,x,z,d):
    return solid(Point(0,0).buffer(d/2,quad_segs=24),length).transform([[1,0,0,x],[0,0,1,y0],[0,-1,0,z]])

for ch,(arm,drop,t) in VARIANTS.items():
    h=drop-12.5
    outline=unary_union([box(-arm,-t,t,0),box(0,-t,t,drop),
        Polygon([(t,-t),(t+7,0),(t,21)]),box(0,drop-25,T,drop),
        Polygon([(t,drop-40),(T,drop-25),(t,drop-25)])])
    outline=outline.difference(Point(0,0).buffer(1.0,quad_segs=20))
    s=solid(outline,W,-W/2)
    # Blind tip clearance leaves 4.4 mm behind the bore, including at the furniture face.
    for z in [-12.5,12.5]:
        s=s-bore_x(4.4,17,h,z,D)-bore_x(13.8,3.6,h,z,7.3,True)
    # Two nuts share a central loading opening from the bottom, then slide left/right.
    s=s-cube((3.6,7.5,25),(13.8,h-3.75,-12.5))
    s=s-cube((3.6,16.3,8.6),(13.8,h-3.75,-4.3))
    # Two opposing blind sockets; retain a 19.6 mm central web.
    for z0 in [-22.1,9.8]:
        s=s-cube((24.4,4.4,12.3),(-46.2,-t/2-2.2,z0))
    # Uninterrupted top contact face for user-selected anti-slip/adhesive attachment.
    ASSEMBLY[ch]=s
    name=f'挂架_顶臂{arm}_下垂{drop}_'+('标准版' if drop==90 else '短版')
    LABEL[ch]=name
    save(name,s)
    # Probe the real boolean result with bolts, and verify cabinet-side thickness.
    lengths={}
    for L in [12,16,18]:
        tip=T+5-L
        collision=(s ^ bore_x(tip,L,h,12.5,4.0)).volume()
        assert collision<1e-6,(ch,L,collision)
        lengths[str(L)]={'tip_x':tip,'clearance_to_blind_bottom':tip-4.4,'bolt_solid_interference_mm3':collision}
    CHECKS[ch]={'board_screws':lengths,'hole_centers':[[-12.5,h],[12.5,h]],'front_face_from_furniture':T,'nut_pocket_from_front':[3,6.6]}
    nut=bore_x(14,3.2,0,0,7,True)
    for yy,zz in [(yy,0) for yy in np.linspace(drop+5,h,40)]+[(h,zz) for zz in np.linspace(-12.5,12.5,51)]:
        assert (s ^ nut.translate((0,yy,zz))).volume()<1e-6,(ch,'nut insertion',yy,zz)
    CHECKS[ch]['nominal_M4_nut_insertion_path_pass']=True

for bw in [200,220,240,260,280]:
    # Local x spans between bracket centers; y is the top-arm depth.
    # 0.2 mm shoulder clearance at each bracket; tongues overlap each bracket 12 mm.
    s=solid(box(22.2,-48,bw-22.2,-20),6)
    tongue=Polygon([(10,-45),(11,-46),(22.4,-46),(22.4,-22),(11,-22),(10,-23)])
    s=s+solid(tongue,4)+solid(Polygon([(bw-x,y) for x,y in tongue.exterior.coords]),4)
    name=f'连接板_适配板宽{bw}_总长{bw-20}'
    LABEL[bw]=name;ASSEMBLY[bw]=s
    save(name,s)
    # Map rail x->bracket width, rail y->top arm, rail z->upwards.
    for ch,(_,_,t) in VARIANTS.items():
        rail=s.transform([[0,1,0,0],[0,0,-1,-t/2+2],[1,0,0,0]])
        left=ASSEMBLY[ch];right=left.translate((0,0,bw))
        assert (rail^left).volume()<1e-6 and (rail^right).volume()<1e-6
        # Approach from the open sides: slide the brackets onto the fixed rail.
        for delta in np.linspace(0,14,40):
            assert (rail ^ left.translate((0,0,-delta))).volume()<1e-6
            assert (rail ^ right.translate((0,0,delta))).volume()<1e-6
        # Two rails on a middle bracket occupy separate sockets.
        previous=rail.translate((0,0,-bw))
        assert (previous ^ rail).volume()<1e-6
        assert (previous ^ left).volume()<1e-6
    CHECKS[str(bw)]={'center_pitch':bw,'clear_body_length':bw-44.4,'overall_length':bw-20,'shoulder_clearance_each':.2,'insertion_each':12,'socket_depth':12.2,'tongue_section':[24,4],'socket_section':[24.4,4.4],'insertion_path_pass':True,'assembly_interference_mm3':0}

# Extract B4 + B2 mesh measurements from the original archive for reproducibility.
source=Path(r'E:/3dprint/模型收藏合集/宜家洞洞板系列收藏/ModelB.3mf')
ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
measurement={}
with zipfile.ZipFile(source) as z:
    for label,filename in [('B4','3D/Objects/object_3.model'),('B2','3D/Objects/object_2.model')]:
        r=E.fromstring(z.read(filename));v=np.array([[float(a.get(k)) for k in ['x','y','z']] for a in r.findall('.//m:vertex',ns)])
        f=np.array([[int(a.get(k)) for k in ['v1','v2','v3']] for a in r.findall('.//m:triangle',ns)])
        m=trimesh.Trimesh(v,f);sec=m.section(plane_origin=[0,0,0],plane_normal=[0,0,1])
        holes=[]
        for a in sec.discrete:
            ext=a.max(0)-a.min(0)
            if np.allclose(ext[:2],[4.4,4.4],atol=.015):holes.append({'center':a.min(0)[:2].tolist() if False else ((a.max(0)+a.min(0))/2)[:2].tolist(),'diameters':ext[:2].tolist()})
        measurement[label]={'archive_member':filename,'thickness':float(m.extents[2]),'holes':holes}
        assert len(holes)==(4 if label=='B4' else 2)
        assert abs(m.extents[2]-20.4)<.01
measurement['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
(ROOT/'技术资料'/'ModelB实测.json').write_text(json.dumps(measurement,ensure_ascii=False,indent=2),encoding='utf8')

# Bambu project writer from V1, using independent objects with Chinese names.
OLD=BASE/'print-kit-v1';SET=json.loads((OLD/'P1S-PETG-settings.json').read_text(encoding='utf8'))
SET['print_settings_id']='V3_PETG_0.20_6walls_50pct';SET['enable_support']='0'
C='http://schemas.microsoft.com/3dmanufacturing/core/2015/02';P='http://schemas.microsoft.com/3dmanufacturing/production/2015/06';B='http://schemas.bambulab.com/package/2021'
E.register_namespace('',C);E.register_namespace('p',P);Tg=lambda s:'{'+C+'}'+s
# V1 writer expects T as a tag function.
T=Tg
I='1 0 0 0 1 0 0 0 1 0 0 0'
def meta(o,k,v):E.SubElement(o,'metadata',key=k,value=str(v))
def xml(o):return E.tostring(o,encoding='utf-8',xml_declaration=True)
tree=ast.parse((BASE/'build_release_v1.py').read_text(encoding='utf8').replace('洞洞板挂架 V1.0 独立零件','洞洞板挂架 V3.0 统一规格').replace('(pi%3)', '(pi%math.ceil(math.sqrt(len(ps))))').replace('(pi//3)', '(pi//math.ceil(math.sqrt(len(ps))))'))
exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='project'],type_ignores=[]),'<project writer>','exec'))

def part(key,x,y,rot=0,index=1):
    m=PARTS[LABEL[key]].copy()
    if rot:m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(rot),[0,0,1]))
    m=normalize(m);m.apply_translation([x,y,0])
    return {'name':LABEL[key]+f'_{index:02d}','key':str(key),'mesh':m,'profile':'P1'}

plates=[]
for ch,(_,drop,t) in VARIANTS.items():
    pp=[part(ch,25,10,index=1),part(ch,25,10+t+7,180,index=2)]
    plates.append((f'第{len(plates)+1:02d}盘_{LABEL[ch]}_一对',pp))
for bw in [200,220,240,260,280]:
    plates.append((f'第{len(plates)+1:02d}盘_连接板单件_适配板宽{bw}',[part(bw,7 if bw==260 else 25,35,45 if bw==280 else 0)]))

validation=[]
for title,pp in plates:
    polys=[footprint(p['mesh']) for p in pp]
    for poly in polys:
        assert box(5,5,251,251).covers(poly),(title,'outside plate',poly.bounds)
        assert not box(0,0,18,28).intersects(poly),(title,'exclusion')
    ds=[polys[i].distance(polys[j]) for i in range(len(polys)) for j in range(i)]
    assert not ds or min(ds)>4,(title,ds)
    validation.append({'plate':title,'objects':len(pp),'minimum_clearance':min(ds) if ds else None,'bed_pass':True})
    project(ROOT/'单盘工程'/(title+'.3mf'),[(title,pp)])
project(ROOT/'V3.0_十一盘工程_独立零件_P1S_PETG.3mf',plates)
(ROOT/'技术资料'/'几何与装配检查.json').write_text(json.dumps({'meshes':REPORT,'assembly':CHECKS,'plates':validation},ensure_ascii=False,indent=2),encoding='utf8')
(ROOT/'技术资料'/'P1S_PETG参数.json').write_text(json.dumps(SET,ensure_ascii=False,indent=2),encoding='utf8')

# Render of actual exported solids in their assembled coordinate frame.
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
def text(d,pos,s,n=24,c='#213449'):d.text(pos,s,font=font(n),fill=c)
im=Image.new('RGB',(1800,1100),'#f5f7fa');d=ImageDraw.Draw(im)
text(d,(40,25),'V3.0：统一接口与厚度；顶臂和下垂按两个独立尺寸选择',35)
upright=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]])
rail=ASSEMBLY[200].transform([[0,1,0,0],[0,0,-1,-14/2+2],[1,0,0,0]])
objects=[]
for ss,col in [(ASSEMBLY['M'],(233,170,53)),(ASSEMBLY['M'].translate((0,0,200)),(233,170,53)),(rail,(57,156,147))]:
    mm=mesh(ss);mm.apply_transform(upright);objects.append((mm,col))
render(d,objects,(30,120,1120,750),view=(1,-1,.8))
for i,st in enumerate(['① 连接板两端插入侧孔','② 每端插入12 mm','③ 矩形截面限制相对转动','④ 再锁紧洞洞板底部螺丝','⑤ 板固定间距，限制插舌退出']):text(d,(1130,190+i*90),st,25)
text(d,(45,925),'插舌24×4 mm；孔24.4×4.4 mm；每侧间隙0.2 mm。中间挂架可向左右续接。',26)
text(d,(45,985),'连接板负责辅助定位；未装洞洞板前可以拔出，不是自锁扣。顶部仍需防滑贴／粘胶。',25,c='#a44828')
im.save(ROOT/'图解'/'01_免螺丝插接装配.png')
im=Image.new('RGB',(1800,1100),'#f5f7fa');d=ImageDraw.Draw(im)
text(d,(40,25),'统一标准：三种顶臂 × 两种下垂',38)
text(d,(40,90),'统一宽44、臂厚14、底座厚20.4 mm；所有款式共用连接板与螺丝规格。',25)
for i,ch in enumerate(['S','M','L']):
    arm,old_drop,t=VARIANTS[ch];short_drop=VARIANTS[ch+'短'][1]
    x=70+i*570;sc=2.6
    text(d,(x,175),f'顶臂 {arm} mm',30)
    text(d,(x,225),f'下垂 {old_drop} → {short_drop} mm',26)
    for j,key in enumerate([ch,ch+'短']):
        # Side projection of the actual model; identical mm-to-pixel scale.
        mm=mesh(ASSEMBLY[key]);poly=footprint(mm);ox=x+arm*sc;oy=330+j*430
        geoms=list(poly.geoms) if poly.geom_type=='MultiPolygon' else [poly]
        for po in geoms:
            d.polygon([(ox+a*sc,oy+bb*sc) for a,bb in po.exterior.coords],fill='#e2b449' if j==0 else '#3f9e96')
            for ring in po.interiors:d.polygon([(ox+a*sc,oy+bb*sc) for a,bb in ring.coords],fill='#f5f7fa')
        text(d,(x,oy+VARIANTS[key][1]*sc+12),'下垂90 · 标准版' if j==0 else '下垂65 · 短版',23)
text(d,(40,1030),'所有短版均比对应标准版抬高25 mm；同排使用同一下垂高度。',25,c='#a44828')
im.save(ROOT/'图解'/'02_统一规格对照.png')
for title,pp in plates:
    im=Image.new('RGB',(1250,980),'#f5f7fa');d=ImageDraw.Draw(im);text(d,(25,20),title,29)
    for i,p in enumerate(pp):
        for tri in p['mesh'].triangles:d.polygon([(30+v[0]*3,850-v[1]*3) for v in tri],fill=['#dea939','#388f8a','#5783a6'][i%3])
        text(d,(825,160+i*100),f'{i+1}. '+(f'顶臂{VARIANTS[p["key"]][0]} / 下垂{VARIANTS[p["key"]][1]}' if p['key'] in VARIANTS else '适配板宽'+p['key']),24)
    text(d,(25,905),'P1S / PETG / 0.20 mm / 6墙 / 50% gyroid；独立对象，可单独补打。',24)
    im.save(ROOT/'图解'/(title+'.png'))
shutil.copy2(__file__,ROOT/'技术资料'/'build_v3.py')
print(ROOT)
print(json.dumps(validation,ensure_ascii=False))
