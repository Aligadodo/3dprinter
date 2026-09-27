from pathlib import Path
import json,zipfile,shutil,copy,xml.etree.ElementTree as E
import numpy as np,trimesh
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).parent
OLD=BASE/'print-kit-v1'
ROOT=BASE/'releases'/'MSkadis洞洞板柜顶挂架_V1.0_20260926'
for p in ['单盘工程','单件STL','技术资料','来源存档','摆盘图','中文装配图解']: (ROOT/p).mkdir(parents=True,exist_ok=True)
LABEL={'L_S':'S小号柜顶挂架_搭接60mm','L_M':'M中号柜顶挂架_搭接90mm','L_L':'L大号柜顶挂架_搭接120mm','rail_head_242':'头部承重背条_242mm','rail_extension_202':'向下续接背条_202mm','splice_front_160':'续接前盖板_带圆柱沉孔','splice_back_160':'续接后盖板','board_spacer_10':'板背隔柱_10mm','lock_spacer_1':'顶部锁紧垫圈_1mm','back_pad_25':'S配套底部靠垫_25mm','back_pad_27':'M配套底部靠垫_27mm','back_pad_29':'L配套底部靠垫_29mm','fit_male_S':'挂扣试配_公扣','fit_female':'挂扣与螺母槽试配_母扣'}
M={k:trimesh.load_mesh(OLD/'STL'/(k+'.stl')) for k in LABEL}
for k,v in LABEL.items(): shutil.copy2(OLD/'STL'/(k+'.stl'),ROOT/'单件STL'/(v+'.stl'))
shutil.copy2(OLD/'洞洞板挂架_P1S_PETG_M4_三种尺寸_中文分盘.3mf',ROOT/'来源存档'/'前版八盘工程_仅存档勿重复打印.3mf')
SET=json.loads((OLD/'P1S-PETG-settings.json').read_text(encoding='utf8'))
SET['print_settings_id']='V1_PETG_0.20mm_6墙_承重50%_小件100%'
(ROOT/'技术资料'/'P1S_PETG_完整基础参数.json').write_text(json.dumps(SET,ensure_ascii=False,indent=2),encoding='utf8')
plates=[]
def part(k,x,y,rot=0,prefix='',index=1):
 m=M[k].copy()
 if rot:m.apply_transform(trimesh.transformations.rotation_matrix(np.pi,[0,0,1]))
 m.apply_translation(-m.bounds[0]);m.apply_translation([x,y,0])
 return dict(key=k,name=f'{prefix}{LABEL[k]}_{index:02d}',mesh=m,profile='P2' if k in ['board_spacer_10','lock_spacer_1'] else 'P1')
plates.append(('第01盘_先试配_挂扣与M4螺母槽',[part('fit_male_S',60,85),part('fit_female',100,85),part('lock_spacer_1',160,85)]))
for n,(s,t,h,reach) in enumerate([('S',10,25,60),('M',12,27,90),('L',14,29,120)],2):
 a=[part('L_'+s,25,7,prefix=s+'_',index=1),part('L_'+s,25,7+t+6,180,prefix=s+'_',index=2)]
 a += [part('rail_head_242',7,y,prefix=s+'_',index=i) for i,y in enumerate([188,218],1)]
 a += [part('back_pad_'+str(h),x,10,prefix=s+'_',index=i) for i,x in enumerate([190,224],1)]
 a += [part('board_spacer_10',x,y,prefix=s+'_',index=i) for i,(x,y) in enumerate([(190,50),(214,50),(190,73),(214,73)],1)]
 a += [part('lock_spacer_1',x,100,prefix=s+'_',index=i) for i,x in enumerate([190,214],1)]
 plates.append((f'第{n:02d}盘_{s}号单板完整套装_搭接{reach}mm',a))
a=[part('rail_extension_202',25,y,index=i) for i,y in enumerate([10,42],1)]
a += [part('splice_front_160',25,y,index=i) for i,y in enumerate([80,112],1)]
a += [part('splice_back_160',25,y,index=i) for i,y in enumerate([144,176],1)]
a += [part('board_spacer_10',210,y,index=i) for i,y in enumerate([85,110,145,170],1)]
plates.append(('第05盘_通用扩展_向下增加一块洞洞板',a))
extras=[(f'补打第{i}盘_{s}号柜顶挂架一对',[part('L_'+s,25,7,index=1),part('L_'+s,25,7+t+6,180,index=2)]) for i,(s,t) in enumerate([('S',10),('L',14)],1)]
# Validate actual projected footprints, including concave nested brackets.
validation=[]
for title,parts in plates+extras:
 polys=[]
 for p in parts:
  mesh=p['mesh'];assert mesh.is_watertight,p['name']
  polys.append(unary_union([Polygon(v[:,:2]) for v in mesh.triangles if Polygon(v[:,:2]).area>1e-8]))
  assert box(5,5,251,251).covers(polys[-1]),(title,p['name'],'bed')
  assert not polys[-1].intersects(box(0,0,18,28)),(title,p['name'],'exclude')
 ds=[polys[i].distance(polys[j]) for i in range(len(polys)) for j in range(i)]
 assert min(ds)>3.9,(title,min(ds))
 validation.append({'plate':title,'objects':len(parts),'minimum_xy_clearance_mm':round(min(ds),3),'watertight':True,'bed_and_exclusion_pass':True})
(ROOT/'技术资料'/'摆盘几何检查.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf8')
C='http://schemas.microsoft.com/3dmanufacturing/core/2015/02';P='http://schemas.microsoft.com/3dmanufacturing/production/2015/06';B='http://schemas.bambulab.com/package/2021'
E.register_namespace('',C);E.register_namespace('p',P);T=lambda s:'{'+C+'}'+s
I='1 0 0 0 1 0 0 0 1 0 0 0'
def meta(o,k,v):E.SubElement(o,'metadata',key=k,value=str(v))
def xml(o):return E.tostring(o,encoding='utf-8',xml_declaration=True)
def project(path,ps):
 r=E.Element(T('model'),{'unit':'millimeter','xml:lang':'en-US','xmlns:BambuStudio':B,'requiredextensions':'p'})
 for k,v in [('Application','BambuStudio-02.06.00.51'),('BambuStudio:3mfVersion','1'),('Title','洞洞板挂架 V1.0 独立零件')]:E.SubElement(r,T('metadata'),name=k).text=v
 res=E.SubElement(r,T('resources'));build=E.SubElement(r,T('build'));cfg=E.Element('config');rels=E.Element('Relationships',xmlns='http://schemas.openxmlformats.org/package/2006/relationships');files={};count=0
 for pi,(title,parts) in enumerate(ps):
  ids=[]
  for p in parts:
   count+=2;pid=count-1;cid=count;ids.append(pid);m=p['mesh'];pn=f'3D/Objects/object_{cid}.model'
   parent=E.SubElement(res,T('object'),id=str(pid),type='model',name=p['name']);comps=E.SubElement(parent,T('components'))
   E.SubElement(comps,T('component'),{'{'+P+'}path':'/'+pn,'objectid':str(cid),'transform':I})
   E.SubElement(build,T('item'),objectid=str(pid),printable='1',transform=f'1 0 0 0 1 0 0 0 1 {(pi%3)*307.2} {-(pi//3)*307.2} 0')
   sub=E.Element(T('model'),unit='millimeter');sr=E.SubElement(sub,T('resources'));o=E.SubElement(sr,T('object'),id=str(cid),type='model',name=p['name']);me=E.SubElement(o,T('mesh'));vs=E.SubElement(me,T('vertices'));ts=E.SubElement(me,T('triangles'))
   for v in m.vertices:E.SubElement(vs,T('vertex'),**{a:f'{b:.6f}' for a,b in zip('xyz',v)})
   for f in m.faces:E.SubElement(ts,T('triangle'),**{a:str(b) for a,b in zip(['v1','v2','v3'],f)})
   files[pn]=xml(sub);E.SubElement(rels,'Relationship',Target='/'+pn,Id=f'rel{cid}',Type='http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel')
   co=E.SubElement(cfg,'object',id=str(pid));meta(co,'name',p['name']);meta(co,'extruder',1)
   if p['profile']=='P2':meta(co,'sparse_infill_density','100%');meta(co,'sparse_infill_pattern','rectilinear')
   cp=E.SubElement(co,'part',id=str(cid),subtype='normal_part');meta(cp,'name',p['name']);meta(cp,'matrix','1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1');meta(cp,'extruder',1)
   E.SubElement(cp,'mesh_stat',face_count=str(len(m.faces)),edges_fixed='0',degenerate_facets='0',facets_removed='0',facets_reversed='0',backwards_edges='0')
  pl=E.SubElement(cfg,'plate')
  for k,v in [('plater_id',pi+1),('plater_name',title),('locked','false'),('filament_maps','1')]:meta(pl,k,v)
  for pid in ids:
   mi=E.SubElement(pl,'model_instance');meta(mi,'object_id',pid);meta(mi,'instance_id',0);meta(mi,'identify_id',pid)
 with zipfile.ZipFile(OLD/'洞洞板挂架_P1S_PETG_M4_三种尺寸_中文分盘.3mf') as z:
  files.update({k:z.read(k) for k in ['[Content_Types].xml','_rels/.rels']})
 files.update({'3D/3dmodel.model':xml(r),'3D/_rels/3dmodel.model.rels':xml(rels),'Metadata/model_settings.config':xml(cfg)})
 settings=copy.deepcopy(SET);settings['wipe_tower_x']=['15']*len(ps);settings['wipe_tower_y']=['220']*len(ps)
 files['Metadata/project_settings.config']=json.dumps(settings,ensure_ascii=False).encode('utf8')
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  for k,v in files.items():z.writestr(k,v)
 assert len(build)==sum(len(a) for _,a in ps)
 assert all(len(o.findall('part'))==1 for o in cfg.findall('object'))
project(ROOT/'V1_主工程_五盘_按尺寸成套_零件可独立打印.3mf',plates)
project(ROOT/'V1_额外补打_S与L主架各一对_两盘.3mf',extras)
for title,a in plates:project(ROOT/'单盘工程'/(title+'.3mf'),[(title,a)])
# Actual top-view plate maps, matching object order and names.
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
colors=['#258f80','#588fb7','#bd823c','#896bad','#ad576c']
for pi,(title,parts) in enumerate(plates):
 im=Image.new('RGB',(1800,1130),'#f7f9fc');d=ImageDraw.Draw(im);d.text((35,20),title,font=font(36),fill='#24384e')
 d.text((35,78),'每个编号都是独立对象；在对象列表中单独选择、删除或导出。',font=font(24),fill='#53697d')
 x0,y0,scale=45,170,3.2
 d.rectangle((x0,y0,x0+256*scale,y0+256*scale),fill='white',outline='#456078',width=3)
 def xy(x,y):return (x0+x*scale,y0+(256-y)*scale)
 d.rectangle((*xy(0,28),*xy(18,0)),fill='#edd2cd')
 for i,p in enumerate(parts,1):
  m=p['mesh'];col=colors[(i-1)%len(colors)]
  for tri in m.triangles:d.polygon([xy(*v[:2]) for v in tri],fill=col)
  # label point within footprint rather than concave bounding box center
  poly=unary_union([Polygon(v[:,:2]) for v in m.triangles if Polygon(v[:,:2]).area>1e-8]);pt=poly.representative_point();xx,yy=xy(pt.x,pt.y)
  d.ellipse((xx-15,yy-15,xx+15,yy+15),fill='white',outline='#23384e');d.text((xx-10,yy-14),str(i),font=font(19),fill='#23384e')
  d.text((910,160+(i-1)*57),f'{i:02d}  {p["name"]}',font=font(23),fill='#24384e')
  d.text((960,190+(i-1)*57),'P2 小件：100%填充' if p['profile']=='P2' else 'P1 承重件：6墙 / 50%填充',font=font(17),fill='#66788a')
 hw='试配件不装入成品；使用实际 M4 螺母检查槽位。' if pi==0 else ('本盘配：M4×25 六颗 + M4×16 两颗 + M4 螺母八颗。' if pi<4 else '本盘新增：M4×25 十二颗 + M4 螺母十二颗；靠垫移至最底段。')
 d.text((40,1040),hw,font=font(27),fill='#a0472e');d.text((40,1080),'螺丝长度从头底量起；平底头，不用锥形沉头。M4×10 不用于本版承重连接。',font=font(23),fill='#a0472e')
 im.save(ROOT/'摆盘图'/(title+'.png'))
manifest=[{'plate':title,'parts':[{'name':p['name'],'stl':LABEL[p['key']]+'.stl','profile':p['profile']} for p in a]} for title,a in plates]
(ROOT/'技术资料'/'各盘独立组件清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
shutil.copy2(__file__,ROOT/'技术资料'/'build_release_v1.py')
print(ROOT)
print(json.dumps(validation,ensure_ascii=False))
