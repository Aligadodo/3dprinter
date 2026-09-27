from pathlib import Path
import json,shutil,zipfile,hashlib,html,csv
BASE=Path(__file__).parent;ROOT=BASE/'releases'/'床头夹具_A_V1.1_左右斜坡螺母入口_十九盘'
result=json.loads((BASE/'slice-v11'/'result.json').read_text(encoding='utf8'))
assert result['return_code']==0 and len(result['sliced_plates'])==19,result.get('error_string')
warnings=[{'id':p['id'],'warning':p.get('warning_message')} for p in result['sliced_plates'] if p.get('warning_message')]
shutil.copy2(BASE/'slice-v11'/'result.json',ROOT/'技术资料'/'实际切片结果.json')
manifest=json.loads((ROOT/'技术资料'/'清单.json').read_text(encoding='utf8'))
rows=[]
for p,m in zip(result['sliced_plates'],manifest):
 rows.append({'盘号':p['id'],'名称':m['plate'],'耗材克':round(sum(f['total_used_g'] for f in p['filaments']),1),'预计小时':round(p['total_predication']/3600,2),'警告':p.get('warning_message') or ''})
with (ROOT/'技术资料'/'逐盘耗材时间.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
report='''# 床头夹具 A V1.1：双接口、三档厚度、三种宽度

本版为完整设计与切片后的试装版，包含18种主体、共用粗螺杆和3种接口试配件。尚未做实物承重及长期夹紧验证，没有额定载荷。

## 如何选择

夹持厚度有20～40、35～55、50～70 mm三档，覆盖20～70 mm。范围重叠时优先选择较小开口；例如38 mm板选20～40档，53 mm板选35～55档。

每档有36、44、60 mm主体宽度。宽度沿床头板左右方向测量，不是可夹厚度，也不代表经过验证的承重等级。挂钩款连接头宽度为max(主体宽,54) mm；螺丝款连接头宽度为max(主体宽,44) mm。小宽主体的头部局部加宽以容纳固定孔距，不缩小接口。

所有款式前夹臂基础厚14 mm；螺丝款局部座厚20.4 mm，延续原V3.0/ModelB标准。顶梁基础厚14 mm。主体总高度约60 mm；上排挂钩钩尖与顶梁上表面齐平，螺丝孔中心距顶梁上表面16 mm。不再用H65/H90下垂系列。

## 打印文件与分盘

- 主工程：床头夹具_A_V1.1_十九盘_P1S_PETG.3mf。
- 第01盘：四挂钩、母螺口、M4双孔座三个小样，加一根正式共用螺杆。建议先打印，用自己的洞洞板和M4螺母检查手感。
- 第02～10盘：挂钩款9个规格。
- 第11～19盘：螺丝款9个规格。
- 每个成套盘均含同规格主体2件、共用粗螺杆2件。只选所需的一盘，不需要将19盘全部打印。
- 每盘还有单独3MF，便于打开某一尺寸。所有零件是独立对象；单件STL可补打。22种单件包括18种主体、1种螺杆、3种小样。

命名固定为“床头夹具_挂钩H4或螺丝S_夹下限-上限_宽主体宽度”。打印盘名称、对象名称和STL名称一致。螺杆不区分尺寸，三档、三宽、两接口全部通用。

## H4挂钩款

接口按用户提供的桌边夹具3MF内洞洞板实测：板厚5 mm，长孔约5.2×15.2 mm，同排/同列40 mm。四钩列距40、排距40 mm；使用相隔40 mm的两排孔，不使用中间错排孔。

每钩宽4.4 mm，与样例孔每侧留约0.4 mm；喉口5.8 mm。钩尖横向圆弧R2.2，侧面轮廓R0.55，并圆滑处理入口。主体外角也做圆角。旧概念图中的5.2 mm宽占位挂钩已经替换，不能混用旧概念STL。

板在最终座位时，背面距夹体前面约0.3 mm。先将四个长孔同时对准挂钩，套入，再向下落约7.2 mm，四个挂钩共同承托。拆卸要先托住洞洞板，向上抬起后再向外移出。禁止从下方向上硬顶整板或不抬起就向外掰。

本版按用户要求取消防上抬保险扣和螺杆防退件。挂钩有朝外方向的几何限位，但仍可向上抬起拆卸。四挂钩指每个夹具；整块板图示/成套配置为一对夹具。

真实宜家板、不同打印板及涂层厚度可能有差别；用第01盘确认自己的孔距、孔宽和板厚。若四钩不能同时轻松套入，不要强压，应按实物调整接口。

## S螺丝款

延续原V3.0/ModelB双孔定位接口：孔径4.4、横向孔距25、前座总厚20.4 mm。适合原有组合板角孔/ModelB拼接体系；它不是任意宜家原装板孔位的通用适配器。与H4的40 mm挂孔网格不要混淆。

使用普通M4六角螺母（对边7、厚约3.2 mm）。左右侧各有一个独立入口，分别通向对应螺丝孔，原底部中央T槽已封闭。先将螺母平贴槽内、上下两边保持水平，从侧面沿15°向内下倾的导槽轻推到内端，再对齐孔位拧入螺丝。建议先装好两颗螺母再把夹具套到床头板上。

导槽轴向厚4.0 mm，对边包络7.6 mm；入口扩口厚约4.8 mm、高约9.0 mm，约2 mm长的导入段。相比3.2 mm厚的标准螺母，两侧各留0.4 mm轴向余量。内端封闭用于限制越位，两条槽不相通。不适配厚防松螺母或法兰螺母。15°是装配方向的浅坡，不代表打印时所有内壁都可无支撑；沿用原侧放方向和自动支撑。

浅坡用于导向，能否靠自重滑动取决于打印粗糙度和摩擦，必要时轻推；清除支撑后先试配，不能保证螺母自动滑到底。未上螺丝前侧口仍可退出螺母，装配时避免反向倾斜。

按5 mm有效板厚，优先使用M4×16，也检查了M4×12/18。盲孔家具侧保留4.4 mm后壁；对应12/16/18 mm螺丝，尾端距盲孔底分别为9/5/3 mm。长度从头底量起，采用平底头；沉头、垫片或其他板厚会改变有效长度，需重新核对。不要让螺丝顶到盲孔底后误以为板已锁紧。

原ModelB拼缝的25 mm双孔可以各固定一块板；单板外侧支点通常仅用其内侧一孔，按已有板的实际孔位选择。不要为凑孔位强行拉扯洞洞板。

## 共用粗螺杆

外螺纹、旋钮轮廓及母螺纹来自用户提供的桌边夹具模型，并非以标准公制螺纹近似重画。牙顶直径约15.38 mm，螺距约4 mm，不等于标准M16螺纹。

原杆40 mm＋旋钮15 mm＝55 mm。本版保留原牙型，将杆根截短5 mm，旋钮截为10 mm，得到杆身35＋旋钮10＝45 mm。螺口周围原材料与新后夹臂布尔融合，形成一体后夹臂，不新增独立螺母。所有夹体共用这根45 mm螺杆。

粗螺杆端面直接顶紧家具背面，无活动挡板。可以在家具接触位置贴薄保护片，保护片厚度会占用夹持余量。只用手轮拧紧，不加长杠杆；过度拧紧不能换取经过验证的额定承重。

分档减少空余开口和顶梁悬伸，但在螺杆顶住板材后，板背到手轮末端仍约45 mm。还需要手指操作余量，不能按零墙缝安装。所有档位最薄端手轮与后臂仍留约2.35 mm轴向间隙。

## 接触面与安装

设计尺寸按前面1 mm、顶面1 mm薄保护垫示意。有效净口（从前保护垫表面量起）分别42/57/72 mm，最大板厚时留2 mm调节余量。保护垫不包含在PETG打印盘里，可用等厚软片裁切；没有软垫时接触位置和余量会变化。

先选能跨过板顶且后方能操作的部位，套上两个夹具，校齐位置，再交替拧紧两根粗螺杆。顶梁通过保护垫坐在板顶，承担向下的力；不要只靠侧面摩擦悬吊。之后安装洞洞板，确认所有挂钩/螺丝都落位。

新夹具不含额外横向连接板，也不改变此前ModelB纵向拼接件。若洞洞板向下延伸较长，可沿用与当前板背距离匹配的下部支撑件以限制摆动。不要假定旧20.4 mm支撑块与H4较薄接口自动齐平。

## 打印设置与清理

工程设为P1S、0.4喷嘴、PETG、0.20 mm层高、6墙、主体50% gyroid填充、螺杆100%填充。使用基础PETG配置中的255°C喷嘴、70°C热床、8 mm³/s体积速度上限作为起点，按线材校准。

主体侧放，使夹体轮廓位于打印层平面；螺杆旋钮底面朝下。因窄主体的接口头加宽，以及横向母螺纹和螺母槽，工程启用了自动普通支撑，并允许模型表面起支撑。保持工程方向，打印后清除头部下方、钩口、螺母槽和母螺纹的支撑/毛刺，再试旋，不靠强拧清理螺纹。

若试配偏紧，先检查象脚和支撑残留；不要整体缩放主体或螺杆，整体缩放会改变孔距、螺距和厚度。需要调公差时应修改指定配合面并重新验证。

## 验证边界

已检查22种最终STL回读为封闭单实体；19盘摆放边界及对象间隙；共用螺纹在20 mm有效行程的81个相位位置无实体干涉；挂钩套入与下落路径73个位置无实体干涉，落座后直接外拉会被钩唇阻挡；全部9种螺丝款的M4左右斜坡插入路径（每侧81个位置）、旧T槽封闭和内端止挡，以及12/16/18 mm螺丝尾端避让。

这些是几何与切片检查，不等于实际摩擦力、强度、长期蠕变或打印公差验证。首次使用先空载试装，再在下方有承托的条件下逐步加物；本版没有额定承重。螺杆没有防退锁，使用后应检查夹紧状态。

## 来源

主夹体尺寸、接口位置、分档和圆角改进来自本次设计。粗螺纹、旋钮形状和母螺纹来自用户提供的“桌边洞洞板夹具.3mf”，原包元数据署名Ms，许可字段为Standard Digital File License。本交付保留来源记录；复用部分不标为原创。
'''
report+='\n## 十九盘实际切片结果\n\n| 盘号 | 对应配置 | 克数 | 小时 | 切片警告 |\n|---|---|---:|---:|---|\n'
for r in rows:report+=f"| {r['盘号']} | {r['名称']} | {r['耗材克']} | {r['预计小时']} | {r['警告'] or '无'} |\n"
(ROOT/'README_选型打印与安装.md').write_text(report,encoding='utf8')
links=''.join(f'<tr><td>{r["盘号"]}</td><td><a href="单盘工程/{m["plate"]}.3mf">{html.escape(r["名称"])}</a></td><td>{r["耗材克"]}</td><td>{r["预计小时"]}</td></tr>' for r,m in zip(rows,manifest))
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>床头夹具 A V1.1</title><style>body{{max-width:1250px;margin:36px auto;padding:0 24px;font:17px/1.75 system-ui,"Microsoft YaHei";color:#20374c;background:#f6f8fb}}img{{width:100%}}a{{color:#166a96}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #ccd3da;padding:9px;text-align:left}}pre{{white-space:pre-wrap;font:inherit}}</style><h1>床头夹具 A V1.1 · 18种规格</h1><p><a href="床头夹具_A_V1.1_十九盘_P1S_PETG.3mf">完整十九盘工程</a> · <a href="README_选型打印与安装.md">选型与装配说明</a> · 先打印第01盘试配，仅选所需的一盘成套打印。</p><img src="图解/01_双接口与全尺寸.png"><img src="图解/02_圆角挂钩与安装.png"><img src="图解/03_左右斜坡螺母入口.png"><h2>单盘选择</h2><table><tr><th>盘号</th><th>配置</th><th>克数</th><th>预计小时</th></tr>{links}</table><h2>完整说明</h2><pre>{html.escape(report)}</pre></html>'''
(ROOT/'打开这里_选型与装配.html').write_text(page,encoding='utf8')
for n in ['finish_v11.py','draw_v11.py','draw_side_entry_v11.py','verify_v11.py','prepare_v11.py','update_docs_v11.py','thread_fit.py']:shutil.copy2(BASE/n,ROOT/'技术资料'/n)
# Save exact upstream metadata separately without distributing the whole reference archive.
original=Path(r'E:/3dprint/模型收藏合集/宜家洞洞板系列收藏/桌边洞洞板夹具.3mf')
with zipfile.ZipFile(original) as z:(ROOT/'来源'/'原模型元数据与组件关系.xml').write_bytes(z.read('3D/3dmodel.model'))
(ROOT/'来源'/'来源记录.json').write_text(json.dumps({'file':str(original),'sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'screw_member':'3D/Objects/object_16.model','female_thread_member':'3D/Objects/object_17.model','pegboard_member':'3D/Objects/object_4.model'},ensure_ascii=False,indent=2),encoding='utf8')
# Keep the geometric builder reproducible in the current workspace; document its paths.
(ROOT/'技术资料'/'重建说明.txt').write_text('build_v11.py在D:/projects/3dprint工作目录运行，依赖output/bedhead-clamp-concepts/revision-a中的源网格，以及output/skadis-corner-support中的既有工程序列化函数和P1S设置。参考网格已保存在本包来源目录。Python依赖numpy/trimesh/manifold3d/shapely/Pillow。图片使用最终导出STL的软件深度渲染。',encoding='utf8')
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(ROOT/'技术资料'/'SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
dest=Path(r'E:/3dprint/自己设计合集/实用组件')/ROOT.name
shutil.copytree(ROOT,dest,dirs_exist_ok=True)
archive=shutil.make_archive(str(dest),'zip',root_dir=dest.parent,base_dir=dest.name)
print(json.dumps({'directory':str(dest),'zip':archive,'plates':len(rows),'warnings':warnings,'models':22},ensure_ascii=False))
