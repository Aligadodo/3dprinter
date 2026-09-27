"""Rename print plates in Chinese without changing geometry or print settings."""
from pathlib import Path
import zipfile, json, hashlib, shutil, re
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

BASE=Path(__file__).parent
ROOT=BASE/'print-kit-v1'
NAMES={
 '00_interface_test_first':'01_先打印_挂扣与螺母槽试配',
 '01_L_S_pair':'02_小号S_柜顶挂架一对_搭接60mm',
 '02_L_M_pair':'03_中号M_柜顶挂架一对_搭接90mm',
 '03_L_L_pair':'04_大号L_柜顶挂架一对_搭接120mm',
 '04_head_rails_pair':'05_顶部承重背条一对_连接挂架与首块板',
 '05_extension_and_splices':'06_向下扩展一块板_续接背条与连接盖板',
 '06_spacers_and_fit_test':'07_装配配件_隔柱垫圈靠垫与备用试配件',
}
TOTAL='洞洞板挂架_P1S_PETG_M4_三种尺寸_中文分盘.3mf'
OLD_TOTAL='P1S_PETG_M4_SML_all_7plates.3mf'

def replace(s):
    for old,new in NAMES.items(): s=s.replace(old,new)
    return s.replace(OLD_TOTAL,TOTAL)

changes=[];before_hashes={}
for p in sorted(ROOT.rglob('*.3mf')):
    before_hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    with zipfile.ZipFile(p) as z: oldfiles={n:z.read(n) for n in z.namelist()}
    newfiles=dict(oldfiles)
    for n,b in oldfiles.items():
        if n.endswith('.model') or n=='Metadata/model_settings.config':
            txt=b.decode('utf-8');new=replace(txt)
            if p.name in (OLD_TOTAL,TOTAL) and n=='Metadata/model_settings.config':
                new=new.replace('key="plater_name" value=""','key="plater_name" value="08_额外打印_小号S与大号L各一对"')
            if new!=txt:
                newfiles[n]=new.encode('utf-8')
                ET.fromstring(newfiles[n])
                # Strip only descriptive names and prove the structural XML is identical.
                def structure(data):
                    r=ET.fromstring(data)
                    for e in r.iter():
                        if e.tag.endswith('object'):e.attrib.pop('name',None)
                        if e.tag.endswith('metadata') and (e.get('key') in ('name','plater_name','source_file') or e.get('name')=='Title'):
                            e.attrib.pop('value',None);e.text=''
                    return ET.tostring(r)
                if structure(b)!=structure(newfiles[n]):
                    import difflib
                    print('\n'.join(difflib.unified_diff(structure(b).decode().replace('><','>\n<').splitlines(),structure(newfiles[n]).decode().replace('><','>\n<').splitlines())))
                    raise AssertionError((p,n,'structural change'))
    assert oldfiles.get('Metadata/project_settings.config')==newfiles.get('Metadata/project_settings.config')
    target=p.with_name(replace(p.name))
    tmp=p.with_suffix('.rename-tmp')
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in newfiles.items():z.writestr(n,b)
    tmp.replace(p)
    if target!=p:p.rename(target)
    changes.append(str(target.relative_to(ROOT)))

for name in ['README-打印说明.md','geometry-validation.json','slice-summary.json']:
    p=ROOT/name;p.write_text(replace(p.read_text(encoding='utf-8')),encoding='utf-8')

p=ROOT/'slice-summary.json';report=json.loads(p.read_text(encoding='utf-8'))
report.setdefault('sliced_project_sha256_before_label_change',report['project_sha256'])
report['project_sha256_before_this_rename']=before_hashes.get(OLD_TOTAL,before_hashes.get(TOTAL))
report['project_sha256']=hashlib.sha256((ROOT/TOTAL).read_bytes()).hexdigest()
report['label_update_validation']='仅修改盘名、对象显示名及文件名；逐项验证本次重命名前后的网格、布局及打印参数未变。'
report['historical_slice_scope']='下列切片数据属于最初七盘工程；当前用户保存的工程含新增第八盘，不能将历史切片结果视为当前八盘工程的重新验证。'
p.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
readme=ROOT/'README-打印说明.md'
intro='> 中文命名更新：当前总工程保留用户新增的第 8 盘“08_额外打印_小号S与大号L各一对”。以下七盘用料与时间为原套件估算，不包含新增第 8 盘。此次只改名称，保留现有模型、摆放和参数。\n\n'
txt=readme.read_text(encoding='utf-8')
if not txt.startswith('> 中文命名更新'):readme.write_text(intro+txt,encoding='utf-8')

# Re-render the plate index from the unchanged geometry, with Chinese captions.
from PIL import Image,ImageDraw,ImageFont
from shapely.geometry import Polygon
from shapely.ops import unary_union
NS={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
im=Image.new('RGB',(1500,1590),'#f7f9fb');d=ImageDraw.Draw(im)
font=lambda n:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',n)
d.text((35,20),'七盘打印用途一览 · P1S / PETG / M4',font=font(32),fill='#20344d')
colors=['#178d82','#dc8a44','#536d88','#9b84ad']
for idx,name in enumerate(NAMES.values()):
    x=35+(idx%3)*490;y=85+(idx//3)*495;sz=425;sc=sz/256
    segments=name.split('_')
    d.text((x,y),segments[0]+'  '+segments[1],font=font(23),fill='#20344d')
    d.text((x,y+30),' · '.join(segments[2:]),font=font(18),fill='#536d88')
    yy=y+65
    d.rectangle((x,yy,x+sz,yy+sz),fill='white',outline='#b8c8d8',width=2)
    with zipfile.ZipFile(ROOT/'plates'/(name+'.3mf')) as z:r=ET.fromstring(z.read('3D/3dmodel.model'))
    for j,o in enumerate(r.findall('m:resources/m:object',NS)):
        vs=[(float(v.get('x')),float(v.get('y'))) for v in o.findall('.//m:vertex',NS)]
        polys=[]
        for t in o.findall('.//m:triangle',NS):
            poly=Polygon([vs[int(t.get(k))] for k in ('v1','v2','v3')])
            if poly.area>1e-6:polys.append(poly)
        p=unary_union(polys)
        for poly in ([p] if p.geom_type=='Polygon' else p.geoms):
            d.polygon([(x+a*sc,yy+b*sc) for a,b in poly.exterior.coords],fill=colors[j%4])
            for ring in poly.interiors:d.polygon([(x+a*sc,yy+b*sc) for a,b in ring.coords],fill='white')
im.save(ROOT/'plate-layouts.png')

(ROOT/'source'/'localize_kit.py').write_text(Path(__file__).read_text(encoding='utf-8'),encoding='utf-8')
zipname=BASE/'洞洞板挂架_P1S_PETG_M4_中文分盘打印包.zip'
with zipfile.ZipFile(zipname,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob('*')):
        if p.is_file():z.write(p,'洞洞板挂架打印包/'+p.relative_to(ROOT).as_posix())
# Refresh the earlier download target too, so an old link gets the same current kit.
shutil.copy2(zipname,BASE/'MSkadis_P1S_PETG_M4_SML_print-kit.zip')
print(json.dumps({'renamed_files':len(changes),'plates':list(NAMES.values()),'zip':str(zipname.resolve()),'geometry_and_settings_unchanged':True},ensure_ascii=False))
