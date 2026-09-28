from pathlib import Path
import json,shutil,hashlib
BASE=Path(__file__).parent;ROOT=BASE/'releases/床头夹具_A_V1.3_斜面防滑_多长度螺杆_二十盘';SOP=Path('docs/skadis-design-sop')
geo=json.loads((ROOT/'技术资料/几何装配验证.json').read_text(encoding='utf8'))
verification=json.loads((ROOT/'技术资料/最终文件独立核验.json').read_text(encoding='utf8'))
result=json.loads((BASE/'slice-v13-final/result.json').read_text(encoding='utf8'));assert result['return_code']==0 and len(result['sliced_plates'])==20
p=json.loads((SOP/'parameters.json').read_text(encoding='utf8'))
p['latest_bedhead_release']=ROOT.name;p['preferred_profiles']['bedhead_body']='bedhead_body_A_v13';p['preferred_profiles']['optional_coarse_screws']='coarse_screw_set_A_v13'
p['profiles']['bedhead_body_A_v13']={'status':'geometry_and_slice_checked','source':'evidence/bedhead_v13_geometry.json','inherits_dimensions':'bedhead_body_A_v12','grip':geo['assembly']['grip'],'limitations':'最大内收减少净开口；未实测摩擦和承重；圆角区域不改变外侧挂孔'}
p['profiles']['coarse_screw_set_A_v13']={'status':'geometry_and_slice_checked','source':'evidence/bedhead_v13_geometry.json','variants':geo['assembly']['extra_screws'],'limits':'P is max working projection with 2mm knob clearance, not board thickness or a physical stop; only geometry checked'}
(SOP/'parameters.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf8')
for src,dst in [('几何装配验证.json','bedhead_v13_geometry.json'),('最终文件独立核验.json','bedhead_v13_export_verification.json')]:shutil.copy2(ROOT/'技术资料'/src,SOP/'evidence'/dst)
shutil.copy2(BASE/'slice-v13-final/result.json',SOP/'evidence/bedhead_v13_slice_result.json')
(ROOT/'技术资料/V1.2对比_主体减料.json').write_text(json.dumps(verification['grip'],ensure_ascii=False,indent=2),encoding='utf8')
print('V1.3 SOP and evidence updated.')
