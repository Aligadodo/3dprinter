from pathlib import Path
import json,shutil,hashlib
from extract_3mf_component import extract

WORK=Path(__file__).resolve().parents[1];OUT=WORK/'docs/skadis-design-sop';SRC=Path('E:/3dprint/模型收藏合集/宜家洞洞板系列收藏')
BASE=WORK/'output/bedhead-clamp-concepts';REL=BASE/'releases/床头夹具_A_V1.1_左右斜坡螺母入口_十九盘'
for folder in ['components','evidence','scripts','implementation-reference']:(OUT/folder).mkdir(parents=True,exist_ok=True)
checks=json.loads((REL/'技术资料/几何装配验证.json').read_text(encoding='utf8'))
params={'schema_version':1,'date':'2026-09-27','units':'mm unless explicitly marked','status_legend':{'reference_mesh_measurement':'从指定参考网格测量；非官方标准和实物测量','geometry_and_slice_checked':'几何及切片通过；未实物验证','project_default':'本项目设计默认值；不是通用强度规则'},'profiles':{
 'reference_board_from_desk_clamp':{'status':'reference_mesh_measurement','source':'桌边洞洞板夹具.3mf / 3D/Objects/object_4.model / object 6','board_thickness':5,'slot_width':5.2,'slot_height':15.2,'same_row_pitch':40,'same_column_pitch':40,'limitations':'中间排错位；真实板、涂层需复测'},
 'H4_bedhead_A_v11':{'status':'geometry_and_slice_checked','source':'evidence/bedhead_geometry.json / assembly.hooks','values':checks['assembly']['hooks'],'limitations':'未验证真实板及承重；无防上抬扣'},
 'S_M4_bedhead_A_v11':{'status':'geometry_and_slice_checked','source':'evidence/bedhead_geometry.json / assembly.m4','values':{k:v for k,v in checks['assembly']['m4'].items() if k!='all_variants'},'seat_total_thickness':20.4,'blind_depth_from_front':16,'furniture_side_wall':4.4,'nut_near_far_from_front':[3.2,6.4],'preferred_bolt_length':16,'unsupported_bolt_length':25,'limitations':'用于ModelB角孔体系；不适配厚防松或法兰螺母；无重力自滑保证'},
 'S_M4_cabinet_v31':{'status':'geometry_and_slice_checked','source':'evidence/cabinet_V3.1_README.md','hole_diameter':4.4,'hole_pitch':25,'corner_edge_offset':12.5,'seat_total_thickness':20.4,'channel_thickness':4.0,'channel_AF':7.5,'slope_degrees_approx':17.5,'drop_approx':3,'limitations':'与床头15度/7.6配置分开维护；未实物验证'},
 'bedhead_body_A_v11':{'status':'project_default','source':'implementation-reference/build_v11.py','clamp_ranges':[[20,40],[35,55],[50,70]],'body_widths':[36,44,60],'front_arm_thickness':14,'head_min_width_H4':54,'head_min_width_S':44,'rear_arm_thickness':10.65,'front_pad_thickness':1,'top_pad_thickness':1,'rear_inner_x_formula':'range_max + 3','effective_openings':[42,57,72],'max_board_adjustment_reserve':2,'min_knob_rear_arm_gap_approx':2.35,'limitations':'宽度不代表额定载荷；前后墙缝须单独核对'},
 'reused_coarse_thread':{'status':'geometry_and_slice_checked','source':'桌边洞洞板夹具.3mf / object_16.model + object_17.model','pitch_approx':4,'major_diameter_approx':15.38,'original_shaft':40,'original_knob':15,'current_shaft':35,'current_knob':10,'current_total':45,'limitations':'非标准M16；保存原牙型和配对母螺纹，不整体缩放'},
 'cabinet_crossbar_v31':{'status':'geometry_and_slice_checked','source':'evidence/cabinet_V3.1_README.md','board_widths':[200,220,240,260,280],'actual_lengths':[180,200,220,240,260],'body_thickness':6,'tongue_thickness':4,'insertion_each_end_approx':12,'clearance_each_side':.2,'limitations':'柜侧系列专用，不是床头夹具的默认横梁'},
 'print_bedhead_v11':{'status':'project_default','source':'evidence/P1S_PETG.json','printer':'P1S','nozzle':.4,'material':'PETG','layer_height':.2,'walls':6,'body_infill_percent':50,'infill_pattern':'gyroid','screw_infill_percent':100,'nozzle_celsius':255,'bed_celsius':70,'max_volumetric_mm3_s':8,'support':'normal(auto); model support allowed','orientation':'body on side; screw knob bottom down','limitations':'柜侧V3.1不启用支撑；温度流量按线材校准'}}}
(OUT/'parameters.json').write_text(json.dumps(params,ensure_ascii=False,indent=2),encoding='utf8')
catalog=json.loads((OUT/'reference-index/catalog.json').read_text(encoding='utf8'))
records=[]
selections=[('桌边洞洞板夹具.3mf','4564564566','source-coarse-screw'),('桌边洞洞板夹具.3mf','jiazi','source-clamp-with-female-thread'),('桌边洞洞板夹具.3mf','洞洞板','source-board'),('ModelB.3mf','B2','source-modelb-b2'),('ModelB.3mf','B4','source-modelb-b4'),('20mm-1.3mf','20mm-1.stl','source-small-hook'),('komplett.3mf','krok.stl','source-tool-hook')]
for rel,name,key in selections:
 f=next(f for f in catalog['files'] if f['relative_path']==rel);o=next(o for o in f['objects'] if o['name']==name)
 r=extract(SRC/rel,o['member'],o['object_id'],OUT/'components'/f'{key}.stl');r.update({'id':key,'file':f'{key}.stl','designer':f['metadata'].get('Designer',''),'license_verbatim':f['metadata'].get('License',''),'status':'extracted source-local mesh; not a new print-ready assembly','reuse':'source-clamp-with-female-thread requires selecting/fusing the sleeve; do not embed entire clamp' if key=='source-clamp-with-female-thread' else 'verify intended mating interface before reuse'})
 records.append(r)
for name in ['共用粗螺杆_杆35_旋钮10_总长45','试配件_H4四钩_孔距40_板厚5','试配件_M4左右斜坡入口_孔距25','试配件_原牙型母螺口']:
 p=REL/'单件STL'/(name+'.stl');dest=OUT/'components'/p.name;shutil.copy2(p,dest)
 records.append({'id':name,'file':p.name,'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'status':'geometry and slicing checked; physical fit pending','coordinate_space':'normalized print coordinates, not assembly coordinates','provenance':'bedhead A V1.1; coarse screw/female thread reuse Ms source, H4 and M4 coupon geometry built in project'})
(OUT/'components/manifest.json').write_text(json.dumps({'component_count':len(records),'records':records,'warning':'Source meshes are reference assets; print-ready coupons are labeled separately. Source license metadata is retained, not replaced.'},ensure_ascii=False,indent=2),encoding='utf8')
copies={'技术资料/几何装配验证.json':'bedhead_geometry.json','技术资料/最终文件独立核验.json':'bedhead_export_verification.json','技术资料/实际切片结果.json':'bedhead_slice_result.json','技术资料/P1S_PETG参数.json':'P1S_PETG.json','README_选型打印与安装.md':'bedhead_V1.1_README.md'}
for src,dst in copies.items():shutil.copy2(REL/src,OUT/'evidence'/dst)
shutil.copy2(WORK/'output/skadis-corner-support/releases/MSkadis挂架_V3.1_双侧斜坡螺母入口_十一盘/README_安装说明.md',OUT/'evidence/cabinet_V3.1_README.md')
for name in ['build_v11.py','verify_v11.py','thread_fit.py']:shutil.copy2(BASE/name,OUT/'implementation-reference'/name)
for name in ['index_skadis_library.py','extract_3mf_component.py','build_skadis_knowledge.py','package_skadis_sop.py']:
 if (WORK/'scripts'/name).exists():shutil.copy2(WORK/'scripts'/name,OUT/'scripts'/name)
(OUT/'implementation-reference/README.md').write_text('这里保存已验证实现的源码快照用于查阅与迁移，不是独立一键构建包。build_v11.py依赖原工作区的revision-a源网格、skadis-corner-support序列化函数和打印配置，执行前阅读源代码并设置输出目录；不要直接导入，会触发整套导出。新设计应提取所需函数和参数。components内小样为打印坐标，不能直接按装配坐标布尔融合。\n',encoding='utf8')
print('Parameters and',len(records),'components created.')
