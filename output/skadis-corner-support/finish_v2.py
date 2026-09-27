from pathlib import Path
import json, shutil, hashlib, zipfile, html
BASE=Path(__file__).parent
ROOT=BASE/'releases'/'MSkadis挂架_V2.0_双孔简化试装版'
raw=json.loads((BASE/'slice-v2'/'result.json').read_text(encoding='utf8'))
assert raw['return_code']==0 and len(raw['sliced_plates'])==7
assert all(not p.get('warning_message') for p in raw['sliced_plates'])
stats=[{'plate':p['id'],'hours':round(p['total_predication']/3600,2),'grams':round(sum(f['total_used_g'] for f in p['filaments']),1),'warnings':p.get('warning_message',''),'objects':len(p['objects'])} for p in raw['sliced_plates']]
shutil.copy2(BASE/'slice-v2'/'result.json',ROOT/'技术资料'/'实际切片结果.json')
report='''# V2.0 双孔简化试装版

本版根据打印实物反馈重做接口，只保留两类新打印零件：S/M/L 主体挂架与5种板宽的横向连接板。保留旧V1文件，不混用两版配件。

## 变化与接口

- 挂架下部直接连接洞洞板，不再使用旧版挂扣背条、隔柱、锁紧垫圈、独立背部靠垫及前后续接盖板。
- 所有挂架宽44 mm；底部两孔横向排列，中心距25 mm，名义直径4.4 mm。孔中心距板接缝各12.5 mm，与 ModelB 标准B2、B4一致。左右两板边缘相接，不人为增加板缝。
- 家具侧接触面到洞洞板背面统一20.4 mm；这是整个下部座厚，包含竖臂，不是再向外增加20.4 mm。S/M/L竖臂厚10/12/14 mm，座部额外突出分别仅10.4/8.4/6.4 mm。
- ModelB含多个变体。此版对齐标准B2/B4的20.4 mm；带凸台的25.4 mm外包络变体不能仅按总厚度直接替代。实测来源及孔轮廓在“技术资料/ModelB实测.json”。
- 中部底边开口装入两颗M4普通六角螺母，再各自滑向左右孔位。螺母槽距板背贴合面3～6.6 mm。避让孔深16 mm，家具侧仍留4.4 mm后壁。
- 顶部依用户选择，保留L形，以防滑贴／粘胶固定；没有新增夹爪、绑带或打印限位配件。横向连接本身不能消除整组滑脱。

## 三种挂架

| 规格 | 顶臂搭接长度 | 下垂长度 | 臂厚 | 总宽 | 底部座厚 |
|---|---:|---:|---:|---:|---:|
| S | 60 | 90 | 10 | 44 | 20.4 |
| M | 90 | 110 | 12 | 44 | 20.4 |
| L | 120 | 130 | 14 | 44 | 20.4 |

单位mm。下垂从家具顶面计算，底部孔中心位于末端上方12.5 mm；板顶与挂架末端上方25 mm齐平。同一排使用同一S/M/L规格，确保顶臂高度及洞洞板高度一致。

## 连接板选型

| 洞洞板宽/挂架中心节距 | 中部净跨实体长度 | 两端搭接后零件总长 |
|---|---:|---:|
| 200 | 155.6 | 180 |
| 220 | 175.6 | 200 |
| 240 | 195.6 | 220 |
| 260 | 215.6 | 240 |
| 280 | 235.6 | 260 |

中部长度=板宽−44−0.4 mm，每端肩部留0.2 mm装配余量；两端另有搭接耳，每端与挂架重叠12 mm。因此**零件总长不是简单“板宽−挂架宽”**，因为需保留实际搭接承载和螺丝连接。连接板宽28 mm，中部厚6 mm，两端厚4 mm，每端两个Ø4.4 mm孔，孔距14 mm。

中间挂架可左右各接一块连接板，两端接口不会叠占同一螺丝位置。不同板宽可在同一排混用对应连接板，但板的顶角安装孔都必须距边12.5 mm；本次只直接测量了原200板及ModelB，其他宽度按这一系列孔位规则适配，打印前对照实际板孔。

## 螺丝与螺母：不要混用长度

| 部位 | 推荐与可用长度 | 螺母 | 注意 |
|---|---|---|---|
| 洞洞板→底部双孔座 | M4×16优先；M4×12、M4×18也支持 | 普通M4六角，名义对边7、厚3.2 mm | 按有效板厚5 mm；12 mm不加额外平垫 |
| 横向连接板→挂架顶臂 | M4×10；或M4×12配1 mm金属平垫 | 同上 | 每端2颗，每条共4颗；此处不要用16/18/25 mm |

底部螺丝在5 mm板背之后的伸入长度：12→7 mm，16→11 mm，18→13 mm；距盲孔底分别余9/5/3 mm。未把螺母后空间封死。

M4×12仅在有效板厚约5 mm、无额外垫片时保证本设计的完整螺母啮合，实际螺丝端部倒角、打印公差仍需试装；16 mm更有装配余量。16/18 mm若使用平垫，需核对实际啮合。M4×10不适用于底部板连接，M4×25不可用于新版这些盲孔。

本版按头底面平的螺钉计算长度（头底至尾端），新设计连接板不设锥形沉头。原洞洞板若用沉头螺钉，头部下沉量会改变有效长度，必须重新核对尾端余量；不可仅照名称“平头”替换。普通螺母槽不兼容厚的防松螺母、法兰螺母或热熔铜螺母。

## 装配顺序

1. 先装顶部连接板的螺母：从挂架顶臂侧面的槽口放入，分别对准两个竖向螺孔。连两侧时，左右各装两颗；排端只装内侧两颗。
2. 连接板薄端搭在相邻挂架顶臂上，每端用两颗M4×10锁紧。不要把6 mm厚的中部当作薄端。两挂架中心距应等于实际板宽。
3. 挂架下端中间的底边开口装入一颗M4螺母，向左推到孔位，再放入另一颗向右推。可用螺丝轻轻带住，避免搬动时退出。
4. 单板两端：挂架中心位于板的左右边缘，内侧各用一个孔，外侧孔预留。两板横向拼缝：中间一只挂架的两孔分别固定两板顶角，形成二板组合接口。
5. 板的下部靠位及向下串联沿用原ModelB连接件。原件与挂架座的家具接触面共面。没有另外增加新版背垫，也没有取消原有拼板必需的ModelB。
6. 顶臂下表面的平面贴防滑材料或粘胶，按所用材料要求处理表面和等待固化。尽量薄且各挂架等厚，避免厚泡棉使几何基准偏斜；若家具背面也贴保护材料，应让挂架与ModelB的接触层等厚。
7. 空载试装确认所有螺丝锁住板而非顶到盲孔底，再在下方有承托的条件下逐步加上真实物品，观察位移、胶层剥离和持续下垂。普通无粘性防滑贴仅提高摩擦，是否足够须用实际载荷验证。照片所示无贴/无胶状态不可直接复用。

对于N列板的顶排：需N+1只挂架、N条对应宽度连接板、2N颗底部板螺丝、4N颗顶部连接螺丝、6N颗螺母。不含原ModelB纵向拼接五金。例：单板用2只挂架+1连接板+2颗板螺丝+4颗顶螺丝+6螺母；两列用3+2+4+8+12。板的下排串联载荷仍经过板及ModelB，应同时检查原拼接处；没有假定横向连接能使各挂架完全均分载荷。

## 打印与选盘

1～3盘分别为S/M/L试装套装（2挂架+1条200连接板）；4～7盘为220/240/260/280连接板选配。不是每个用户都要打印七盘。所有对象中文命名、互不组合，可删除200连接板换成相应板宽，也可只补打中间挂架。

280连接板总长260 mm，已斜放在256 mm热床内，请保持方向；260板宽对应零件总长240 mm。主体L侧面贴床，使轮廓线连续绕过转角；连接板大平面贴床。P1S、0.4喷嘴、PETG、层高0.20、6墙、50% gyroid、上下各6层、不启用支撑。保存温度255°C/热床70°C、最大体积速度8 mm³/s，与此前PETG基础配置一致；根据实际线材校准。

## 已验证与未验证

八种单件全部为单一闭合实体，STL回读通过；七盘无越界或碰撞；套装间最小模型间距7 mm。进行了ModelB截面测量、M4螺丝实体避让检查、普通M4螺母插入路径检查及15组S/M/L与连接板装配干涉检查。七盘已通过本机Bambu Studio实际切片，返回码0、无警告。切片成功不等于实物强度合格。

这是一版可打印的试装改版，尚未经实物配合和持续承重试验，没有额定承重值，也不宣称只贴任意防滑材料即可保证不滑脱。先用一套所需尺寸试装，不必重复打印全套三种尺寸。
'''
(ROOT/'README_装配与螺丝.md').write_text(report,encoding='utf8')
rows=''.join(f'<tr><td>{s["plate"]}</td><td>{s["objects"]}</td><td>{s["hours"]}</td><td>{s["grams"]}</td><td>通过</td></tr>' for s in stats)
# Use a self-contained HTML viewer with prewrapped markdown text, all diagrams local.
imgs=''.join(f'<figure><img src="图解/{html.escape(p.name)}"><figcaption>{html.escape(p.stem)}</figcaption></figure>' for p in sorted((ROOT/'图解').glob('*.png')) if p.name[:2] in ['01','02','03'])
links=''.join(f'<li><a href="单盘工程/{html.escape(p.name)}">{html.escape(p.stem)}</a></li>' for p in sorted((ROOT/'单盘工程').glob('*.3mf')))
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>V2 双孔挂架 · 装配与打印</title><style>body{{max-width:1200px;margin:40px auto;padding:0 24px;background:#f5f7fa;color:#203348;font:17px/1.8 system-ui,"Microsoft YaHei"}}h1{{line-height:1.4}}img{{width:100%;border-radius:12px}}figure{{margin:30px 0}}figcaption{{color:#617488}}a{{color:#16766f}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}pre{{white-space:pre-wrap;font:inherit;padding:24px;background:white;border-radius:12px}}.note{{background:#fff0d5;padding:16px;border-radius:10px}}</style><h1>V2 双孔简化挂架</h1><p>3种主体＋5种连接板。保留L形，顶部使用防滑贴／粘胶。</p><p class="note">可打印试装版：七盘切片通过，尚无实物承重验证。先打印所需尺寸的一套。</p><p><a href="V2_七盘工程_独立零件_P1S_PETG.3mf">打开七盘总工程</a> · <a href="README_装配与螺丝.md">装配与螺丝说明</a></p>{imgs}<h2>选择打印盘</h2><ul>{links}</ul><table><tr><th>盘号</th><th>独立件数</th><th>预计小时</th><th>预计PETG克数</th><th>切片</th></tr>{rows}</table><h2>完整说明</h2><pre>{html.escape(report)}</pre></html>'''
(ROOT/'打开这里_装配与打印.html').write_text(page,encoding='utf8')
# A reproducible source bundle; functions are imported from these two archived scripts.
for name in ['build_print_kit.py','build_release_v1.py','finish_v2.py']:
    shutil.copy2(BASE/name,ROOT/'技术资料'/name)
dep=ROOT/'技术资料'/'print-kit-v1';dep.mkdir(exist_ok=True)
for name in ['P1S-PETG-settings.json','洞洞板挂架_P1S_PETG_M4_三种尺寸_中文分盘.3mf']:
    shutil.copy2(BASE/'print-kit-v1'/name,dep/name)
(ROOT/'技术资料'/'源代码说明.txt').write_text('build_v2.py使用本目录两个V1脚本中的纯函数；不会执行旧版建模。原始ModelB路径保留在脚本中。运行需要numpy/trimesh/manifold3d/shapely/Pillow。修改后重新运行建模，再调用Bambu Studio验证切片。finish_v2.py为本工作目录的发布归档脚本，切片结果目录需同步更新。print-kit-v1中的旧3MF仅供提取包装头信息，不属于本版打印对象。\n',encoding='utf8')
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(ROOT/'技术资料'/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
dest=Path(r'E:/3dprint/自己设计合集/实用组件')/ROOT.name
shutil.copytree(ROOT,dest,dirs_exist_ok=True)
for rel,digest in hashes.items():assert hashlib.sha256((dest/rel).read_bytes()).hexdigest()==digest,rel
archive=dest.parent/(ROOT.name+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(dest.rglob('*')):
        if p.is_file():z.write(p,Path(dest.name)/p.relative_to(dest))
print(json.dumps({'files_verified':len(hashes),'release':str(dest),'archive':str(archive),'slice':stats},ensure_ascii=False))
