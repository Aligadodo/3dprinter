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
ROOT=BASE/'releases'/'MSkadis挂架_V2.0_双孔简化试装版'
STL=ROOT/'单件STL'
for p in [STL,ROOT/'单盘工程',ROOT/'技术资料',ROOT/'图解']:p.mkdir(parents=True,exist_ok=True)
PARTS={};REPORT={};ASSEMBLY={}
# Reuse only pure geometry/serialization helpers, never execute the V1 build.
tree=ast.parse((BASE/'build_print_kit.py').read_text(encoding='utf8'))
names={'solid','roundbox','bore_x','mesh','normalize','save','footprint','render'}
exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'<geometry helpers>','exec'))
W=44.;T=20.4;D=4.4;PITCH=25.
VARIANTS={'S':(60,90,10),'M':(90,110,12),'L':(120,130,14)}
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
    # Four top-rail fastening stations: each end has two M4 screws against rotation.
    for z in [-16,16]:
        for x in [-41,-27]:
            s=s-bore_y(-t-.1,8.6,x,z,4.4)
            # Side-loading nut slot. 7.5 across flats restrains the nut from rotating.
            z0=-22.1 if z<0 else 16-4.3
            s=s-cube((7.5,3.6,10.4),(x-3.75,-t+2,z0))
    # Uninterrupted top contact face for user-selected anti-slip/adhesive attachment.
    ASSEMBLY[ch]=s
    name=f'{ch}号挂架_顶臂{arm}_下垂{drop}_双孔25_厚20.4'
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
    s=s+solid(box(10,-48,22.4,-20),4)+solid(box(bw-22.4,-48,bw-10,-20),4)
    for x in [16,bw-16]:
        for y in [-41,-27]:s=s-solid(Point(x,y).buffer(2.2,quad_segs=24),6.2,-.1)
    name=f'连接板_适配板宽{bw}_净跨{bw-44.4:g}_总长{bw-20}'
    LABEL[bw]=name;ASSEMBLY[bw]=s
    save(name,s)
    # Map rail x->bracket width, rail y->top arm, rail z->upwards.
    for ch,(_,_,t) in VARIANTS.items():
        rail=s.transform([[0,1,0,0],[0,0,-1,-t],[1,0,0,0]])
        left=ASSEMBLY[ch];right=left.translate((0,0,bw))
        assert (rail^left).volume()<1e-6 and (rail^right).volume()<1e-6
        for xx in [-41,-27]:
            for zz in [16,bw-16]:
                bolt=bore_y(-t-4,10,xx,zz,4)
                assert ((left+right+rail)^bolt).volume()<1e-6
    CHECKS[str(bw)]={'center_pitch':bw,'clear_body_length':bw-44.4,'overall_length':bw-20,'shoulder_clearance_each':.2,'overlap_each':12,'assembly_interference_mm3':0}

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
SET['print_settings_id']='V2_PETG_0.20_6walls_50pct';SET['enable_support']='0'
C='http://schemas.microsoft.com/3dmanufacturing/core/2015/02';P='http://schemas.microsoft.com/3dmanufacturing/production/2015/06';B='http://schemas.bambulab.com/package/2021'
E.register_namespace('',C);E.register_namespace('p',P);Tg=lambda s:'{'+C+'}'+s
# V1 writer expects T as a tag function.
T=Tg
I='1 0 0 0 1 0 0 0 1 0 0 0'
def meta(o,k,v):E.SubElement(o,'metadata',key=k,value=str(v))
def xml(o):return E.tostring(o,encoding='utf-8',xml_declaration=True)
tree=ast.parse((BASE/'build_release_v1.py').read_text(encoding='utf8').replace('洞洞板挂架 V1.0 独立零件','洞洞板挂架 V2.0 双孔简化版'))
exec(compile(ast.Module([n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='project'],type_ignores=[]),'<project writer>','exec'))

def part(key,x,y,rot=0,index=1):
    m=PARTS[LABEL[key]].copy()
    if rot:m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(rot),[0,0,1]))
    m=normalize(m);m.apply_translation([x,y,0])
    return {'name':LABEL[key]+f'_{index:02d}','key':str(key),'mesh':m,'profile':'P1'}

plates=[]
for ch,(_,drop,t) in VARIANTS.items():
    # Each bracket gets a separate side-on footprint; a small rail fits above the pair.
    # Compact nested pair preserves 6 mm clearance in the concave L footprints.
    pp=[part(ch,25,10,index=1),part(ch,25,10+t+7,180,index=2)]
    # Pair occupied height <= 2*t+drop+7; leave the connector above it.
    ymax=max(p['mesh'].bounds[1,1] for p in pp)
    pp.append(part(200,35,ymax+8))
    plates.append((f'{ch}号试装套装_两挂架加200连接板',pp))
for bw in [220,240,260,280]:
    plates.append((f'选配连接板_板宽{bw}',[part(bw,7 if bw==260 else 25,35,45 if bw==280 else 0)]))

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
project(ROOT/'V2_七盘工程_独立零件_P1S_PETG.3mf',plates)
(ROOT/'技术资料'/'几何与装配检查.json').write_text(json.dumps({'meshes':REPORT,'assembly':CHECKS,'plates':validation},ensure_ascii=False,indent=2),encoding='utf8')
(ROOT/'技术资料'/'P1S_PETG参数.json').write_text(json.dumps(SET,ensure_ascii=False,indent=2),encoding='utf8')

# True triangle render of the delivered solids, plus dimensional schematics.
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
def text(d,pos,s,n=24,c='#213449'):d.text(pos,s,font=font(n),fill=c)
im=Image.new('RGB',(1800,1150),'#f5f7fa');d=ImageDraw.Draw(im)
text(d,(40,25),'V2 双孔简化版：只保留挂架与横向连接板',38)
text(d,(40,85),'ModelB 标准接口：Ø4.4 / 孔距25 / 接触厚20.4 mm；此版需试装，尚未额定承重。',24)
for i,ch in enumerate(VARIANTS):
    render(d,[(mesh(ASSEMBLY[ch]),(233,170,53))],(35+i*570,160,510,430),view=(1,.4,1.3))
    arm,drop,t=VARIANTS[ch];text(d,(60+i*570,605),f'{ch}：顶臂{arm} / 下垂{drop} / 宽44',25)
text(d,(45,675),'横向接缝安装：一只挂架的两个孔分别锁住相邻两块板的顶角。',28)
for k in range(3):
    x=70+k*390;d.rounded_rectangle((x,735,x+390,1000),12,fill='#e0e7ef',outline='#8498aa',width=2)
    for xx in [x+24,x+366]:d.ellipse((xx-5,752,xx+5,762),fill='#213449')
for x in [70,460,850,1240]:
    d.rectangle((x-43,705,x+43,770),outline='#c78417',width=5)
for x in [70,460,850]:d.rectangle((x+44,706,x+346,725),fill='#439993')
text(d,(1300,740),'每增一列：',26);text(d,(1300,790),'+1 挂架',26);text(d,(1300,835),'+1 对应宽度连接板',26)
text(d,(45,1040),'底部与纵向拼板继续使用原 ModelB；双孔及横向连接板不能替代家具端防滑固定。',25,c='#a44828')
im.save(ROOT/'图解'/'01_结构与组合.png')

im=Image.new('RGB',(1800,1050),'#f5f7fa');d=ImageDraw.Draw(im)
text(d,(40,25),'双孔座：螺母中间装入，长螺丝在内部避让',36)
text(d,(40,85),'统一 20.4 mm 板背距离；孔中心距25 mm；入口保留在底部中央。',25)
render(d,[(mesh(ASSEMBLY['S']),(234,172,51))],(20,160,680,720),view=(1,.8,1.4))
# Section schematic with axis depth measured inward from the board back.
x0=850;scale=29;y0=290
d.rectangle((x0-5*scale,y0,x0,y0+240),fill='#dce5ec')
d.rectangle((x0,y0,x0+20.4*scale,y0+240),fill='#e7b853')
d.rectangle((x0,y0+100,x0+16*scale,y0+140),fill='#f5f7fa')
d.rectangle((x0+3*scale,y0+78,x0+6.6*scale,y0+162),fill='#7d8c9b')
for i,(length,color) in enumerate([(12,'#22867f'),(16,'#326ea3'),(18,'#a24776')]):
    yy=y0+104+i*12;d.line((x0-5*scale,yy,x0+(length-5)*scale,yy),fill=color,width=6)
    text(d,(760,590+i*58),f'M4×{length}：进入座内 {length-5} mm，距盲孔底余量 {16-(length-5)} mm',23,c=color)
text(d,(740,205),'洞洞板 5 mm',23);text(d,(1030,205),'螺母槽深 3～6.6 mm',23)
text(d,(760,810),'板背到家具接触面 20.4 mm；避让深度16 mm，后壁4.4 mm。',24)
text(d,(45,955),'按有效板厚5 mm、M4普通螺母厚3.2 mm设计；沉头下沉会改变有效长度，需核对余量。',25,c='#a44828')
im.save(ROOT/'图解'/'02_螺丝与厚度.png')

im=Image.new('RGB',(1800,1100),'#f5f7fa');d=ImageDraw.Draw(im)
text(d,(40,25),'横向连接：每端双螺丝，上方搭接；可以连续接下一列',34)
upright=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]])
rail=ASSEMBLY[200].transform([[0,1,0,0],[0,0,-1,-12],[1,0,0,0]])
objects=[]
for ss,col in [(ASSEMBLY['M'],(233,170,53)),(ASSEMBLY['M'].translate((0,0,200)),(233,170,53)),(rail,(57,156,147))]:
    mm=mesh(ss);mm.apply_transform(upright);objects.append((mm,col))
render(d,objects,(40,120,1120,750),view=(1,-1,.8))
for i,st in enumerate(['① 两端各放入2颗M4螺母','② 连接板薄端搭在顶臂上','③ 每端2颗M4×10锁紧','④ 底部双孔连接洞洞板','⑤ 顶臂下表面贴防滑／粘胶']):text(d,(1150,190+i*90),st,25)
text(d,(45,920),'中间挂架左右各接一块连接板；同一排选同一S/M/L规格。',27)
text(d,(45,985),'连接板螺丝：M4×10（无垫圈）或M4×12配1 mm金属平垫；禁止误用16/18 mm。',25,c='#a44828')
im.save(ROOT/'图解'/'03_横向连接装配.png')

for title,pp in plates:
    im=Image.new('RGB',(1250,980),'#f5f7fa');d=ImageDraw.Draw(im);text(d,(25,20),title,29)
    for i,p in enumerate(pp):
        for tri in p['mesh'].triangles:d.polygon([(30+v[0]*3,850-v[1]*3) for v in tri],fill=['#dea939','#388f8a','#5783a6'][i%3])
        text(d,(825,160+i*100),f'{i+1}. '+p['key'],26)
    text(d,(25,905),'P1S / PETG / 0.20 mm / 6墙 / 50% gyroid；独立对象，可单独补打。',24)
    im.save(ROOT/'图解'/(title+'.png'))
shutil.copy2(__file__,ROOT/'技术资料'/'build_v2.py')
print(ROOT)
print(json.dumps(validation,ensure_ascii=False))
