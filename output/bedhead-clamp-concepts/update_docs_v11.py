from pathlib import Path
p=Path(__file__).parent
old='床头夹具_A_V1_双接口_三档三宽_十九盘';new='床头夹具_A_V1.1_左右斜坡螺母入口_十九盘'
s=(p/'draw_v1.py').read_text(encoding='utf8').replace(old,new).replace('A V1｜','A V1.1｜').replace('普通M4螺母从下方装入，再滑向孔位','左右侧分别装入M4螺母，沿15°坡轻推定位')
(p/'draw_v11.py').write_text(s,encoding='utf8')
s=(p/'finish_v1.py').read_text(encoding='utf8').replace(old,new).replace('slice-v1','slice-v11').replace('A V1','A V1.1').replace('A_V1_十九盘','A_V1.1_十九盘').replace('finish_v1.py','finish_v11.py').replace('draw_v1.py','draw_v11.py').replace('build_v1.py','build_v11.py')
s=s.replace('使用普通M4六角螺母（对边7、厚约3.2 mm），从座下缘中央开口进入，再左右滑到相应孔位。螺母腔轴向厚3.6 mm；不适配厚防松螺母或法兰螺母。','使用普通M4六角螺母（对边7、厚约3.2 mm）。左右侧各有一个独立入口，分别通向对应螺丝孔，原底部中央T槽已封闭。先将螺母平贴槽内、上下两边保持水平，从侧面沿15°向内下倾的导槽轻推到内端，再对齐孔位拧入螺丝。建议先装好两颗螺母再把夹具套到床头板上。\n\n导槽轴向厚4.0 mm，对边包络7.6 mm；入口扩口厚约4.8 mm、高约9.0 mm，约2 mm长的导入段。相比3.2 mm厚的标准螺母，两侧各留0.4 mm轴向余量。内端封闭用于限制越位，两条槽不相通。不适配厚防松螺母或法兰螺母。15°是装配方向的浅坡，不代表打印时所有内壁都可无支撑；沿用原侧放方向和自动支撑。\n\n浅坡用于导向，能否靠自重滑动取决于打印粗糙度和摩擦，必要时轻推；清除支撑后先试配，不能保证螺母自动滑到底。未上螺丝前侧口仍可退出螺母，装配时避免反向倾斜。')
s=s.replace('M4螺母插入/横向滑动','全部9种螺丝款的M4左右斜坡插入路径（每侧81个位置）、旧T槽封闭和内端止挡')
s=s.replace('<img src="图解/02_圆角挂钩与安装.png">','<img src="图解/02_圆角挂钩与安装.png"><img src="图解/03_左右斜坡螺母入口.png">')
s=s.replace("for n in ['finish_v11.py','draw_v11.py','thread_fit.py']", "for n in ['finish_v11.py','draw_v11.py','draw_side_entry_v11.py','verify_v11.py','prepare_v11.py','update_docs_v11.py','thread_fit.py']")
(p/'finish_v11.py').write_text(s,encoding='utf8')
