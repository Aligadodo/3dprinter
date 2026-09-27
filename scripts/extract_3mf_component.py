"""Extract ONE mesh in source-local coordinates; never flatten a whole project implicitly."""
from pathlib import Path
import argparse,zipfile,json,hashlib
import xml.etree.ElementTree as E
import numpy as np,trimesh
C='{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
def extract(source,member,object_id,output):
 source=Path(source);output=Path(output)
 with zipfile.ZipFile(source) as z:
  root=E.fromstring(z.read(member));unit=root.get('unit','millimeter')
  factor={'micron':.001,'millimeter':1,'centimeter':10,'meter':1000,'inch':25.4,'foot':304.8}[unit]
  o=root.find(f"{C}resources/{C}object[@id='{object_id}']")
  if o is None or o.find(C+'mesh') is None:raise ValueError('Object is absent or is an assembly; select an explicit mesh member/ID from catalog.')
  vv=np.array([[float(v.get(k)) for k in ['x','y','z']] for v in o.findall(C+'mesh/'+C+'vertices/'+C+'vertex')])*factor
  ff=np.array([[int(t.get(k)) for k in ['v1','v2','v3']] for t in o.findall(C+'mesh/'+C+'triangles/'+C+'triangle')])
  m=trimesh.Trimesh(vv,ff,process=False);output.parent.mkdir(parents=True,exist_ok=True);m.export(output)
  read=trimesh.load(output)
  assert np.allclose(read.bounds,m.bounds,atol=.001)
 record={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'member':member,'object_id':str(object_id),'source_unit':unit,'output_unit':'mm','coordinate_space':'source mesh local; no build/component transforms applied','output':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'extents_mm':read.extents.tolist(),'watertight':bool(read.is_watertight),'mesh_only_not_assembly':True}
 output.with_suffix('.source.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8');return record
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('member');p.add_argument('object_id');p.add_argument('output');a=p.parse_args();print(json.dumps(extract(a.source,a.member,a.object_id,a.output),ensure_ascii=False))
