"""Parametric prototype kit. Geometry is in mm; no load rating is implied."""
from pathlib import Path
import json, math, zipfile, xml.etree.ElementTree as ET
import numpy as np
import trimesh
import manifold3d as md
from shapely.geometry import Polygon, Point, box, LineString
from shapely.ops import unary_union
from shapely.geometry.polygon import orient
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).parent/'print-kit-v1'
STL=ROOT/'STL'; PLATES=ROOT/'plates'
for p in [ROOT,STL,PLATES]: p.mkdir(parents=True,exist_ok=True)
PARTS={}; ASSEMBLY={}; REPORT={}; PLATE_DATA=[]
CORE='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
ET.register_namespace('',CORE)

def solid(poly,h,z=0):
    if poly.geom_type=='MultiPolygon':
        return md.Manifold.batch_boolean([solid(p,h,z) for p in poly.geoms],md.OpType.Add)
    poly=orient(poly,sign=1.0)
    rings=[np.asarray(poly.exterior.coords)[:-1].tolist()]
    rings += [np.asarray(r.coords)[:-1].tolist() for r in poly.interiors]
    return md.CrossSection(rings).extrude(h).translate((0,0,z))

def roundbox(x0,y0,x1,y1,r=1):
    return box(x0+r,y0+r,x1-r,y1-r).buffer(r,quad_segs=10)

def bore_x(x0,length,y,z,d,hexagon=False):
    # local disk x/y -> world y/z; local extrusion -> world x.
    if hexagon:
        radius=d/math.sqrt(3)
        p=Polygon([(radius*math.cos(math.radians(30+60*i)),radius*math.sin(math.radians(30+60*i))) for i in range(6)])
    else: p=Point(0,0).buffer(d/2,quad_segs=20)
    return solid(p,length).transform([[0,0,1,x0],[1,0,0,y],[0,1,0,z]])

def mesh(s):
    m=s.simplify(.005).to_mesh64(); return trimesh.Trimesh(np.asarray(m.vert_properties)[:,:3],np.asarray(m.tri_verts),process=False)

def normalize(m):
    m=m.copy(); m.apply_translation(-m.bounds[0]); return m

def save(name,s,orientation=None):
    raw=mesh(s)
    if orientation is not None: raw.apply_transform(orientation)
    m=normalize(raw)
    # STL stores float32. Quantize now, weld coincident vertices and remove collapsed triangles.
    m=trimesh.Trimesh(m.vertices.astype(np.float32),m.faces,process=True)
    m.merge_vertices(digits_vertex=4)
    m.update_faces(m.nondegenerate_faces());m.remove_unreferenced_vertices()
    if not m.is_watertight:
        edges,counts=np.unique(m.edges_sorted,axis=0,return_counts=True)
        print(name,'bad_edges',m.vertices[np.unique(edges[counts!=2])].tolist())
    assert m.is_watertight and m.is_winding_consistent and m.volume>0,(name,str(s.status()),m.is_watertight,m.is_winding_consistent,m.volume,len(m.faces))
    assert len(m.split())==1,(name,'disconnected geometry')
    m.export(STL/(name+'.stl')); PARTS[name]=m
    check=trimesh.load_mesh(STL/(name+'.stl'))
    assert check.is_watertight and check.is_winding_consistent,(name,'STL roundtrip invalid')
    REPORT[name]={'size_mm':np.round(m.extents,3).tolist(),'volume_cm3':round(m.volume/1000,3),'watertight':True,'components':1,'triangles':len(m.faces)}
    return m

def label(s,ch,x,y,z):
    strokes={
      'S': [[(5,0),(0,0),(0,3),(5,3),(5,6),(0,6)]],
      'M': [[(0,6),(0,0),(2.5,3),(5,0),(5,6)]],
      'L': [[(0,0),(0,6),(5,6)]]}
    for path in strokes[ch]:
        s=s-solid(LineString([(x+a,y+b) for a,b in path]).buffer(.45),.7,z-.6)
    return s

# Assembly frame: u outward from furniture; v downward; w across bracket width.
# Print main brackets on their side (u/v in XY), allowing continuous L perimeters.
VARIANTS={'S':(60,90,32,10),'M':(90,110,36,12),'L':(120,130,40,14)}
for ch,(arm,drop,width,t) in VARIANTS.items():
    outline=unary_union([box(-arm,-t,t,0),box(0,-t,t,drop),
        Polygon([(t,-t),(t+10,0),(t,22)]),
        Polygon([(t,80),(t+16,80),(t+16,50),(t,66)])])
    outline=outline.buffer(-.8,join_style=1).buffer(.8,join_style=1)
    # Preserve exact cleat bearing face and the furniture clearance, not a fillet intruding into it.
    outline=outline.union(Polygon([(t-.1,80),(t+16,80),(t+16,50),(t-.1,66.1)]))
    outline=outline.difference(box(-arm-5,0,0,drop+5)).difference(Point(0,0).buffer(1.5))
    outline=outline.difference(roundbox(-arm+14,-t/2-2,-arm+30,-t/2+2,.8))
    s=solid(outline,width,-width/2)
    s=s-bore_x(t-1,28,72,0,4.6)
    # M4 nut slides in from the printed upper side, away from furniture contact.
    s=s-bore_x(t+4,3.6,72,0,7.3,True)
    s=s-md.Manifold.cube((3.64,7.5,width/2+1)).translate((t+3.98,72-3.75,0))
    s=label(s,ch,-arm+38,-t/2-3,width/2)
    ASSEMBLY[ch]=s
    save('L_'+ch,s)

# Common female cleat/first rail; face coordinate relative to the L's outside face.
# The first board top is v=80, so its 175 mm mounting pitch is v=92.5 / 267.5.
rail_profile=Polygon([(.4,40),(24.4,40),(24.4,282),(16.4,282),(16.4,49.6),(.4,65.6)])
head=solid(rail_profile,24,-12)
for v,d in [(72,5.0),(92.5,4.6),(267.5,4.6),(222,4.6),(242,4.6)]:
    head=head-bore_x(-1,27,v,0,d)
for v in [92.5,267.5]: head=head-bore_x(16.3,3.7,v,0,7.3,True)
# Print rail face-down: long axis in XY, clip growing upward, no unsupported rear tongue.
RAIL_PRINT=np.array([[0,1,0,0],[0,0,1,0],[-1,0,0,0],[0,0,0,1]],float)
ASSEMBLY['head']=head
save('rail_head_242',head,RAIL_PRINT)

extension=solid(box(16.4,0,24.4,202),24,-12)
for v,d in [(12.5,4.6),(187.5,4.6),(40,4.6),(60,4.6),(142,4.6),(162,4.6)]:
    extension=extension-bore_x(15,12,v,0,d)
for v in [12.5,187.5]: extension=extension-bore_x(16.3,3.7,v,0,7.3,True)
ASSEMBLY['extension']=extension
save('rail_extension_202',extension,RAIL_PRINT)

# M4x25 splice: front plate has flat-bottom counterbores, back plate takes nuts/washers.
for name,h in [('splice_front_160',8),('splice_back_160',6)]:
    splice=solid(roundbox(0,0,160,24,2),h)
    for x in [20,40,120,140]:
        splice=splice-solid(Point(x,12).buffer(2.3,quad_segs=20),h+2,-1)
        if 'front' in name: splice=splice-solid(Point(x,12).buffer(4.4,quad_segs=24),4.6,h-4.5)
    save(name,splice)

def washer(name,h,od,id):
    return save(name,solid(Point(0,0).buffer(od/2,quad_segs=24).difference(Point(0,0).buffer(id/2,quad_segs=20)),h))
washer('board_spacer_10',10,14,4.6)
washer('lock_spacer_1',1,12,4.6)
# Bottom standoff: 3 selectable lengths for surface and nut clearance. Pair can be taped for trial.
for h in [25,27,29]:
    pad=solid(roundbox(0,0,24,24,3),h)
    pad=pad-solid(Point(12,12).buffer(2.3,quad_segs=20),11,-1)
    hexpoly=Polygon([(12+7.3/math.sqrt(3)*math.cos(math.radians(30+60*i)),12+7.3/math.sqrt(3)*math.sin(math.radians(30+60*i))) for i in range(6)])
    pad=pad-solid(hexpoly.union(box(12,12-4.3,25,12+4.3)),3.6,2)
    save('back_pad_'+str(h),pad)

# Paired interface coupons, one bearing male and one shortened female, same print orientation.
coupon_male=solid(Polygon([(0,40),(10,40),(10,66),(26,50),(26,80),(0,80)]),24,-12)
coupon_male=coupon_male-bore_x(9,28,72,0,4.6)-bore_x(14,3.6,72,0,7.3,True)
coupon_male=coupon_male-md.Manifold.cube((3.64,7.5,13)).translate((13.98,68.25,0))
save('fit_male_S',coupon_male)
coupon_female=head ^ md.Manifold.cube((40,45,40)).translate((-2,39,-20))
save('fit_female',coupon_female,RAIL_PRINT)

def footprint(m):
    # Boundary of vertical projection, not convex hull; allows deliberate L nesting.
    triangles=m.vertices[m.faces][:,:,:2]
    polys=[Polygon(t) for t in triangles if abs(np.cross(t[1]-t[0],t[2]-t[0]))>1e-6]
    return unary_union(polys)

def placed(name,x,y,rot=0):
    m=PARTS[name].copy()
    if rot: m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(rot),(0,0,1)))
    m=normalize(m);m.apply_translation((x,y,0))
    return name,m

def write3mf(path,items):
    tag=lambda x:'{'+CORE+'}'+x
    r=ET.Element(tag('model'),{'unit':'millimeter','xml:lang':'en-US'})
    ET.SubElement(r,tag('metadata'),{'name':'Title'}).text=path.stem
    ET.SubElement(r,tag('metadata'),{'name':'Description'}).text='Prototype geometry only. Not a sliced printer job. See README-打印说明.md.'
    resources=ET.SubElement(r,tag('resources')); build=ET.SubElement(r,tag('build'))
    for i,(name,m) in enumerate(items,1):
        obj=ET.SubElement(resources,tag('object'),{'id':str(i),'type':'model','name':name})
        mm=ET.SubElement(obj,tag('mesh')); vs=ET.SubElement(mm,tag('vertices')); fs=ET.SubElement(mm,tag('triangles'))
        for x,y,z in m.vertices: ET.SubElement(vs,tag('vertex'),{'x':f'{x:.6f}','y':f'{y:.6f}','z':f'{z:.6f}'})
        for a,b,c in m.faces: ET.SubElement(fs,tag('triangle'),{'v1':str(a),'v2':str(b),'v3':str(c)})
        ET.SubElement(build,tag('item'),{'objectid':str(i)})
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',ET.tostring(r,encoding='utf-8',xml_declaration=True))

def plate(name,items):
    # P1S reserves x=0..18, y=0..28. Keep every part above it, including brim space.
    for _,m in items: m.apply_translation((0,25,0))
    bounds=np.array([m.bounds for _,m in items]); lo=bounds[:,0,:].min(0);hi=bounds[:,1,:].max(0)
    assert lo[0]>=4.9 and lo[1]>=4.9 and hi[0]<=251 and hi[1]<=251,(name,lo,hi)
    footprints=[footprint(m) for _,m in items]
    for i,a in enumerate(footprints):
        for b in footprints[i+1:]: assert a.distance(b)>=3.9,(name,'clearance',a.distance(b))
    write3mf(PLATES/(name+'.3mf'),items)
    # Individual placed objects preserved in 3MF; STL plate is not needed.
    PLATE_DATA.append({'name':name,'items':[n for n,_ in items],'occupied_mm':np.round(hi-lo,2).tolist(),'min_xy':lo[:2].tolist(),'max_xy':hi[:2].tolist(),'objects':len(items)})
    return items

ALL_PLATES=[]
for ch,(arm,drop,w,t) in VARIANTS.items():
    ALL_PLATES.append(plate('0'+str(len(ALL_PLATES)+1)+'_L_'+ch+'_pair',[
        placed('L_'+ch,7,7),placed('L_'+ch,7,7+t+6,180)]))
ALL_PLATES.append(plate('04_head_rails_pair',[placed('rail_head_242',7,7),placed('rail_head_242',7,43)]))
ALL_PLATES.append(plate('05_extension_and_splices',[
    placed('rail_extension_202',7,7),placed('rail_extension_202',7,39),
    *[placed(n,7,75+i*32) for i,n in enumerate(['splice_front_160','splice_back_160']*2)]]))
small=[]
for i in range(8): small.append(placed('board_spacer_10',7+(i%4)*22,7+(i//4)*22))
for i in range(2): small.append(placed('lock_spacer_1',110+i*22,7))
for j,h in enumerate([25,27,29]):
    for i in range(2): small.append(placed('back_pad_'+str(h),7+i*34,65+j*34))
small += [placed('fit_male_S',110,91),placed('fit_female',155,91)]
ALL_PLATES.append(plate('06_spacers_and_fit_test',small))
# Tiny first-print plate saves material before printing the full batch.
plate('00_interface_test_first',[placed('fit_male_S',7,7),placed('fit_female',50,7),placed('lock_spacer_1',105,7)])

# Exact interference checks, excluding intended contact faces (zero-volume intersections).
assembly_checks={}
for ch,(_,_,w,t) in VARIANTS.items():
    h=head.translate((t,0,0))
    overlap=(ASSEMBLY[ch]^h).volume()
    assert overlap<1e-5,(ch,overlap)
    # Male/female sloped bearing face matches; transverse and length margins.
    assembly_checks[ch]={'L_head_intersection_mm3':overlap,'side_margin_mm':(w-24)/2,
        'lock_axis_v':72,'board_holes_v':[92.5,267.5],'cleat_side_clearance_mm':.4,
        'M4x25_tip_x_relative_L_face_with_printed_and_metal_washers':24.4+1+1-25,
        'M4_nut_axial_interval_relative_L_face':[4,7.6]}

# Render true mesh triangles orthographically, with depth sorting. No illustrative fake geometry.
FONT='C:/Windows/Fonts/msyh.ttc'; BOLD='C:/Windows/Fonts/msyhbd.ttc'
def txt(d,xy,s,size=24,fill='#26374b',bold=False): d.text(xy,s,font=ImageFont.truetype(BOLD if bold else FONT,size),fill=fill)
def render(d,objects,rect,view=(1,-.6,.8)):
    forward=np.array(view,float);forward/=np.linalg.norm(forward)
    right=np.cross([0,0,1],forward);right/=np.linalg.norm(right)
    up=np.cross(forward,right);basis=np.array([right,-up,forward])
    entries=[];allv=[]
    for m,color in objects:
        p=m.vertices@basis.T;allv.append(p)
        for f,n in zip(m.faces,m.face_normals):
            shade=.58+.42*abs(float(n@forward))
            c=tuple(int(v*shade) for v in color)
            entries.append((p[f,2].mean(),p[f,:2],c))
    pp=np.vstack(allv);mi=pp[:,:2].min(0);ma=pp[:,:2].max(0)
    x,y,w,h=rect;scale=min(w/(ma[0]-mi[0]),h/(ma[1]-mi[1]))
    offset=np.array([x,y])+([w,h]-(ma-mi)*scale)/2-mi*scale
    for _,p,c in sorted(entries,key=lambda a:a[0]): d.polygon([tuple(v) for v in p*scale+offset],fill=c)

im=Image.new('RGB',(1600,1070),'#f7f9fb');d=ImageDraw.Draw(im)
txt(d,(45,25),'三种尺寸 · 同一套可续接背条',38,bold=True)
txt(d,(45,83),'实际导出网格视图｜原型试装套件，未做额定承重认证',23,fill='#63768a')
for i,(ch,(arm,drop,w,t)) in enumerate(VARIANTS.items()):
    txt(d,(55+i*520,135),f'{ch}  顶臂 {arm} / 下垂 {drop} / 宽 {w} / 厚 {t} mm',22,bold=True)
    render(d,[(PARTS['L_'+ch],(29,155,143))],(60+i*520,183,465,330))
# Assembly mounted in intuitive upright coordinates (u,w,-v), common two columns / two boards.
upright=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]],float)
scene=[]
for side in [-87.5,87.5]:
    for key,col,tr in [('M',(29,155,143),(0,0,side)),('head',(220,134,61),(12,0,side)),('extension',(220,134,61),(12,282,side))]:
        m=mesh(ASSEMBLY[key].translate(tr));m.apply_transform(upright);scene.append((m,col))
render(d,scene,(930,555,540,440),view=(1,-1,.6))
txt(d,(55,570),'交付：6 盘主套件 + 1 盘优先试配小样',27,bold=True)
txt(d,(55,627),'每档 L 架 2 个；共用头部背条 2 根；续接背条 2 根',24)
txt(d,(55,673),'连接盖板 4 块；板间隔柱 8 个；锁紧垫圈 / 靠垫',24)
txt(d,(55,734),'L 侧面着床，字母朝上；背条正面着床。',24)
txt(d,(55,780),'最长零件 242 mm，分盘布局按 256 × 256 mm 准备。',24)
txt(d,(55,839),'金属件：M4×25 主连接，M4×16 靠垫；需防外拉限位。',24)
txt(d,(55,923),'右图展示两个支点与两层背条，省略洞洞板及螺栓。',21,fill='#63768a')
txt(d,(55,986),'S / M / L 表示外形尺寸，不代表承重等级。',23,fill='#b76a27')
im.save(ROOT/'versions-preview.png')

im=Image.new('RGB',(1500,1080),'#f7f9fb');d=ImageDraw.Draw(im)
txt(d,(35,18),'主套件打印分盘 · 256 mm 热床',33,bold=True)
colors=['#178d82','#dc8a44','#536d88','#9b84ad']
for idx,items in enumerate(ALL_PLATES):
    x=35+(idx%3)*490;y=87+(idx//3)*490;sz=425;sc=sz/256
    txt(d,(x,y),PLATE_DATA[idx]['name'],22,bold=True)
    d.rectangle((x,y+35,x+sz,y+35+sz),fill='white',outline='#b8c8d8',width=2)
    for j,(name,m) in enumerate(items):
        p=footprint(m)
        for poly in ([p] if p.geom_type=='Polygon' else p.geoms):
            d.polygon([(x+a*sc,y+35+b*sc) for a,b in poly.exterior.coords],fill=colors[j%4])
            for ring in poly.interiors: d.polygon([(x+a*sc,y+35+b*sc) for a,b in ring.coords],fill='white')
im.save(ROOT/'plate-layouts.png')

(ROOT/'geometry-validation.json').write_text(json.dumps({'parts':REPORT,'plates':PLATE_DATA,'assembly':assembly_checks,'notes':['Mesh and geometric fit checks only; no physical load test.','Generic geometry-only 3MF; select your printer/material before slicing.']},ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'parts':len(PARTS),'plates':len(PLATE_DATA),'output':str(ROOT.resolve())},ensure_ascii=False))
