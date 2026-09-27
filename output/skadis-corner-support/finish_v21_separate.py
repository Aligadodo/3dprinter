from pathlib import Path
import json, shutil, hashlib, zipfile, html
BASE=Path(__file__).parent
ROOT=BASE/'releases'/'MSkadis挂架_V2.1_免螺丝插接试装版_八盘分开'
raw=json.loads((BASE/'slice-v21-separate'/'result.json').read_text(encoding='utf8'))
assert raw['return_code']==0 and len(raw['sliced_plates'])==8
assert all(not p.get('warning_message') for p in raw['sliced_plates'])
shutil.copy2(BASE/'slice-v21-separate'/'result.json',ROOT/'技术资料'/'实际切片结果.json')
report='''# V2.1 免螺丝插接试装版

连接板改为两端插入挂架顶臂侧孔，取消连接板所有螺丝孔以及挂架顶臂的螺母槽。不增加独立锁扣、插销或夹片。连接板用于保持形态、限制相对转动和辅助传递力矩，不作为独立承重梁，也未验证均分载荷的比例。

## 插接尺寸与固定方式

- 挂架左右各有一个24.4×4.4 mm矩形盲插孔，深12.2 mm，两个孔之间保留19.6 mm实体。
- 连接板插舌截面24×4 mm，有1 mm平面导入斜角；每端实际插入12 mm。截面每侧间隙0.2 mm，孔底余量0.2 mm。
- 连接板中部宽28、厚6 mm，端部插舌厚4 mm。肩部与挂架侧面各留0.2 mm，便于装配。
- 不是过盈压入或自锁卡扣。未装洞洞板时可自由拔出；先插接，再拧紧底部洞洞板螺丝，利用板的固定孔约束挂架间距，限制插舌轴向退出。拆卸需先松开洞洞板连接，不能强掰顶臂。
- 矩形插舌限制转动，但有装配间隙和塑料变形；不要用连接板单独提起整组，不能假定它能承受单侧主架失效后的全部重量。
- 中间挂架左右可同时插接，插舌不相碰。同一排使用同一S/M/L规格。

## 挂架与连接板选型（mm）

| 挂架 | 顶臂长度 | 下垂长度 | 臂厚 | 宽 | 底部座厚 |
|---|---:|---:|---:|---:|---:|
| S | 60 | 90 | 10 | 44 | 20.4 |
| M | 90 | 110 | 12 | 44 | 20.4 |
| L | 120 | 130 | 14 | 44 | 20.4 |

| 适配板宽/挂架中心节距 | 中部实体长度 | 含插舌总长 |
|---|---:|---:|
| 200 | 155.6 | 180 |
| 220 | 175.6 | 200 |
| 240 | 195.6 | 220 |
| 260 | 215.6 | 240 |
| 280 | 235.6 | 260 |

中部长度=板宽−44−0.4；总长还包括两端插舌。S/M/L共用同一套连接板。280连接板已在P1S热床斜放，保持该方向。

## 底部接口保持不变

底部双孔直径4.4、孔距25 mm；两孔中心距拼板接缝各12.5 mm。家具接触面到板背20.4 mm，对齐ModelB标准B2/B4。ModelB另含25.4 mm外包络的凸台变体，本版未按那个总厚度设计。

螺母仍从底边中央开口装入，再左右滑到孔位。使用普通M4六角螺母，名义对边7、厚3.2 mm；不使用厚防松螺母或法兰螺母。槽深为距板背3～6.6 mm。

底部支持M4×12/16/18，优先16 mm。按5 mm有效板厚计算，螺丝进入座内7/11/13 mm，距16 mm深的避让孔底余9/5/3 mm，家具侧后壁4.4 mm。12 mm不加额外垫片，并需核对实际螺丝端部倒角及螺母啮合。新版本不再需要顶部M4×10螺丝；M4×25不能用于这些盲孔。

螺丝长度按头底至尾端计算。沉头螺丝下沉量会改变有效长度，必须另行核对尾端余量。适配其他板宽的前提是顶角孔仍距边12.5 mm；本次测量来自原200板和ModelB，其他尺寸打印前对照实际孔位。

## 装配

1. 选择对应板宽的插接板。将一端推入第一只挂架侧孔，再将第二只挂架套到另一端；检查每端约12 mm入孔。
2. 多列时依次加板与挂架，中间挂架左右各接一块。此时未自锁，平放组装并托住各零件。
3. 从挂架下端中央口放入M4螺母，分别滑向使用的孔。用M4×12/16/18固定洞洞板，确认锁紧的是板而非螺丝顶到盲孔底。
4. 单板最外侧两挂架各使用内侧一个孔；相邻两板拼缝处的挂架使用两个孔，各锁一块板。板边相接，不另留板缝。
5. 板下部支撑和纵向拼板继续用原ModelB，不再增加新版背条、隔柱和独立靠垫。
6. 顶臂下平面使用你选择的防滑贴／粘胶，贴层薄且等厚，按材料要求处理家具表面及等待固化。普通无粘性防滑贴能否满足实际负载仍需测试。

顶排N列需要N+1只挂架、N块插接板、2N颗底部M4螺丝及2N颗螺母。单板仅2颗螺丝+2颗螺母，连接板本身零五金。不含原ModelB纵向拼接的五金。

## 打印与验证

1～3盘分别仅放S/M/L挂架一对；4～8盘分别单独放200/220/240/260/280插接板一件。挂架与连接板不混盘，200插接板不再在三种挂架盘中重复。独立中文对象，可以单件补打。只选所需尺寸打印，不必把八盘都打完。V2.1挂架和连接板需成套使用，不能与V2.0的顶部螺丝接口混用。

P1S、0.4喷嘴、PETG、0.20层高、6墙、50% gyroid、上下各6层、不启用支撑；255°C喷嘴/70°C热床，体积速度上限8 mm³/s，按线材校准。主体侧面贴床，插接板大面贴床。矩形插孔打印后的桥接下垂与PETG尺寸误差可能影响手感，先试一套；清除毛刺，不能靠锤击硬装。

八种单件均为闭合单实体，STL回读通过；八盘摆放无碰撞越界；15种组合的最终装配与插入路径检查通过，中间挂架双向续接不干涉；底部螺丝避让和螺母装入路径检查通过。八盘实际切片全部返回成功且无警告。

这是试装版，尚未实物验证插接手感、长期变形及承重，无额定载荷。先空载组装，再在下方有承托的条件下逐渐加载，观察插接松动、支架位移和胶层剥离。横向辅助连接不替代家具端防滑固定。
'''
(ROOT/'README_插接装配.md').write_text(report,encoding='utf8')
rows=''.join(f'<tr><td>{p["id"]}</td><td>{p["total_predication"]/3600:.2f}</td><td>{sum(f["total_used_g"] for f in p["filaments"]):.1f}</td><td>通过</td></tr>' for p in raw['sliced_plates'])
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>V2.1 免螺丝插接挂架</title><style>body{{max-width:1200px;margin:40px auto;padding:0 24px;background:#f5f7fa;color:#203348;font:17px/1.8 system-ui,"Microsoft YaHei"}}img{{width:100%}}a{{color:#16766f}}table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}pre{{white-space:pre-wrap;font:inherit;padding:24px;background:white;border-radius:12px}}</style><h1>V2.1 免螺丝插接挂架</h1><p>先插连接板，再固定洞洞板。连接板无需五金；底部仍使用M4螺丝。</p><p><a href="V2.1_八盘工程_独立零件_P1S_PETG.3mf">打开打印工程</a> · <a href="README_插接装配.md">装配说明</a></p><img src="图解/01_免螺丝插接装配.png"><table><tr><th>盘号</th><th>预计小时</th><th>PETG克数</th><th>实际切片</th></tr>{rows}</table><pre>{html.escape(report)}</pre></html>'''
(ROOT/'打开这里_免螺丝插接说明.html').write_text(page,encoding='utf8')
for name in ['build_print_kit.py','build_release_v1.py','finish_v21_separate.py']:
    shutil.copy2(BASE/name,ROOT/'技术资料'/name)
dep=ROOT/'技术资料'/'print-kit-v1';dep.mkdir(exist_ok=True)
for name in ['P1S-PETG-settings.json','洞洞板挂架_P1S_PETG_M4_三种尺寸_中文分盘.3mf']:
    shutil.copy2(BASE/'print-kit-v1'/name,dep/name)
(ROOT/'技术资料'/'源代码说明.txt').write_text('build_v21.py仅提取两个V1脚本中的纯函数，不执行旧版建模；依赖numpy/trimesh/manifold3d/shapely/Pillow及脚本中指定路径的原ModelB。print-kit-v1中的旧3MF仅供提取包装头，不是本版打印对象。finish_v21_separate.py为原工作目录的发布脚本，需要slice-v21-separate下的实际切片结果。',encoding='utf8')
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(ROOT/'技术资料'/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
dest=Path(r'E:/3dprint/自己设计合集/实用组件')/ROOT.name
shutil.copytree(ROOT,dest,dirs_exist_ok=True)
for rel,h in hashes.items():assert hashlib.sha256((dest/rel).read_bytes()).hexdigest()==h
with zipfile.ZipFile(dest.parent/(dest.name+'.zip'),'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(dest.rglob('*')):
        if p.is_file():z.write(p,Path(dest.name)/p.relative_to(dest))
print('Published and verified',len(hashes),'files; eight plates passed without warnings')
