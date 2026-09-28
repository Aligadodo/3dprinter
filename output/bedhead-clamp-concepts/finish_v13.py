from pathlib import Path
import json,shutil,hashlib,zipfile,csv,math
import markdown
BASE=Path(__file__).parent;ROOT=BASE/'releases/床头夹具_A_V1.3_斜面防滑_多长度螺杆_二十盘'
result=json.loads((BASE/'slice-v13-final/result.json').read_text(encoding='utf8'));assert result['return_code']==0 and len(result['sliced_plates'])==20
verified=json.loads((ROOT/'技术资料/最终文件独立核验.json').read_text(encoding='utf8'));assert verified['all_28_STL_single_solid']
geo=json.loads((ROOT/'技术资料/几何装配验证.json').read_text(encoding='utf8'));manifest=json.loads((ROOT/'技术资料/清单.json').read_text(encoding='utf8'))
rows=[]
for p,m in zip(result['sliced_plates'],manifest):rows.append({'盘号':p['id'],'名称':m['plate'],'耗材克':round(sum(f['total_used_g'] for f in p['filaments']),1),'预计小时':round(p['total_predication']/3600,2),'警告':p.get('warning_message') or ''})
with (ROOT/'技术资料/逐盘耗材时间.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
shutil.copy2(BASE/'slice-v13-final/result.json',ROOT/'技术资料/实际切片结果.json')
table='| 刻字/编号 | 最大工作伸入P | 杆身长 | 旋钮厚 | 总长 |\n|---|---:|---:|---:|---:|\n'
for r in geo['assembly']['extra_screws']:table+=f'| {r["engraved"]} | {r["max_working_projection_mm"]} | {r["shaft_mm"]:.1f} | 10 | {r["total_mm"]:.1f} |\n'
report='''# 床头夹具 A V1.3：斜面齿槽、圆润夹板、五种选配螺杆

2026-09-28。沿用V1.2等宽轻量主体，依据用户参考照片增加固定侧内接触面的1.5°微倾、横向圆底浅槽和自由端圆角。照片只作为形态参考；未取得照片中产品的CAD或性能数据，不将其成熟程度转化为本模型的性能保证。

## 夹板改变了什么

固定侧是没有粗母螺纹孔的一侧，不是取消S接口的M4螺母槽。两种接口、三档夹厚、每种接口的三种宽度，全部18种主体同步更新。

- 内接触面从根部向自由端向夹口内倾1.5°，38.5 mm名义接触长度对应最大内收约1.01 mm。外侧安装孔位与挂钩位置不动。
- 14道横向浅槽，节距2.5、圆底R0.6、名义深0.35 mm。齿顶为较宽接触面，不采用尖锐咬齿。提高摩擦是设计意图，尚未实测摩擦和防滑效果。
- 固定夹板自由端缩短5 mm至Z=−40，并采用R3.3轮廓圆角，主要削除Z<−36.5 mm末端角部材料。挂钩根部、螺丝座和顶梁连接区域保留，左右仍然等宽，侧放打印基准面保持平整。
- 内倾增加少量楔形材料；通过自由端缩短、圆角和齿槽去料抵消，并另存与V1.2的主体体积比较。总打印耗材还受支撑变化影响，按实际切片表判断。

斜面并不保证整面均匀贴合硬板，也不是自锁机构。柔性薄保护垫可以缓和局部接触；硬齿面直接夹漆面仍可能留下压痕。前面及顶面保护垫继续按1 mm设计，实际厚度要计入夹口。

## 主体与原有五金

夹厚20～40、35～55、50～70 mm三档保留。S全体等宽36／40／44；H4等宽48／50／54。前臂和顶梁9.4，后部母螺纹座9.4，S前座总厚13.6 mm。H4孔位40×40，S孔距25、孔径4.4；H4钩尖高于薄顶梁约4.6 mm。

S仍用普通M4六角螺母和M4×12平底头螺丝，按5 mm有效板厚、无垫片计算。尾端余量2 mm。左右15°侧入螺母槽保留，不采用旧T入口。不得沿用M4×16／18／25；旧20.4 mm板背支撑块也不能直接与13.6 mm座混配。

保留原共用粗螺杆：杆身35、手轮10、总长45 mm。之前配合良好的这根螺杆仍可用于新版，各成套盘继续配它，选配长短杆另放第20盘。

## 五种粗螺杆如何命名

用户确认的10～50 mm指**伸入夹口的工作长度**，不是可夹板厚，也不是杆身总长。P从后夹臂内侧平面量到螺杆端面；达到标称P时，手轮与后夹臂还保留2 mm间隙，9.4 mm母螺纹座全长处于啮合范围。

`杆身长L = P + 9.4（后夹臂厚）+ 2（手轮间隙）`

`总长 = L + 10（旋钮）`

'''+table+'''
单位mm。对象名、STL名同时包含P、杆身长及总长；旋钮底面刻P10／P20／P30／P40／P50，刻槽宽约0.56、深0.55，打印后可涂色识别。

这些是最大工作伸入值，不是物理止挡。继续拧入会减少预留手轮间隙；禁止用手轮顶住夹体强拧。较长杆在小夹口中未必能达到其标称P，可能先碰到固定夹板或板材。长杆不能让夹具跨过更厚的家具板，也不能据此提高承重。

新五种杆按原模型正X截面采样重建连续4 mm螺距，径向额外留0.04 mm配合余量，保留5 mm中心孔并做端部导入；旋钮轮廓继续复用原件。没有沿轴向缩放，也未简单拼接错相螺纹。原35 mm杆仍保持其原牙型网格。

## 怎样选长度

保守按最大内收1.01和1 mm前垫计算，有效开口约：40档40.99、55档55.99、70档70.99 mm。某板厚T需要的伸入量约为“有效开口−T”；选择P不小于该值的杆。实际齿面圆角与软垫压缩会影响接触位置，最后以手拧试配为准。

| 螺杆 | 在20–40档内可覆盖的板厚（保守） | 35–55档 | 50–70档 |
|---|---|---|---|
| P10 | 约30.99～40 | 约45.99～55 | 约60.99～70 |
| P20 | 约20.99～40 | 约35.99～55 | 约50.99～70 |
| P30 | 原20～40全范围 | 原35～55全范围 | 原50～70全范围 |
| P40 / P50 | 原范围可覆盖，但占用更多后方空间 | 同左 | 同左 |
| 原35 mm杆身 | 原20～40全范围 | 原35～55全范围 | 原50～70全范围 |

以上只列原三档设计范围内的覆盖，未将更薄板的几何可达性宣称为新增验证范围。通常选择能顶到目标板的较短杆；P40/P50主要作为可选长度留给更大的伸入需求，长悬伸刚度需要额外实测。短杆在某一档薄端顶不到时，换长杆，不要只啮合少量螺纹硬夹。

## 分盘与打印

- 主工程：床头夹具_A_V1.3_二十盘_P1S_PETG.3mf。
- 第01盘：H4、M4侧槽、母螺纹、斜面齿槽4种试配件，加原35 mm杆身螺杆，共5件。
- 第02～10盘：9种H4主体，每盘2主体＋2根原35 mm杆身螺杆。
- 第11～19盘：9种S主体，同样每盘2＋2。
- **第20盘：P10～P50各一根，共5根**，每个都是独立命名对象，可只保留需要的长度打印。另提供这一盘单独3MF。

共28种单件STL，主工程82个对象。先打第01盘；选配杆首次使用时建议P10或P20与母螺口先试配。

P1S／0.4喷嘴／PETG／0.20层高；主体4墙、30% Gyroid，全部粗螺杆100%填充。主体平侧面贴床，螺杆旋钮底面朝下。保留普通自动支撑，允许模型上起支撑；内孔、挂钩和导槽仍可能需要清理。255/70°C及8 mm³/s沿用既有配置起点，按线材校准。

刻字槽起始层的桥接清晰度、长螺杆垂直度和支撑清理需实物确认。先空载手拧，再逐步放轻物；没有新增防退锁或防上抬扣，当前没有新版承重及长期夹紧结果。

## 验证和来源

全部18种主体STL和3MF回读、等宽平面、1.5°斜面与槽深、末端圆角；28种STL闭合单实体；五种新螺杆各101个理论相位及导出网格各41个相位，检查与原配母螺纹的干涉；M4×12路径保持。20盘实际切片结果见下表。几何与切片通过不代表实际摩擦、强度或长杆抗弯已验证。

原粗螺纹和旋钮来自用户收藏“桌边洞洞板夹具.3mf”，原包作者字段Ms，许可原文Standard Digital File License，来源记录保留。用户新照片作为形态参考，不包含在打印交付里。

V1.2及更旧文件未覆盖；打开V1.3主工程或第20盘单独工程才能看到新增结构与长度。

'''
report+='| 盘 | 名称 | 克 | 小时 | 警告 |\n|---|---|---:|---:|---|\n'
for r in rows:report+='| '+' | '.join(str(r[k]) or '无' for k in r)+' |\n'
(ROOT/'README_选型打印与安装.md').write_text(report,encoding='utf8')
page='<!doctype html><meta charset="utf-8"><title>床头夹具V1.3</title><style>body{font:17px/1.8 system-ui;max-width:1250px;margin:30px auto;padding:20px;color:#20374c}img{width:100%}td,th{padding:8px;border-bottom:1px solid #ccd}table{border-collapse:collapse}</style><p><a href="床头夹具_A_V1.3_二十盘_P1S_PETG.3mf">新版二十盘工程</a> · <a href="单盘工程/第20盘_粗螺杆选配_P10至P50_五种长度.3mf">单独螺杆盘</a></p><img src="图解/01_斜面齿槽与圆角.png"><img src="图解/02_五种螺杆尺寸.png">'+markdown.markdown(report,extensions=['tables'])
(ROOT/'打开这里_斜面与螺杆选型.html').write_text(page,encoding='utf8')
for name in ['prepare_v13.py','build_v13.py','sampled_screw_v13.py','prepare_verify_v13.py','verify_v13.py','draw_v13.py','finish_v13.py']:shutil.copy2(BASE/name,ROOT/'技术资料'/name)
old=BASE/'releases/床头夹具_A_V1.2_等宽轻量_M4x12_十九盘/来源'
for name in ['来源记录.json','原模型元数据与组件关系.xml']:shutil.copy2(old/name,ROOT/'来源'/name)
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(ROOT/'技术资料/SHA256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2),encoding='utf8')
dest=Path('E:/3dprint/自己设计合集/实用组件')/ROOT.name;shutil.copytree(ROOT,dest,dirs_exist_ok=True)
for rel,digest in hashes.items():assert hashlib.sha256((dest/rel).read_bytes()).hexdigest()==digest
archive=shutil.make_archive(str(dest),'zip',root_dir=dest.parent,base_dir=dest.name)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
(dest.parent/'床头夹具_最新版说明.md').write_text('# 当前版本：V1.3 斜面防滑与多长度螺杆\n\n新版目录：'+dest.name+'\n\n主工程：床头夹具_A_V1.3_二十盘_P1S_PETG.3mf\n\n第20盘为P10～P50五种粗螺杆。S接口仍仅M4×12、板厚5 mm。旧版未覆盖。\n',encoding='utf8')
print(json.dumps({'plates':20,'unique_STL':28,'warnings':[r for r in rows if r['警告']],'extra_screw_plate':rows[-1]},ensure_ascii=False))
