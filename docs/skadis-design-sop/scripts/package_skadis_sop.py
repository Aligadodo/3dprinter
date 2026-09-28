"""Validate local knowledge assets, render readable HTML, sync the published copy."""
from pathlib import Path
import json,hashlib,shutil,zipfile,re,html
import markdown
import trimesh
WORK=Path(__file__).resolve().parents[1];ROOT=WORK/'docs/skadis-design-sop'
catalog=json.loads((ROOT/'reference-index/catalog.json').read_text(encoding='utf8'))
assert not catalog['errors']
assert catalog['file_count']==len(catalog['files'])
assert catalog['mesh_count']==sum(len(f['objects']) for f in catalog['files'])
manifest=json.loads((ROOT/'components/manifest.json').read_text(encoding='utf8'))
for entry in manifest['records']:
 p=ROOT/'components'/entry['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256']
 mesh=trimesh.load(p);assert len(mesh.faces)>0
for p in ROOT.rglob('*.json'):json.loads(p.read_text(encoding='utf8'))
for p in ROOT.glob('*.md'):
 for dest in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf8')):
  if not re.match(r'\w+://',dest):assert (p.parent/dest.split('#')[0]).exists(),(p,dest)
for name in ['index_skadis_library.py','extract_3mf_component.py','build_skadis_knowledge.py','package_skadis_sop.py']:shutil.copy2(WORK/'scripts'/name,ROOT/'scripts'/name)
nav='<nav><a href="index.html">设计SOP</a> · <a href="reference-guide.html">选用指南</a> · <a href="reference-index/index.html">54个模型索引</a> · <a href="parameters.json">参数JSON</a> · <a href="components/manifest.json">组件清单</a></nav>'
css='body{font:17px/1.85 system-ui,"Microsoft YaHei";color:#22384b;background:#f5f7fa;max-width:1150px;margin:30px auto;padding:0 24px}article{padding:28px 40px;background:white;border-radius:12px}nav{position:sticky;top:0;background:#e6eff5;padding:15px;z-index:1}a{color:#086b9c}table{border-collapse:collapse;width:100%;font-size:15px}th,td{border:1px solid #d5dde3;padding:9px;vertical-align:top}h2{margin-top:38px;border-bottom:2px solid #d5dde3}pre{overflow:auto;background:#edf2f6;padding:16px}code{overflow-wrap:anywhere}img{max-width:100%}'
for src,dst in [('README.md','index.html'),('reference-guide.md','reference-guide.html'),('new-design-template.md','new-design-template.html')]:
 content=markdown.markdown((ROOT/src).read_text(encoding='utf8'),extensions=['tables','fenced_code'])
 content=content.replace('href="reference-guide.md"','href="reference-guide.html"').replace('href="new-design-template.md"','href="new-design-template.html"')
 (ROOT/dst).write_text(f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>宜家洞洞板配件设计SOP</title><style>{css}</style>{nav}<article>{content}</article></html>',encoding='utf8')
checks={'files_indexed':catalog['file_count'],'mesh_definitions':catalog['mesh_count'],'exact_duplicate_groups':len(catalog['exact_mesh_duplicates']),'reference_parse_errors':0,'components_checked':len(manifest['records']),'relative_markdown_links_pass':True,'json_parse_pass':True,'scope':'metadata/local bounds/asset integrity; no new load or physical testing'}
(ROOT/'verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf8')
(ROOT/'最新版说明.md').write_text('# 当前版本：SOP 1.2（2026-09-28）\n\n打开 index.html 阅读设计流程，reference-index/index.html 检索收藏。\n\n工程编辑源：D:/projects/3dprint/docs/skadis-design-sop。E盘此目录为同步副本。工作区AGENTS.md已登记：后续洞洞板任务先读取本SOP。\n\n当前床头夹具：床头夹具_A_V1.3_斜面防滑_多长度螺杆_二十盘。当前柜侧挂架：MSkadis挂架_V3.1_双侧斜坡螺母入口_十一盘。两套参数分别维护。\n\n未进行新的打印或承重试验。\n',encoding='utf8')
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(ROOT/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
dest=Path('E:/3dprint/自己设计合集/实用组件/宜家洞洞板配件设计SOP');shutil.copytree(ROOT,dest,dirs_exist_ok=True)
for rel,digest in hashes.items():assert hashlib.sha256((dest/rel).read_bytes()).hexdigest()==digest
archive=shutil.make_archive(str(dest),'zip',root_dir=dest.parent,base_dir=dest.name)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps(checks,ensure_ascii=False));print(dest)
