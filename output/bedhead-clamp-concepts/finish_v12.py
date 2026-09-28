from pathlib import Path
import json,shutil,hashlib,zipfile,csv,html
BASE=Path(__file__).parent;ROOT=BASE/'releases/床头夹具_A_V1.2_等宽轻量_M4x12_十九盘'
result=json.loads((BASE/'slice-v12/result.json').read_text(encoding='utf8'));assert result['return_code']==0 and len(result['sliced_plates'])==19
manifest=json.loads((ROOT/'技术资料/清单.json').read_text(encoding='utf8'));geo=json.loads((ROOT/'技术资料/几何装配验证.json').read_text(encoding='utf8'))
old=json.loads((BASE/'slice-v11/result.json').read_text(encoding='utf8'))
rows=[]
for p,m,o in zip(result['sliced_plates'],manifest,old['sliced_plates']):
 grams=sum(f['total_used_g'] for f in p['filaments']);oldgrams=sum(f['total_used_g'] for f in o['filaments'])
 rows.append({'盘号':p['id'],'名称':m['plate'],'新耗材克':round(grams,1),'旧对应档耗材克':round(oldgrams,1),'耗材减少百分比':round((1-grams/oldgrams)*100,1),'预计小时':round(p['total_predication']/3600,2),'警告':p.get('warning_message') or ''})
with (ROOT/'技术资料/逐盘新旧对比.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
shutil.copy2(BASE/'slice-v12/result.json',ROOT/'技术资料/实际切片结果.json')
report='''# 床头夹具 A V1.2：等宽轻量版，M4×12

2026-09-28。根据用户实物照片与反馈改版：照片可见明显悬空线条及表面缺陷，但单张照片不能确认所有缺陷的原因。V1.1存在主体较窄、前头加宽的台阶；侧放时较窄主体不贴热床，需要额外支撑。V1.2取消这个宽度台阶，减少截面厚度和多余边缘。

## 具体变化

| 项目 | V1.1 | V1.2 |
|---|---|---|
| 前臂、顶梁厚度 | 14 | 9.4，减少约33% |
| S局部前座总厚 | 20.4 | 13.6，减少约33% |
| 后部母螺纹座厚 | 10.65 | 9.4，保留较充分的粗螺纹啮合 |
| S款宽度 | 主体36/44/60，前头至少44 | 全体等宽36/40/44 |
| H4款宽度 | 主体36/44/60，前头至少54 | 全体等宽48/50/54 |
| 夹持范围 | 20–40 / 35–55 / 50–70 | 保持 |
| M4螺丝 | 优先16，可用12/18 | 仅按12设计 |
| 主体打印设置 | 6墙、50%填充 | 4墙、30% Gyroid |

单位mm。“夹20–40”指可夹家具板厚；“宽36”指沿家具左右方向的宽度。每一种新夹具的前臂、顶梁和后臂都使用同一宽度，S前座沿前后方向仍有必要的局部厚度。

H4最窄版从旧主体36变为48，是为了容纳保持不变的40 mm挂钩列距并消除加宽头；其接口头从54收窄到48。不能把H4也缩为36而保持四钩孔距。钩外侧至48 mm主体边缘约1.8 mm，仍需实物核对根部及层间状态。宽度选择不代表已验证承重等级。

## 接口与安装位置

S孔径4.4，左右中心Y=±12.5、Z=−1，25 mm孔距保持。H4列距和排距40，挂钩宽4.4、喉口5.8、钩尖R2.2及侧轮廓R0.55保留。以家具顶面Z=0为基准，接口竖向位置不变。前臂／前座变薄后，板背在前后方向更靠近家具，这是减薄带来的尺寸变化，不是整体缩放模型。

顶梁从原Z=1～15减为Z=1～10.4；挂钩钩尖仍到Z=15，因此现在比顶梁高约4.6 mm。这样保留挂孔竖向位置，不把挂口向下移。原有20.4 mm柜侧／ModelB背部支撑厚度不再与S款13.6 mm座自动共面，配套下支撑需按新版实际板背距离调整。

前保护垫及顶保护垫各按1 mm计算，最大板厚时留2 mm夹紧余量。粗螺杆仍是杆35＋手轮10＝45，保留原牙型，全部档位通用。旧粗螺杆如果牙型和实际配合良好可继续使用；照片中螺杆是否合格不能仅凭外观确定。后部占位仍约45 mm，另需手指空间。

## M4×12与左右螺母入口

适用于有效安装板厚5 mm、普通M4螺母（对边7、厚3.2）、平底头M4×12、不加垫片。板厚、沉头或垫片改变后重新核对，不直接套用。

座厚13.6；盲孔深9，家具侧隔墙4.6。M4×12穿过5 mm板后进入7 mm，尾端净余量2 mm。螺母名义占据前座表面后2.8～6.0 mm；在4.0 mm槽内最不利偏移后远面可到6.4 mm，12 mm螺丝仍有0.6 mm穿出余量。先用第01盘小样确认五金实际厚度和打印毛刺。

左右独立15°浅坡入口保留；导槽对边包络7.6、厚4.0，扩口名义约4.8×9。螺母沿侧口轻推至孔位，拧入正面螺丝。无中央下进T槽；前皮槽内2.4、入口最薄设计值约2.0。未拧上螺丝前，螺母可从侧口退出。坡度用于导向，不承诺凭自重滑到底。

不要继续使用旧版推荐的M4×16／18／25：本版会顶到盲孔底。不要靠强拧把螺丝顶穿后壁。每只S座有两个孔，实际螺母数量按所用孔位配齐。

## 打印与试装

主工程为“床头夹具_A_V1.2_十九盘_P1S_PETG.3mf”。第01盘含四钩、M4侧槽、母螺口小样和共用粗螺杆；第02～10盘H4，第11～19盘S，每盘两主体加两螺杆。共18种主体、22种单件。小样不额外装到正式夹具上。

使用工程内方向：主体平侧面贴床，避免再次把前头作为支点让主体悬空。等宽解决主体大面积悬空，挂钩及内部孔槽仍有局部桥接／支撑需要；普通自动支撑保持启用，允许模型上起支撑。不要将“等宽”理解为可关闭全部支撑。先检查切片首层主体接地，以及母螺口和槽内支撑是否能清理。

P1S、0.4喷嘴、PETG、0.20层高、主体4墙／30% Gyroid、粗螺杆100%。温度255/70°C、最大体积速度8 mm³/s为原配置起点，按线材校准。本次减薄、减宽且降低主体填充；刚度会下降，不能只按少了三分之一厚度推算剩余强度。

先打印小样检查螺母与粗螺纹，再打一档空载试装。清理支撑、毛刺后手拧，不使用长杠杆。本版按轻负载收纳方向调整，但没有额定负载，也没有新版实物承重或长期夹紧结果。

## 验证与比较说明

所有18种主体STL和3MF回读检查；前臂／顶梁／后臂全宽相同；S款左右路径各81个采样，M4×12避让与M4×16不可用；粗螺纹有效行程81个相位；四钩套入下落73个位置。19盘使用实际交付工程切片，结果见下表。

新旧耗材按宽度档序号对应：S旧36/44/60→新36/40/44；H4旧36/44/60→新48/50/54，因此不是所有行都同宽比较。切片耗材包含支撑及本盘螺杆，且填充设置已变；几何体积减少另见“几何装配验证.json”的comparison，不应混为仅壁厚变化的效果。

## 来源与版本

粗螺杆及母螺纹复用用户收藏“桌边洞洞板夹具.3mf”，原作者字段Ms，许可原文Standard Digital File License，保留来源记录。V1.1文件未覆盖；请按本版文件名打开，不要继续使用V1或V1.1主工程打印新版。

'''
report+='| 盘 | 配置 | 新克数 | 旧对应档克数 | 减少% | 小时 | 警告 |\n|---|---|---:|---:|---:|---:|---|\n'
for r in rows:report+='| '+' | '.join(str(r[k]) or '无' for k in r)+' |\n'
(ROOT/'README_选型打印与安装.md').write_text(report,encoding='utf8')
import markdown
content=markdown.markdown(report,extensions=['tables'])
(ROOT/'打开这里_等宽轻量版说明.html').write_text('<!doctype html><meta charset="utf-8"><title>床头夹具 V1.2</title><style>body{font:17px/1.8 system-ui;max-width:1200px;margin:30px auto;padding:20px;color:#20374c}img{width:100%}td,th{padding:8px;border-bottom:1px solid #ccd}table{border-collapse:collapse}</style><p><a href="床头夹具_A_V1.2_十九盘_P1S_PETG.3mf">打开新版十九盘工程</a></p><img src="图解/01_等宽轻量新旧对比.png"><img src="图解/02_双接口与安装注意.png">'+content,encoding='utf8')
for n in ['prepare_v12.py','build_v12.py','verify_v12.py','draw_v12.py','finish_v12.py']:shutil.copy2(BASE/n,ROOT/'技术资料'/n)
oldsource=BASE/'releases/床头夹具_A_V1.1_左右斜坡螺母入口_十九盘/来源'
for n in ['来源记录.json','原模型元数据与组件关系.xml']:shutil.copy2(oldsource/n,ROOT/'来源'/n)
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(ROOT/'技术资料/SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
dest=Path('E:/3dprint/自己设计合集/实用组件')/ROOT.name;shutil.copytree(ROOT,dest,dirs_exist_ok=True)
for rel,digest in hashes.items():assert hashlib.sha256((dest/rel).read_bytes()).hexdigest()==digest
archive=shutil.make_archive(str(dest),'zip',root_dir=dest.parent,base_dir=dest.name)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
(dest.parent/'床头夹具_最新版说明.md').write_text('# 当前版本：V1.2 等宽轻量版\n\n新版目录：'+dest.name+'\n\n主工程：床头夹具_A_V1.2_十九盘_P1S_PETG.3mf\n\nS款仅按M4×12、有效板厚5 mm设计；V1/V1.1为历史版。\n',encoding='utf8')
print(json.dumps({'plates':19,'warnings':[r for r in rows if r['警告']],'solid_reduction_range':[min(r['solid_volume_reduction_percent'] for r in geo['assembly']['comparison']),max(r['solid_volume_reduction_percent'] for r in geo['assembly']['comparison'])],'filament_reduction_range':[min(r['耗材减少百分比'] for r in rows[1:]),max(r['耗材减少百分比'] for r in rows[1:])]},ensure_ascii=False))
