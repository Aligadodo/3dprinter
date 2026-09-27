from pathlib import Path
import subprocess,json
B=Path('output/skadis-corner-support').resolve();R=B/'releases'/'MSkadis洞洞板柜顶挂架_V1.0_20260926'
p=subprocess.run([r'D:\3d\Bambu Studio\bambu-studio.exe','--slice','0','--arrange','0','--orient','0','--outputdir',str(B/'slice-release-extra'),str(R/'V1_额外补打_S与L主架各一对_两盘.3mf')],capture_output=True,timeout=180)
print('exit',p.returncode)
(B/'slice-release-extra.log').write_bytes(p.stdout+p.stderr)
