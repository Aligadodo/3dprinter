from pathlib import Path
import json, shutil, zipfile, hashlib, re
import markdown

BASE=Path(__file__).parent
SRC=BASE/'releases'/'MSkadis挂架_V3.1_双侧斜坡螺母入口_十一盘'
OUT=BASE/'publication'/'MSkadis挂架_V3.1_双侧入口发布材料_20260927'
(OUT/'配图').mkdir(parents=True,exist_ok=True)
body='''# 洞洞板桌沿／柜侧挂架

**三种顶臂长度 × 两种下垂高度，统一接口，按空间选尺寸。**

这是一套用于将兼容洞洞板布置在桌沿、柜侧的 L 形挂架。顶臂搭在家具上表面，洞洞板固定在挂架下部；多块板横向组合时，可以通过插接式连接板连接相邻挂架。

本套件只包含两类打印件：**主体挂架、横向连接板**。连接板无需额外螺丝；固定洞洞板仍需 M4 螺丝和螺母。

> **先看这三点：**
> - 适配采用本文角孔标准的洞洞板，并非所有洞洞板通用。
> - 顶臂需要配合防滑贴／粘胶使用，单靠 L 形搭放不能保证不滑落。
> - 已完成几何和切片检查，尚无实物承重验证及额定承重值。

## 主要特点

- **尺寸分开选：**顶臂选 60／90／120 mm，下垂选 90 mm 标准版或 65 mm 短版。
- **厚度统一：**六种挂架统一宽 44 mm、主体臂厚 14 mm、底部安装座总厚 20.4 mm。
- **双孔拼接：**底部两孔中心距 25 mm，中间挂架可同时固定相邻两块板的顶角。
- **横梁免螺丝：**连接板两端插入侧孔，用于保持间距、辅助限制摆动和传递力矩。
- **侧面装螺母、长螺丝有避让：**螺母从左右两侧分别装入，后方保留螺丝尾端空间，支持符合下文条件的 M4×12／16／18。
- **分盘更直观：**六种挂架与五种连接板分别摆盘，按需选盘，不必全部打印。

## 1. 先确认是否适配

本版依据 MSkadis 200 板及 ModelB 标准 B2／B4 连接件的几何尺寸设计。

| 检查项 | 本版对应标准 |
|---|---|
| 洞洞板有效安装厚度 | 约 5 mm，用于下文螺丝长度计算 |
| 板顶角安装孔位置 | 距相邻两边各 12.5 mm |
| 两块板相接处的角孔中心距 | 25 mm，不额外增加板缝 |
| 挂架安装孔直径 | 4.4 mm，对应 M4 螺丝 |
| 板背至家具接触面的距离 | 20.4 mm |

ModelB 文件中还包含其他变体，本版以 **20.4 mm 厚的标准件**为基准，不按带凸台变体的 25.4 mm 总外包络设计。

200／220／240／260／280 mm 的连接板规格，均以“顶角孔距边 12.5 mm”为适配前提。其他宽度板型请先核对实际孔位；不能仅凭板宽相同就认定兼容。洞洞板、原 ModelB 拼接件及收纳配件不包含在本套挂架模型内。

家具顶面需要有对应长度的可用搭接空间，侧面需能让挂架和板背支撑贴合。请同时检查抽屉、柜门以及板上收纳件的活动空间。

## 2. 六种挂架怎么选

### 第一步：选顶臂长度

顶臂提供 **60／90／120 mm** 三档，根据家具顶面的可用空间选择。这里的长度指从家具边缘向内的搭接长度，不是模型整体外包络长度。

### 第二步：选下垂高度

- **标准版：统一下垂 90 mm。**洞洞板安装位置相对更低，板顶距家具顶面约 65 mm。
- **短版：统一下垂 65 mm。**相对标准版将洞洞板抬高 25 mm，节约材料和时间；板顶距家具顶面约 40 mm。

下垂高度从家具顶面量到挂架下端，不包含上方 14 mm 的顶臂厚度。标准版整体高度为 104 mm，短版为 79 mm。

| 盘号 | 款式 | 顶臂长度 | 下垂高度 | 每盘数量 |
|---|---|---:|---:|---:|
| 01 | 标准版 | 60 mm | 90 mm | 挂架 2 只 |
| 02 | 标准版 | 90 mm | 90 mm | 挂架 2 只 |
| 03 | 标准版 | 120 mm | 90 mm | 挂架 2 只 |
| 04 | 短版 | 60 mm | 65 mm | 挂架 2 只 |
| 05 | 短版 | 90 mm | 65 mm | 挂架 2 只 |
| 06 | 短版 | 120 mm | 65 mm | 挂架 2 只 |

**六种挂架的共同规格：**宽 44 mm、主体臂厚 14 mm、底座总厚 20.4 mm，孔位、螺母槽、插接接口及螺丝规格一致。底座总厚度已经包含竖臂，不是在竖臂外再增加 20.4 mm。

名称直接标尺寸，例如：`挂架_顶臂60_下垂65_短版`。同一排必须选相同下垂高度，标准版与短版不要混排；初次安装建议同排也选相同顶臂长度。

## 3. 连接板怎么选

**按洞洞板宽度选连接板，不按顶臂长度选。**六种挂架共用以下五种连接板。

| 盘号 | 适配洞洞板宽度 | 连接板实际总长 | 每盘数量 |
|---|---:|---:|---:|
| 07 | 200 mm | 180 mm | 1 块 |
| 08 | 220 mm | 200 mm | 1 块 |
| 09 | 240 mm | 220 mm | 1 块 |
| 10 | 260 mm | 240 mm | 1 块 |
| 11 | 280 mm | 260 mm | 1 块 |

连接板中段厚 6 mm，插舌厚 4 mm；两端各插入挂架约 12 mm。矩形截面用于限制相对转动，插舌与孔每侧预留 0.2 mm 间隙。

**装配顺序是先插连接板，再固定洞洞板。**插接不是自锁卡扣，未装洞洞板时可以拔出。固定洞洞板后，其安装孔会约束挂架间距，限制插舌退出。连接板是辅助定位件，不应单独提起整组，也不代表各挂架能完全均分载荷。

## 4. 螺丝、螺母与数量

### 六种挂架使用同一套五金标准

| 用途 | 规格 | 说明 |
|---|---|---|
| 固定洞洞板 | **M4×16，优先选择** | 六种挂架通用 |
| 可选长度 | M4×12／M4×18 | 按有效板厚 5 mm 核算，条件见下文 |
| 螺母 | 普通 M4 六角螺母 | 名义对边 7 mm、厚约 3.2 mm |
| 横向连接板 | 无需五金 | 两端直接插接 |
| 顶部防滑固定 | 防滑贴／粘胶 | 根据家具表面与实际负载选用 |

以 5 mm 有效板厚计算：

| 螺丝长度 | 进入挂架座内的长度 | 距避让孔底的余量 |
|---|---:|---:|
| M4×12 | 7 mm | 9 mm |
| M4×16 | 11 mm | 5 mm |
| M4×18 | 13 mm | 3 mm |

螺丝长度按**头底至尾端**计算。M4×12 不加额外垫片，并需核对实物啮合；使用平垫或不同板厚时，应重新核对啮合及尾端余量。以上按头底面为平面的螺丝计算，沉头螺丝的下沉量会改变有效长度，不能直接按同一表格替换。

不要把 M4×10 用于底部板连接，也不要把 M4×25 拧入本版盲孔。螺母槽不适用于厚防松螺母、法兰螺母或热熔铜螺母。

### 双侧入口怎样装螺母

左右入口分别通向各自螺孔。入口外扩，螺母槽厚4.0 mm，给3.2 mm厚的普通M4螺母留出余量；导槽对边7.5 mm，朝孔位方向缓降约3 mm，中心导向坡度约17.5°。底面与中央保留实体。

坡道用于辅助滑入，尚未实测自行滑动效果。打印毛刺和表面摩擦可能影响滑动，轻推或稍倾斜即可辅助；螺母就位后需通过正面的安装螺丝固定。侧口位于板背后，靠墙较紧时请先装螺母，再将挂架组放到家具上。

### 常见组合需要多少零件

| 顶排组合 | 挂架 | 连接板 | M4 板连接螺丝 | M4 螺母 |
|---|---:|---:|---:|---:|
| 单列 1 块板 | 2 只 | 1 块 | 2 颗 | 2 颗 |
| 横向 2 列 | 3 只 | 2 块 | 4 颗 | 4 颗 |
| 横向 3 列 | 4 只 | 3 块 | 6 颗 | 6 颗 |

以上不包含原 ModelB 拼板连接所需的五金。单板两端各使用挂架的内侧孔；横向拼缝处的中间挂架使用两个孔，各固定一块板。

**举例：**一块 200 mm 宽的板，想选 90 mm 顶臂、65 mm 下垂：打印 **第 05 盘＋第 07 盘**，准备 2 颗 M4×16、2 颗普通 M4 螺母，以及顶部防滑固定材料。

## 5. 装配步骤

1. **试配插接板。**将连接板一端插入第一只挂架，再将另一只挂架套上另一端；确认每端约 12 mm 入孔。先清理毛刺，不要敲击硬装。
2. **扩展横向组合。**需要多列时，依次加入连接板和挂架，中间挂架可左右续接。尚未固定洞洞板时，请平放组装并托住零件。
3. **装入螺母。**将挂架按正常悬挂方向拿正，从左右侧入口分别放入普通 M4 螺母，让螺母平面与槽壁平行，沿缓坡滑向对应孔位。可轻推或稍倾斜辅助，先从板正面用螺丝带住螺母。不要敲击硬装。
4. **固定洞洞板。**从板正面拧入 M4 螺丝。外侧挂架使用内侧孔，拼缝挂架使用双孔；两板边缘相接。确认螺丝确实压紧板，而不是尾端顶到盲孔底。
5. **完成板背支撑与纵向拼接。**沿用相匹配的原 ModelB 连接件，让板背支撑与挂架的家具接触面共面。
6. **处理顶部固定。**顶臂下平面铺设防滑贴／粘胶，尽量薄且各支点等厚，按所用材料要求处理表面及等待固化。
7. **先空载，再逐步放置物品。**在下方有承托的条件下检查支架位移、插接松动、胶层剥离及持续变形，再决定实际使用负载。

顶部防滑固定不能省略。普通无粘性的防滑贴只能增加摩擦，是否足够取决于实际表面、重心和负载；横向连接板不能代替家具端固定。

## 6. 打印配置

本工程按 **P1S＋0.4 mm 喷嘴＋PETG** 配置，十一盘分别命名，所有零件均为独立对象。

| 参数 | 已保存设置 |
|---|---|
| 层高 | 0.20 mm |
| 墙层数 | 6 |
| 填充 | 50%，Gyroid |
| 顶／底层 | 各 6 层 |
| 支撑 | 不启用 |
| 喷嘴／热床 | 255°C／70°C |
| 最大体积速度 | 8 mm³/s |

温度与流量请按实际 PETG 校准。挂架以 **L 形侧面贴床**，连接板大平面贴床；保留工程方向，不要随意竖起打印。适配 280 mm 板宽的连接板实际长 260 mm，已斜放在热床内。

只需打印所选挂架盘与对应连接板盘，不必把十一盘全部打印。先打一套试配，检查孔内桥接下垂、毛刺和插接松紧。

## 7. 常见问题

**不同尺寸需要换螺丝吗？**  
不需要。六种挂架的安装座厚度、螺母位置与避让深度一致，统一按上面的 M4 标准选用。

**“连接板免螺丝”是不是整套免螺丝？**  
不是。横向连接板插接安装，洞洞板仍用 M4 螺丝和螺母固定。

**为什么每只挂架有两个孔，单板安装却只用一个？**  
外侧挂架预留另一孔；多列拼接时，中间挂架的两个孔分别固定相邻两块板。

**能直接用于所有宜家／SKÅDIS 洞洞板吗？**  
不能这样认定。本版依据兼容 MSkadis 板的顶角安装孔设计，请以本文孔位、板厚和背部距离核对实际产品。

**标准版和短版能混在同一排吗？**  
不能。两者下垂高度不同，会使板的安装高度不一致。

**目前验证到了哪一步？**  
已完成十一种零件的闭合实体检查、装配及插入路径检查，以及十一盘实际切片，切片无警告。V3.1 尚未进行实物插接、长期变形和承重验证，没有额定载荷。切片通过不等于承重合格。
'''
(OUT/'01_作品详细说明_可直接复制.md').write_text(body,encoding='utf8')
meta='''# 发布标题与简介

## 推荐标题

洞洞板桌沿／柜侧挂架｜六种统一规格・免螺丝插接连接板

## 简洁标题

洞洞板桌沿／柜侧挂架｜标准版与短版

## 一句话简介

三种顶臂、两种下垂，厚度与M4五金统一；连接板插接安装，十一盘按需选择。

## 作品摘要

用于兼容洞洞板的桌沿／柜侧L形挂架。提供60／90／120 mm顶臂与90／65 mm下垂，共六种规格，统一44 mm宽、14 mm主体臂厚及20.4 mm安装座厚。底部双孔可连接相邻两板，横向连接板无需五金，适配200～280 mm系列板宽。顶部需防滑贴／粘胶；当前已通过切片检查，尚无实物承重验证。

## 建议标签

洞洞板、桌沿挂架、柜侧收纳、L形支架、模块化、拼接、收纳、PETG、MSkadis、M4

'''
(OUT/'02_标题与简介.md').write_text(meta,encoding='utf8')
profile='''# 打印配置说明

## 配置名称

统一规格｜0.20mm・6墙・50%填充｜PETG｜11盘选打

## 可复制的配置简介

P1S／0.4 mm喷嘴／PETG，0.20 mm层高、6墙、50% Gyroid、顶底各6层、不启用支撑。

- 01～03盘：顶臂60／90／120，统一下垂90 mm，每盘挂架一对。
- 04～06盘：顶臂60／90／120，统一下垂65 mm，每盘挂架一对。
- 07～11盘：适配板宽200／220／240／260／280的连接板，各单独一盘一件。

按需打印挂架盘＋对应板宽连接板盘，不必全打。六种挂架统一采用M4×16优先、普通M4六角螺母；12／18 mm的使用条件见作品说明。连接板免螺丝。保留摆放方向，280规格连接板已斜放。顶部需防滑贴／粘胶，先试配再加载。

以下时间与重量来自保存的切片结果，是估算值；当前未做V3.1实物打印验证。

| 盘号 | 内容 | 预计时间 | PETG估重 |
|---|---|---:|---:|
'''
raw=json.loads((SRC/'技术资料'/'实际切片结果.json').read_text(encoding='utf8'))
for i,p in enumerate(raw['sliced_plates'],1):
    mins=round(p['total_predication']/60);grams=sum(f['total_used_g'] for f in p['filaments'])
    label=(f'挂架 顶臂{[60,90,120][(i-1)%3]}／下垂{90 if i<=3 else 65}，一对' if i<=6 else f'连接板 适配板宽{[200,220,240,260,280][i-7]}，一件')
    profile+=f'| {i:02d} | {label} | {mins//60}小时{mins%60:02d}分 | {grams:.1f} g |\n'
(OUT/'03_打印配置发布说明.md').write_text(profile,encoding='utf8')
shutil.copy2(SRC/'图解'/'02_统一规格对照.png',OUT/'配图'/'01_六种统一规格.png')
shutil.copy2(SRC/'图解'/'01_免螺丝插接装配.png',OUT/'配图'/'02_插接装配.png')
shutil.copy2(SRC/'图解'/'03_双侧斜坡螺母装入.png',OUT/'配图'/'03_双侧斜坡螺母装入.png')
editor='''# 发布材料使用说明

本目录为发布草稿，未执行网站上传或发布。

- `01_作品详细说明_可直接复制.md`：公开作品正文。只包含普通Markdown标题、列表、表格、引用与加粗，没有本地图片路径和待填写占位符，可独立复制。
- `02_标题与简介.md`：标题、摘要和标签。
- `03_打印配置发布说明.md`：打印配置名称、简介及十一盘时间重量对照。
- `预览.html`：查看排版效果。仅为本地Markdown预览，不代表已验证MakerWorld编辑器支持原样粘贴Markdown。若平台粘贴后显示源码，可从预览页复制渲染后的内容，或在编辑器内设置标题／表格格式。
- `配图`：当前V3.1模型生成的规格图和装配图。上传到网站后，按下表放到相应段落；不要把本地文件地址粘贴到公开正文。

## 配图顺序与图注

| 顺序 | 文件 | 建议位置 | 可用图注 |
|---|---|---|---|
| 1 | 01_六种统一规格.png | 封面候选或“六种挂架怎么选”之后 | V3.1统一规格：顶臂60／90／120 mm，标准版下垂90 mm，短版下垂65 mm；六种挂架厚度及接口一致。模型示意图，非实拍。 |
| 2 | 02_插接装配.png | “连接板怎么选”之后 | 先插连接板，再固定洞洞板。每端插入约12 mm；连接板免五金，洞洞板仍需M4螺丝。模型示意图，非实拍。 |
| 3 | 03_双侧斜坡螺母装入.png | “双侧入口怎样装螺母”之后 | 左右侧入口分别通向各自孔位，缓坡辅助导向，可轻推或稍倾斜挂架辅助就位。实际模型剖视与局部示意，非实拍。 |

发布使用的模型工程：同级目录“MSkadis挂架_V3.1_双侧斜坡螺母入口_十一盘”内的十一盘工程。三张配图均为模型示意图，上传时按图注标明即可。
'''
(OUT/'00_发布材料使用说明.md').write_text(editor,encoding='utf8')
css='''body{max-width:1040px;margin:36px auto;padding:0 24px 70px;color:#243448;background:#f5f7fa;font:17px/1.85 system-ui,"Microsoft YaHei",sans-serif}header{padding:22px 26px;background:#183c42;color:white;border-radius:16px}header p{margin:4px 0}nav a{display:inline-block;margin:12px 18px 12px 0;color:#126d66}article{background:white;border-radius:14px;padding:30px;margin-top:22px}h1{font-size:30px;line-height:1.4}h2{margin:34px 0 14px;padding-bottom:8px;border-bottom:2px solid #dcebea;font-size:24px}h3{font-size:20px}table{border-collapse:collapse;width:100%;font-size:15px;margin:20px 0}th,td{padding:10px 12px;border:1px solid #dce3e7;text-align:left}th{background:#e9f2f1}blockquote{border-left:4px solid #cd963b;margin:20px 0;padding:1px 18px;background:#fff7e7}code{font-size:15px;background:#f0f3f5;padding:2px 5px;border-radius:4px}img{max-width:100%;border-radius:10px}details{background:white;padding:20px;margin-top:20px;border-radius:12px}summary{cursor:pointer;font-weight:bold}footer{color:#62788b;font-size:14px;margin-top:25px}@media(max-width:650px){body{padding:0 12px;font-size:16px}article{padding:18px}table{display:block;overflow-x:auto}h1{font-size:25px}}'''
render=lambda s:markdown.markdown(s,extensions=['tables','fenced_code','sane_lists'])
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>洞洞板挂架发布材料预览</title><style>'+css+'</style><header><h1>洞洞板挂架发布材料</h1><p>统一规格 · 六种挂架 · 五种独立连接板</p><p>以下是本地草稿，尚未上传发布。</p></header><nav><a href="01_作品详细说明_可直接复制.md">Markdown正文</a><a href="02_标题与简介.md">标题与简介</a><a href="03_打印配置发布说明.md">打印配置说明</a></nav><details><summary>查看规格、插接与螺母安装示意图</summary><img src="配图/01_六种统一规格.png"><img src="配图/02_插接装配.png"><img src="配图/03_双侧斜坡螺母装入.png"></details><article>'+render(body)+'</article><details><summary>标题、摘要与标签</summary>'+render(meta)+'</details><details><summary>打印配置与切片估算</summary>'+render(profile)+'</details><footer>本地Markdown排版预览；未验证目标平台编辑器的粘贴效果。</footer></html>'
(OUT/'预览.html').write_text(page,encoding='utf8')
# Validate the publication text against the actual inventory and measured inputs.
assert len(list((SRC/'单件STL').glob('*.stl')))==11
assert len(raw['sliced_plates'])==11 and raw['return_code']==0
assert all(not p.get('warning_message') for p in raw['sliced_plates'])
for w in [200,220,240,260,280]:assert (SRC/'单件STL'/f'连接板_适配板宽{w}_总长{w-20}.stl').exists()
for a in [60,90,120]:
    for h in [90,65]:
        suffix='标准版' if h==90 else '短版'
        assert (SRC/'单件STL'/f'挂架_顶臂{a}_下垂{h}_{suffix}.stl').exists()
assert not re.search(r'(?:[A-Z]:[/\\]|file://|TODO|待填写)',body)
assert render(body).count('<table>')==7
assert page.count('<h1>')>=2 and '<table>' in page
for p in (OUT/'配图').glob('*.png'):assert p.stat().st_size>1000
(OUT/'素材来源与校验.json').write_text(json.dumps({'version':'V3.1','source_release':str(SRC),'reference_page_read':False,'reference_read_note':'Web inaccessible; browser connection failed. No source text retrieved.','publish_action_performed':False,'markdown_tables':7,'slice_plates':11,'files':[p.name for p in OUT.glob('*.md')]},ensure_ascii=False,indent=2),encoding='utf8')
DEST=Path(r'E:/3dprint/自己设计合集/实用组件')/OUT.name
shutil.copytree(OUT,DEST,dirs_exist_ok=True)
for p in OUT.rglob('*'):
    if p.is_file():assert hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((DEST/p.relative_to(OUT)).read_bytes()).digest()
archive=DEST.parent/(DEST.name+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(DEST.rglob('*')):
        if p.is_file():z.write(p,Path(DEST.name)/p.relative_to(DEST))
print(json.dumps({'directory':str(DEST),'archive':str(archive),'body_chars':len(body),'files':len([p for p in DEST.rglob('*') if p.is_file()])},ensure_ascii=False))
