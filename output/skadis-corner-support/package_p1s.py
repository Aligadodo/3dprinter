from pathlib import Path
import zipfile,json,xml.etree.ElementTree as E,copy
ROOT=Path(__file__).parent/'print-kit-v1'
PROFILES=Path(r'D:\3d\Bambu Studio\resources\profiles\BBL')
FILES={p.stem:p for p in PROFILES.rglob('*.json')}
META={'name','type','inherits','from','setting_id','instantiation','description','include','filament_id'}
def resolve(name,seen=None):
    seen=set() if seen is None else set(seen)
    if name in seen: raise ValueError(name)
    seen.add(name);d=json.loads(FILES[name].read_text(encoding='utf8'));out={}
    if d.get('inherits'): out.update(resolve(d['inherits'],seen))
    for inc in d.get('include',[]): out.update(resolve(inc,seen))
    out.update({k:v for k,v in d.items() if k not in META});return out
with zipfile.ZipFile('scripts/templates/bambu/base.3mf') as z:
    settings=json.loads(z.read('Metadata/project_settings.config'))
base_settings=copy.deepcopy(settings)
filament=resolve('Generic PETG')
settings.update({k:v for k,v in filament.items() if k in settings and type(v)==type(settings[k])})
settings.update({
 'printer_model':'Bambu Lab P1S','printer_settings_id':'Bambu Lab P1S 0.4 nozzle',
 'print_settings_id':'Skadis M4 PETG 0.20 6walls','filament_settings_id':['Generic PETG'],
 'filament_type':['PETG'],'filament_ids':['GFG99'],'filament_colour':['#289d90'],
 'filament_is_support':['0'],'filament_diameter':['1.75'],'filament_density':['1.27'],
 'layer_height':'0.2','initial_layer_print_height':'0.2','wall_loops':'6',
 'top_shell_layers':'6','bottom_shell_layers':'6','top_shell_thickness':'1.2',
 'sparse_infill_density':'50%','sparse_infill_pattern':'gyroid',
 'enable_support':'0','support_type':'normal(auto)','brim_type':'no_brim','brim_width':'0',
 'enable_prime_tower':'0','prime_tower_enable':'0','print_sequence':'by layer',
 'curr_bed_type':'Textured PEI Plate','filament_map':['1'],
 'wall_filament':'1','sparse_infill_filament':'1','solid_infill_filament':'1',
 'support_filament':'0','support_interface_filament':'0',
 'outer_wall_speed':['60'],'inner_wall_speed':['90'],'sparse_infill_speed':['100'],
 'internal_solid_infill_speed':['90'],'top_surface_speed':['60'],'initial_layer_speed':['30'],
 'filament_max_volumetric_speed':['8'],'additional_cooling_fan_speed':['0'],
 'fan_min_speed':['30'],'fan_max_speed':['60'],'overhang_fan_speed':['80'],
 'flush_volumes_matrix':['0'],'flush_volumes_vector':['0','0'],'filament_flush_multiplier':['1'],
 'wipe_tower_x':['15'],'wipe_tower_y':['220'],
})
# This Bambu build uses two values per filament for some fields; preserve that stride.
for k,v in list(settings.items()):
    if isinstance(v,list) and v and (k.startswith('filament_') or k in filament):
        old=base_settings.get(k,[])
        stride=2 if isinstance(old,list) and len(old) in (2,8) else 1
        settings[k]=[v[0]]*stride
for k in ['outer_wall_speed','inner_wall_speed','sparse_infill_speed','internal_solid_infill_speed','top_surface_speed','initial_layer_speed']:
    settings[k]=[settings[k][0]]*len(base_settings.get(k,['0','0']))
settings['filament_map']=['1']
# Retain the installed template's vector dimensions. Mixing the newer resource
# schema with this executable crashes its CLI for the larger plates.
settings=copy.deepcopy(base_settings)
settings.update({'printer_model':'Bambu Lab P1S','printer_settings_id':'Bambu Lab P1S 0.4 nozzle',
 'print_settings_id':'Skadis M4 PETG 0.20 6walls','layer_height':'0.2','initial_layer_print_height':'0.2',
 'wall_loops':'6','sparse_infill_density':'50%','sparse_infill_pattern':'gyroid',
 'top_shell_layers':'6','bottom_shell_layers':'6','top_shell_thickness':'1.2',
 'enable_prime_tower':'0','enable_support':'0','brim_type':'no_brim','brim_width':'0',
 'curr_bed_type':'Textured PEI Plate','print_sequence':'by layer','wall_filament':'1',
 'sparse_infill_filament':'1','solid_infill_filament':'1','support_filament':'0','support_interface_filament':'0'})
for k,val in [('filament_type','PETG'),('filament_density','1.27'),('filament_settings_id','Generic PETG'),
 ('filament_ids','GFG99'),('filament_colour','#289D90'),('nozzle_temperature','255'),
 ('nozzle_temperature_initial_layer','255'),('textured_plate_temp','70'),('textured_plate_temp_initial_layer','70'),
 ('fan_min_speed','30'),('fan_max_speed','60'),('overhang_fan_speed','80'),('additional_cooling_fan_speed','0'),
 ('filament_max_volumetric_speed','8'),('outer_wall_speed','60'),('inner_wall_speed','90'),
 ('sparse_infill_speed','100'),('internal_solid_infill_speed','90'),('top_surface_speed','60'),('initial_layer_speed','30')]:
    old=settings.get(k,['0']);settings[k]=[val]*len(old) if isinstance(old,list) else val
(ROOT/'P1S-PETG-settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf8')
CORE='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
BBL='http://schemas.bambulab.com/package/2021'
PROD='http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
E.register_namespace('',CORE);E.register_namespace('BambuStudio',BBL)
E.register_namespace('p',PROD)
T=lambda t:'{'+CORE+'}'+t
def addmeta(p,k,v): E.SubElement(p,'metadata',{'key':k,'value':str(v)})
def project(path,plates):
    r=E.Element(T('model'),{'unit':'millimeter','xml:lang':'en-US','xmlns:BambuStudio':BBL,'requiredextensions':'p'})
    E.SubElement(r,T('metadata'),{'name':'Application'}).text='BambuStudio-02.06.00.51'
    E.SubElement(r,T('metadata'),{'name':'BambuStudio:3mfVersion'}).text='1'
    E.SubElement(r,T('metadata'),{'name':'Title'}).text='MSkadis M4 PETG prototypes S M L'
    res=E.SubElement(r,T('resources'));build=E.SubElement(r,T('build'));config=E.Element('config');objects=[];count=0;extra={}
    rels=E.Element('Relationships',xmlns='http://schemas.openxmlformats.org/package/2006/relationships')
    for n,src in enumerate(plates):
        x=(n%3)*307.2;y=-(n//3)*307.2
        with zipfile.ZipFile(src) as z: rr=E.fromstring(z.read('3D/3dmodel.model'))
        count+=1;parent_id=count;ids=[parent_id]
        parent=E.SubElement(res,T('object'),{'id':str(parent_id),'type':'model'})
        components=E.SubElement(parent,T('components'))
        co=E.SubElement(config,'object',{'id':str(parent_id)})
        addmeta(co,'name',src.stem);addmeta(co,'extruder',1)
        E.SubElement(build,T('item'),{'objectid':str(parent_id),'printable':'1','transform':f'1 0 0 0 1 0 0 0 1 {x} {y} 0'})
        for o in rr.find(T('resources')):
            count+=1;child=count;o=copy.deepcopy(o);o.set('id',str(child))
            sub=E.Element(T('model'),{'unit':'millimeter'})
            E.SubElement(sub,T('resources')).append(o)
            partpath=f'3D/Objects/object_{child}.model'
            extra[partpath]=E.tostring(sub,encoding='utf-8',xml_declaration=True)
            E.SubElement(components,T('component'),{'{'+PROD+'}path':'/'+partpath,'objectid':str(child),'transform':'1 0 0 0 1 0 0 0 1 0 0 0'})
            E.SubElement(rels,'Relationship',{'Target':'/'+partpath,'Id':f'rel{child}','Type':'http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel'})
            part=E.SubElement(co,'part',{'id':str(child),'subtype':'normal_part'})
            addmeta(part,'name',o.get('name','part'));addmeta(part,'matrix','1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1')
            addmeta(part,'extruder',1)
            E.SubElement(part,'mesh_stat',{'face_count':str(len(o.find(T('mesh')).find(T('triangles')))),'edges_fixed':'0','degenerate_facets':'0','facets_removed':'0','facets_reversed':'0','backwards_edges':'0'})
        objects.append((n,src,ids))
    for n,src,ids in objects:
        p=E.SubElement(config,'plate');addmeta(p,'plater_id',n+1);addmeta(p,'plater_name',src.stem)
        addmeta(p,'locked','false');addmeta(p,'filament_maps','1')
        for i in ids:
            ins=E.SubElement(p,'model_instance');addmeta(ins,'object_id',i);addmeta(ins,'instance_id',0);addmeta(ins,'identify_id',i)
    with zipfile.ZipFile(plates[0]) as z: base={n:z.read(n) for n in ['[Content_Types].xml','_rels/.rels']}
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in base.items():z.writestr(n,b)
        for n,b in extra.items():z.writestr(n,b)
        z.writestr('3D/_rels/3dmodel.model.rels',E.tostring(rels,encoding='utf-8',xml_declaration=True))
        z.writestr('3D/3dmodel.model',E.tostring(r,encoding='utf-8',xml_declaration=True))
        z.writestr('Metadata/model_settings.config',E.tostring(config,encoding='utf-8',xml_declaration=True))
        local_settings=dict(settings)
        local_settings['wipe_tower_x']=['15']*len(plates);local_settings['wipe_tower_y']=['220']*len(plates)
        z.writestr('Metadata/project_settings.config',json.dumps(local_settings,ensure_ascii=False))
sources=sorted((ROOT/'plates').glob('*.3mf'))
folder=ROOT/'P1S-projects';folder.mkdir(exist_ok=True)
for s in sources:project(folder/s.name,[s])
project(ROOT/'P1S_PETG_M4_SML_all_7plates.3mf',sources)
print(json.dumps({'project_count':len(sources)+1,'temperature':settings.get('nozzle_temperature'),'bed':settings.get('textured_plate_temp'),'printer':settings['printer_model']},ensure_ascii=False))
