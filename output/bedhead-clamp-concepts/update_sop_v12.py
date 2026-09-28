from pathlib import Path
import json,shutil,hashlib
BASE=Path(__file__).parent;ROOT=BASE/'releases/床头夹具_A_V1.2_等宽轻量_M4x12_十九盘';SOP=Path('docs/skadis-design-sop')
geo=json.loads((ROOT/'技术资料/几何装配验证.json').read_text(encoding='utf8'))
params=json.loads((SOP/'parameters.json').read_text(encoding='utf8'));params['date']='2026-09-28'
params['preferred_profiles']={'bedhead_body':'bedhead_body_A_v12','bedhead_S_interface':'S_M4_bedhead_A_v12','bedhead_H4_interface':'H4_bedhead_A_v12'}
params['latest_bedhead_release']='床头夹具_A_V1.2_等宽轻量_M4x12_十九盘'
params['profiles']['bedhead_body_A_v12']={'status':'geometry_and_slice_checked','source':'evidence/bedhead_v12_geometry.json','front_arm':9.4,'top_beam':9.4,'rear_arm':9.4,'S_seat':13.6,'S_uniform_widths':[36,40,44],'H4_uniform_widths':[48,50,54],'clamp_ranges':[[20,40],[35,55],[50,70]],'body_walls':4,'body_infill_percent':30,'support':'normal(auto)','limitations':'未进行V1.2实物验证；板背支撑距离需更新；不是额定荷载参数'}
params['profiles']['S_M4_bedhead_A_v12']={'status':'geometry_and_slice_checked','source':'evidence/bedhead_v12_geometry.json','values':{k:v for k,v in geo['assembly']['m4'].items() if k!='all_variants'},'limitations':'只按M4x12+5mm板+无垫片；16/18/25不可沿用'}
params['profiles']['H4_bedhead_A_v12']={'status':'geometry_and_slice_checked','source':'evidence/bedhead_v12_geometry.json','values':geo['assembly']['hooks'],'front_arm':9.4,'tip_above_beam':4.6,'limitations':'孔位YZ不变；X随前臂减薄向家具靠近4.6；未实物验证'}
(SOP/'parameters.json').write_text(json.dumps(params,ensure_ascii=False,indent=2),encoding='utf8')
for src,dst in [('几何装配验证.json','bedhead_v12_geometry.json'),('最终文件独立核验.json','bedhead_v12_export_verification.json'),('实际切片结果.json','bedhead_v12_slice_result.json')]:shutil.copy2(ROOT/'技术资料'/src,SOP/'evidence'/dst)
photo=Path('C:/Users/hrcao/Downloads/IMG_20260928_095853.jpg')
(SOP/'evidence/bedhead_user_feedback_20260928.json').write_text(json.dumps({'photo_filename':photo.name,'photo_sha256':hashlib.sha256(photo.read_bytes()).hexdigest(),'observation':'visible loose/suspended strands and surface defects on prior prints','cause_limit':'photo alone cannot establish all causes','request':'uniform widths, reduce edges and thickness about one third, preserve interface positions, M4x12 only','new_physical_validation':False},ensure_ascii=False,indent=2),encoding='utf8')
print('SOP V1.2 profile and feedback recorded.')
