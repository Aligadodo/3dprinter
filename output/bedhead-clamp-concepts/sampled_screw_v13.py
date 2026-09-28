"""Length variants from a sampled source thread profile; no axial scaling."""
import numpy as np,trimesh,math

def sample_profile(source_mesh):
 section=source_mesh.section([0,1,0],[0,0,0])
 a=np.concatenate([c[:-1] for c in section.discrete]);b=np.concatenate([c[1:] for c in section.discrete])
 phases=np.linspace(0,4,801);radii=[]
 for z in phases:
  mask=(np.minimum(a[:,2],b[:,2])<=z)&(np.maximum(a[:,2],b[:,2])>z)
  aa=a[mask];bb=b[mask];xx=aa[:,0]+(z-aa[:,2])/(bb[:,2]-aa[:,2])*(bb[:,0]-aa[:,0]);radii.append(float(max(xx)))
 radii[-1]=radii[0]
 return phases,np.array(radii)

def shaft_mesh(profile,rootz,tipz=28,radial_allowance=.04):
 phases,radii=profile;N=128;zz=np.linspace(rootz,tipz,int(math.ceil((tipz-rootz)/.08))+1);theta=np.arange(N)*2*np.pi/N
 phase=(zz[:,None]-theta[None,:]*4/(2*np.pi))%4
 r=np.interp(phase,phases,radii)-radial_allowance
 # Small lead-in at the tip; a constant 5 mm central bore matches the source.
 r=np.minimum(r,6.45+(tipz-zz[:,None])*2)
 outer=np.stack([r*np.cos(theta),r*np.sin(theta),np.broadcast_to(zz[:,None],r.shape)],axis=-1).reshape(-1,3)
 inner=np.stack([np.broadcast_to(2.5*np.cos(theta),r.shape),np.broadcast_to(2.5*np.sin(theta),r.shape),np.broadcast_to(zz[:,None],r.shape)],axis=-1).reshape(-1,3)
 v=np.vstack([outer,inner]);off=len(outer);f=[]
 for j in range(len(zz)-1):
  for i in range(N):
   a=j*N+i;b=j*N+(i+1)%N;c=(j+1)*N+(i+1)%N;d=(j+1)*N+i
   f.extend([(a,b,c),(a,c,d),(a+off,c+off,b+off),(a+off,d+off,c+off)])
 for j,flip in [(0,True),(len(zz)-1,False)]:
  for i in range(N):
   a=j*N+i;b=j*N+(i+1)%N
   faces=[(a,b,b+off),(a,b+off,a+off)]
   f.extend([t[::-1] if flip else t for t in faces])
 m=trimesh.Trimesh(v,np.array(f),process=False);assert m.is_watertight and m.is_winding_consistent and m.volume>0
 return m
