from pathlib import Path
import trimesh,numpy as np,manifold3d as md,json
P=Path(__file__).parent/'revision-a'
def solid(m):return md.Manifold(md.Mesh(np.asarray(m.vertices,np.float32),np.asarray(m.faces,np.uint32)))
male=solid(trimesh.load(P/'概念网格_未定型'/'共用粗螺杆_总长45_杆身35_旋钮10_概念.stl')).simplify(.01)
female=solid(trimesh.load(P/'extracted-female-thread.stl')).translate((-13.65,0,0)).simplify(.01)
# Both retain the original z axis. At this position the shortened shaft spans the sleeve.
delta=-37.5
values=[]
for angle in range(0,360,15):
 vol=(female^male.rotate((0,0,angle)).translate((0,0,delta))).volume()
 values.append([angle,vol])
best=min(values,key=lambda q:q[1]);print('phase scan',values,flush=True)
checks=[]
for sign in [-1,1]:
 for dz in [0,.5,1,2,3,4,8,16,20]:
  angle=best[0]+sign*dz*90
  vol=(female^male.rotate((0,0,angle)).translate((0,0,delta+dz))).volume()
  checks.append([sign,dz,vol])
print('helical sweep',checks,flush=True)
(P/'thread-fit-scan.json').write_text(json.dumps({'phase_scan':values,'best':best,'sweep':checks},indent=2))
