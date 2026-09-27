"""Read-only 3MF inventory. Re-run to refresh the local reference index."""
from pathlib import Path
import argparse,zipfile,hashlib,json,csv,html,re
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from io import BytesIO

C='{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',default='E:/3dprint/模型收藏合集/宜家洞洞板系列收藏');ap.add_argument('--output',default='docs/skadis-design-sop/reference-index');args=ap.parse_args()
 src=Path(args.source);out=Path(args.output);out.mkdir(parents=True,exist_ok=True);(out/'thumbnails').mkdir(exist_ok=True)
 files=[];errors=[]
 for index,p in enumerate(sorted(src.rglob('*.3mf')),1):
  row={'id':f'R{index:03}','relative_path':p.relative_to(src).as_posix(),'absolute_path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'objects':[]}
  try:
   with zipfile.ZipFile(p) as z:
    roots={n:ET.fromstring(z.read(n)) for n in z.namelist() if n.lower().endswith('.model')}
    root=roots.get('3D/3dmodel.model');row['metadata']={m.get('name'):m.text or '' for m in root.findall(C+'metadata')};row['unit']=root.get('unit','millimeter')
    names={};subtypes={};row['plate_count']=None
    if 'Metadata/model_settings.config' in z.namelist():
     cfg=ET.fromstring(z.read('Metadata/model_settings.config'));row['plate_count']=len(cfg.findall('plate'))
     for o in cfg.findall('object'):
      nm=o.find("metadata[@key='name']");names[o.get('id')]=nm.get('value','') if nm is not None else ''
      for part in o.findall('part'):subtypes[(o.get('id'),part.get('id'))]=part.get('subtype','unknown')
     row['project_object_names']=list(names.values())
    links={};roles={}
    for o in root.findall('.//'+C+'resources/'+C+'object'):
     for comp in o.findall(C+'components/'+C+'component'):
      path=next((v for k,v in comp.attrib.items() if k.endswith('}path')), '3D/3dmodel.model').lstrip('/')
      links.setdefault((path,comp.get('objectid')),[]).append(names.get(o.get('id'),o.get('name','')))
      roles.setdefault((path,comp.get('objectid')),[]).append(subtypes.get((o.get('id'),comp.get('objectid')),'unknown'))
    for member,r in roots.items():
     for o in r.findall(C+'resources/'+C+'object'):
      mesh=o.find(C+'mesh')
      if mesh is None:continue
      verts=mesh.find(C+'vertices');tris=mesh.find(C+'triangles')
      vv=np.array([[float(v.get(k)) for k in ['x','y','z']] for v in verts]);ff=np.array([[int(t.get(k)) for k in ['v1','v2','v3']] for t in tris],dtype=np.int64)
      geometry_hash=hashlib.sha256(vv.astype('<f8').tobytes()+ff.astype('<i8').tobytes()).hexdigest()
      row['objects'].append({'member':member,'object_id':o.get('id'),'name':o.get('name') or names.get(o.get('id')) or ' / '.join(dict.fromkeys(links.get((member,o.get('id')),[]))),'vertex_count':len(vv),'triangle_count':len(ff),'local_bounds':np.round([vv.min(0),vv.max(0)],5).tolist(),'local_extents':np.round(np.ptp(vv,axis=0),5).tolist(),'unit':r.get('unit',row['unit']),'geometry_sha256':geometry_hash})
      row['objects'][-1]['part_subtypes']=list(dict.fromkeys(roles.get((member,o.get('id')),[subtypes.get((o.get('id'),o.get('id')),'unknown')])))
    row['build_instances']=len(root.findall(C+'build/'+C+'item'))
    candidates=['Auxiliaries/.thumbnails/thumbnail_3mf.png','Metadata/plate_1.png','Metadata/plate_no_light_1.png']
    thumb=next((n for n in candidates if n in z.namelist()),None)
    if thumb:
     im=Image.open(BytesIO(z.read(thumb))).convert('RGBA');im.thumbnail((480,360));im.save(out/'thumbnails'/f'{row["id"]}.png');row['thumbnail']=f'thumbnails/{row["id"]}.png';row['thumbnail_source']=thumb
    if 'Metadata/project_settings.config' in z.namelist():
     try:
      settings=json.loads(z.read('Metadata/project_settings.config'));row['saved_print_settings']={k:settings[k] for k in ['printer_model','printer_settings_id','filament_type','layer_height','wall_loops','sparse_infill_density','enable_support','support_type'] if k in settings}
     except (ValueError,UnicodeDecodeError):row['settings_parse']='not JSON'
   files.append(row)
  except Exception as e:row['error']=str(e);files.append(row);errors.append({'file':str(p),'error':str(e)})
  print(row['id'],len(row['objects']),flush=True)
 groups={}
 for f in files:
  for o in f['objects']:groups.setdefault(o['geometry_sha256'],[]).append({'file_id':f['id'],'file':f['relative_path'],'member':o['member'],'object_id':o['object_id'],'name':o['name']})
 dup=[v for v in groups.values() if len(v)>1]
 data={'source_root':str(src),'bounds_semantics':'Untransformed mesh-local XYZ in declared model unit, not assembly size or interface measurement. Thumbnails are source-supplied, not newly verified renders. Identical hashes require identical vertex/triangle order.','file_count':len(files),'mesh_count':sum(len(f['objects']) for f in files),'errors':errors,'files':files,'exact_mesh_duplicates':dup}
 (out/'catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
 with (out/'objects.csv').open('w',encoding='utf-8-sig',newline='') as fp:
  w=csv.writer(fp);w.writerow(['文件ID','模型文件','网格成员','对象ID','对象名称','局部X','局部Y','局部Z','单位','三角面数','作者','许可原文'])
  for f in files:
   for o in f['objects']:w.writerow([f['id'],f['relative_path'],o['member'],o['object_id'],o['name'],*o['local_extents'],o['unit'],o['triangle_count'],f['metadata'].get('Designer',''),f['metadata'].get('License','')])
 cards=[]
 for f in files:
  meta=f.get('metadata',{});desc=html.unescape(html.unescape(meta.get('Description','')));desc=re.sub('<[^>]+>',' ',desc)
  rows=''.join('<tr>'+''.join(f'<td>{html.escape(str(v))}</td>' for v in [o['name'] or '(unnamed)',o['member']+' #'+o['object_id'],' × '.join(str(x) for x in o['local_extents']),o['triangle_count']])+'</tr>' for o in f['objects'])
  thumb=f'<img src="{f["thumbnail"]}">' if f.get('thumbnail') else ''
  cards.append(f'<article><h2>{f["id"]} · {html.escape(f["relative_path"])}</h2>{thumb}<p>作者：{html.escape(meta.get("Designer", "未记录"))}　许可字段：{html.escape(meta.get("License", "未记录"))}</p><p>盘数：{f.get("plate_count")}　网格：{len(f["objects"])}　单位：{f.get("unit")}</p><details><summary>网格定位及原包描述</summary><table><tr><th>对象</th><th>ZIP成员 / ID</th><th>局部XYZ包络</th><th>面数</th></tr>{rows}</table><p>{html.escape(desc[:5000])}</p></details></article>')
 page='<!doctype html><meta charset="utf-8"><title>洞洞板参考模型索引</title><style>body{font:16px/1.7 system-ui;max-width:1200px;margin:30px auto;background:#f5f7fa;color:#20374c}input{width:95%;padding:14px}article{background:white;padding:22px;margin:18px 0;border-radius:12px}img{max-width:360px;max-height:240px}td,th{padding:8px;border-bottom:1px solid #ccc;text-align:left}table{width:100%;font-size:13px}h2{font-size:21px}</style><h1>洞洞板参考模型索引</h1><p>离线索引；预览来自原3MF。包络为网格局部尺寸，不能作为挂孔、螺纹或装配尺寸。原包说明仅作来源资料。</p><input id="search" placeholder="搜索文件名、对象名、作者或描述"><p id="count"></p>'+''.join(cards)+'<script>const q=document.getElementById("search"),a=[...document.querySelectorAll("article")];function filter(){let n=0;for(const x of a){x.hidden=!x.textContent.toLowerCase().includes(q.value.toLowerCase());if(!x.hidden)n++}document.getElementById("count").textContent=n+" 个文件"}q.addEventListener("input",filter);filter()</script>'
 (out/'index.html').write_text(page,encoding='utf8')
 font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
 for start in range(0,len(files),18):
  subset=files[start:start+18];sheet=Image.new('RGB',(1200,((len(subset)+3)//4)*230),'#eef2f6');d=ImageDraw.Draw(sheet)
  for j,f in enumerate(subset):
   x=(j%4)*300;y=(j//4)*230
   if f.get('thumbnail'):
    im=Image.open(out/f['thumbnail']).convert('RGBA');im.thumbnail((285,185));sheet.paste(im,(x+(300-im.width)//2,y),im)
   label=f['id']+' '+Path(f['relative_path']).stem;d.text((x+6,y+185),label[:27],fill='#20374c',font=font);d.text((x+6,y+207),label[27:54],fill='#20374c',font=font)
  sheet.save(out/f'contact-{start//18+1}.jpg')
 print(json.dumps({'files':len(files),'meshes':data['mesh_count'],'duplicate_groups':len(dup),'errors':errors}))
if __name__=='__main__':main()
