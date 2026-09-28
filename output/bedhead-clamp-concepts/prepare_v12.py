from pathlib import Path
p=Path(__file__).parent
s=(p/'build_v11.py').read_text(encoding='utf8')
s=s.replace('床头夹具_A_V1.1_左右斜坡螺母入口_十九盘','床头夹具_A_V1.2_等宽轻量_M4x12_十九盘').replace('床头夹具_A_V1.1_十九盘_P1S_PETG','床头夹具_A_V1.2_十九盘_P1S_PETG').replace('床头夹具 A V1.1 左右斜坡螺母入口','床头夹具 A V1.2 等宽轻量 M4x12')
s=s.replace('WIDTHS=[36,44,60]','WIDTHS={"挂钩H4":[48,50,54],"螺丝S":[36,40,44]}')
s=s.replace('rear=10.65;axis=13.65','rear=9.4;axis=13.65').replace('.translate((axis,0,-30))','.translate((axis,0,-19.35-rear))')
s=s.replace('HOOKS=make_hooks()','HOOKS=make_hooks().translate((4.6,0,0))')
s=s.replace('s=s-bore(-20.5,16.1,y,-1,4.4)','s=s-bore(-13.7,9.1,y,-1,4.4)')
s=s.replace('yz(channel,-17.6,4.0)','yz(channel,-11.2,4.0)').replace('(fw/2-2,-17.6,-13.6,3.8),(fw/2+.5,-18,-13.2,4.5)','(fw/2-2,-11.2,-7.2,3.8),(fw/2+.5,-11.6,-6.8,4.5)')
s=s.replace('for w in WIDTHS:','for w in WIDTHS[kind]:')
s=s.replace('sb(-14,-15,G+rear,-1),sb(-14,-15,0,45),sb(G,-15,G+rear,45)','sb(-9.4,-10.4,G+rear,-1),sb(-9.4,-10.4,0,45),sb(G,-10.4,G+rear,45)')
s=s.replace('fw=max(54,w)','fw=w').replace('front=xz(sb(-14,-15,0,45).buffer(-1,join_style=1).buffer(1,join_style=1),fw)','front=frame').replace('s=frame+front+HOOKS','s=frame+HOOKS')
s=s.replace('fw=max(44,w)','fw=w').replace('sb(-20.4,-15,0,17)','sb(-13.6,-10.4,0,17)')
s=s.replace("'front_arm_mm':14,'front_seat_mm':14 if kind=='挂钩H4' else 20.4,'min_knob_gap_mm':2.35,'max_knob_gap_mm':22.35","'front_arm_mm':9.4,'top_beam_mm':9.4,'rear_arm_mm':9.4,'front_seat_mm':9.4 if kind=='挂钩H4' else 13.6,'min_knob_gap_mm':3.6,'max_knob_gap_mm':23.6")
s=s.replace('def pegboard(back=-14.3,zc=10):','def pegboard(back=-9.7,zc=10):').replace('床头夹具_挂钩H4_夹20-40_宽44','床头夹具_挂钩H4_夹20-40_宽48').replace('np.linspace(-28,-14.3,36)','np.linspace(-23.4,-9.7,36)').replace('pegboard(-14.3,zz)','pegboard(-9.7,zz)').replace('pegboard(-16.5,2.8)','pegboard(-11.9,2.8)')
s=s.replace('nut=yz(nut_outline(7),-17.2,3.2)','nut=yz(nut_outline(7),-10.8,3.2)').replace('cube((-17.3,-3,-16),(-14.1,3,-6))','cube((-10.8,-3,-16),(-7.6,3,-6))').replace('for length in [12,16,18]:','for length in [12]:').replace('bore(-25.4,length,yy,-1,4)','bore(-18.6,length,yy,-1,4)')
s=s.replace("'front_skin_min_channel_mm':2.8,'front_skin_min_mouth_mm':2.4","'front_skin_min_channel_mm':2.4,'front_skin_min_mouth_mm':2.0").replace("'bolts_mm':[12,16,18],'board_mm':5","'bolts_mm':[12],'board_mm':5,'blind_depth_mm':9,'tail_clearance_mm':2,'nominal_nut_depth_range_mm':[2.8,6.0],'minimum_full_nut_exit_mm':0.6")
s=s.replace("save(HCOUPON,cube((-14,-27,-44),(-10,27,15))+HOOKS,FRAME_ROT)","save(HCOUPON,cube((-9.4,-24,-44),(-5.4,24,10.4))+HOOKS,FRAME_ROT)")
s=s.replace('m4_cuts(cube((-20.4,-22,-17),(0,22,15)))','m4_cuts(cube((-13.6,-18,-17),(0,18,10.4)),36)')
s=s.replace('床头A_V1.1_PETG_020_6墙_50填充_自动支撑','床头A_V1.2_PETG_020_4墙_30填充_自动支撑').replace("'support_threshold_angle':'30'","'support_threshold_angle':'30','wall_loops':'4','sparse_infill_density':'30%'")
# Record reversible print transform and the volume comparison for all size variants.
s=s.replace("if rotation is not None:m.apply_transform(rotation)","assembly_bounds=m.bounds.copy()\n if rotation is not None:m.apply_transform(rotation)\n print_min=m.bounds[0].copy()")
s=s.replace("'watertight_single_solid':True}","'watertight_single_solid':True,'assembly_bounds':assembly_bounds.tolist(),'print_translation':(-print_min).tolist(),'assembly_to_print_rotation':(np.eye(4) if rotation is None else rotation).tolist()}")
s=s.replace('back=trimesh.load(dest);assert', 'back=trimesh.load(dest)\n back.update_faces(back.nondegenerate_faces());back.update_faces(back.unique_faces());back.remove_unreferenced_vertices()\n back.export(dest);back=trimesh.load(dest)\n assert')
anchor="# Full-range helical sweep"
idx=s.index(anchor)
s=s[:idx]+'''# Equal-width body contact at the first printable layer; no widened floating head.
comparisons=[]
previous=BASE/'releases'/'床头夹具_A_V1.1_左右斜坡螺母入口_十九盘'/'单件STL'
for kind,w,lo,hi,name in names:
 oldw=[36,44,60][WIDTHS[kind].index(w)]
 old=trimesh.load(previous/f'床头夹具_{kind}_夹{lo}-{hi}_宽{oldw}.stl')
 current=PARTS[name]
 sec=current.section([0,0,1],[0,0,.2]);assert sec is not None
 # x=10 lies inside the top beam, well away from front head and thread sleeve.
 cross=ALL_ASSEMBLY[name]^cube((10,-w/2,2),(11,w/2,9))
 assert abs(cross.volume()-w*7)<1e-4,(name,'non-uniform bridge width')
 comparisons.append({'new':name,'old_width':oldw,'new_width':w,'old_volume_mm3':float(old.volume),'new_volume_mm3':float(current.volume),'solid_volume_reduction_percent':round(100*(1-current.volume/old.volume),1),'equal_width_bridge_pass':True})
CHECKS['comparison']=comparisons

''' + s[idx:]
(p/'build_v12.py').write_text(s,encoding='utf8')
print(p/'build_v12.py')
