"""Chinese engineering illustrations from delivered STL geometry and measured interfaces.
Does not modify any printable model or project.
"""
from pathlib import Path
import math,json,zipfile,html,shutil
import numpy as np
import trimesh
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).parent/'print-kit-v1'
OUT=ROOT/'中文装配图解';OUT.mkdir(exist_ok=True)
STL=ROOT/'STL'
BG='#f7f9fc';INK='#23384e';MUTED='#62778b';GREEN='#168c80';ORANGE='#df8a3a';BLUE='#658ba9';YELLOW='#e5b632';METAL='#8793a0';RED='#b4543c';WOOD='#e3d8c8'
F='C:/Windows/Fonts/msyh.ttc';FB='C:/Windows/Fonts/msyhbd.ttc'
def font(n,b=False):return ImageFont.truetype(FB if b else F,n)
def text(d,x,y,s,n=27,c=INK,b=False):d.text((x,y),s,font=font(n,b),fill=c)
def lines(d,x,y,ss,n=26,c=INK,gap=40):
    for i,s in enumerate(ss):text(d,x,y+i*gap,s,n,c)
def canvas(title,subtitle,w=1800,h=1150):
    im=Image.new('RGB',(w,h),BG);d=ImageDraw.Draw(im)
    text(d,45,25,title,40,b=True);text(d,45,83,subtitle,25,MUTED)
    return im,d
def arrow(d,a,b,c=RED,width=5):
    d.line([a,b],fill=c,width=width)
    t=math.atan2(b[1]-a[1],b[0]-a[0]);p=[b,(b[0]-17*math.cos(t-.43),b[1]-17*math.sin(t-.43)),(b[0]-17*math.cos(t+.43),b[1]-17*math.sin(t+.43))]
    d.polygon(p,fill=c)
def dash(d,a,b,c=MUTED,width=2):
    v=np.array(b,float)-a;L=np.linalg.norm(v)
    if not L:return
    for t in np.arange(0,L,13):d.line([tuple(np.array(a)+v*t/L),tuple(np.array(a)+v*min(t+7,L)/L)],fill=c,width=width)
def badge(d,x,y,s,c=INK):
    d.ellipse((x-19,y-19,x+19,y+19),fill=c);bb=d.textbbox((0,0),s,font=font(23,True));d.text((x-(bb[2]-bb[0])/2,y-17),s,font=font(23,True),fill='white')
def dim(d,a,b,s,offset=0):
    d.line([a,b],fill=MUTED,width=2)
    for x,y in [a,b]:d.line([(x-5,y-6),(x+5,y+6)],fill=MUTED,width=2)
    text(d,(a[0]+b[0])/2-35,(a[1]+b[1])/2+offset,s,20,MUTED)
def finish(im,name):im.save(OUT/name)

cache={}
def load(name):
    if name not in cache:cache[name]=trimesh.load_mesh(STL/(name+'.stl'))
    return cache[name].copy()
def rgb(c):return tuple(int(c[i:i+2],16) for i in (1,3,5))
def render(d,objects,rect,view=(1,-1,1.2)):
    v=np.array(view,float);v/=np.linalg.norm(v)
    right=np.cross([0,0,1],v);right/=np.linalg.norm(right);up=np.cross(v,right)
    basis=np.array([right,-up,v]);entries=[];allv=[]
    for m,col in objects:
        p=m.vertices@basis.T;allv.append(p);color=rgb(col)
        for face,normal in zip(m.faces,m.face_normals):
            shade=.55+.45*abs(float(normal@v))
            entries.append((p[face,2].mean(),p[face,:2],tuple(int(q*shade) for q in color)))
    pp=np.vstack(allv);lo=pp[:,:2].min(0);hi=pp[:,:2].max(0)
    x,y,w,h=rect;scale=min(w/max(1e-6,hi[0]-lo[0]),h/max(1e-6,hi[1]-lo[1]))
    shift=np.array([x,y])+(np.array([w,h])-(hi-lo)*scale)/2-lo*scale
    for _,p,col in sorted(entries,key=lambda e:e[0]):d.polygon([tuple(t) for t in p*scale+shift],fill=col)

# 01: clear front/back map plus side installation, actual board pitch and component locations.
im,d=canvas('01｜装好后是什么样：柜顶挂架＋两根背条＋两块板','示例选 M 号主架；S / M / L 装法相同，只选同规格的一对。',1800,1250)
text(d,55,145,'正面定位图（背后的承重件用颜色透视显示）',26,b=True)
x0,y0,sc=145,325,1.56
for j in [0,1]:
    yy=y0+j*202*sc
    d.rounded_rectangle((x0,yy,x0+200*sc,yy+200*sc),radius=9,fill='#edf1f5',outline=BLUE,width=3)
    holes=json.loads((ROOT/'source-board-measurements.json').read_text(encoding='utf8'))['holes']
    for h in holes:
        cx,cy=h['center'];sx,sy=h['size']
        if sy<10:continue
        xx=x0+(cx+100)*sc;yv=yy+(100-cy)*sc
        d.rounded_rectangle((xx-sx*sc/2,yv-sy*sc/2,xx+sx*sc/2,yv+sy*sc/2),radius=4,fill='white',outline='#ccd7e0')
for x in [x0+12.5*sc,x0+187.5*sc]:
    d.rectangle((x-12*sc,y0-40*sc,x+12*sc,y0+404*sc),fill=ORANGE)
    d.rounded_rectangle((x-18*sc,y0-80*sc,x+18*sc,y0-20*sc),radius=4,fill=GREEN)
    seam=y0+202*sc
    d.rectangle((x-12*sc,seam-80*sc,x+12*sc,seam+80*sc),fill=BLUE)
    for dy in [-60,-40,40,60]:d.ellipse((x-5,seam+dy*sc-5,x+5,seam+dy*sc+5),fill='white')
    for j in [0,1]:
        for dy in [12.5,187.5]:
            yy=y0+(j*202+dy)*sc;d.ellipse((x-7,yy-7,x+7,yy+7),fill=YELLOW,outline=INK,width=2)
    yy=y0+(202+162)*sc;d.rounded_rectangle((x-16,yy-16,x+16,yy+16),radius=3,fill='#947fac')
for number,pos in [('A',(110,215)),('B',(490,362)),('C',(490,824)),('D',(490,618)),('G',(110,865))]:badge(d,*pos,number)
lines(d,550,215,['A  两只 L 形挂架：搭在柜顶承重','B  头部背条：上端带反向斜钩','C  续接背条：让第二块板向下延伸','D  前后盖板：夹住背条接缝','E  隔柱：每块板背后放四个','F  薄垫圈：放在顶部锁紧螺栓下','G  靠垫：最下面抵住柜体侧面'],25,gap=60)
text(d,550,689,'黄色圆点：板固定的 M4×25',24,YELLOW,b=True)
text(d,550,735,'两块板之间留 2 mm 缝',25)
dim(d,(x0+12.5*sc,982),(x0+187.5*sc,982),'175 mm',10)
text(d,150,1040,'一块板四角各固定一次；板重直接传到背条。',24)
# side schematic, not to scale so face distinctions remain legible.
text(d,1160,145,'侧面：家具在左，洞洞板在右',26,b=True)
d.rectangle((1150,295,1340,930),fill=WOOD);text(d,1177,670,'柜体',28,MUTED)
d.polygon([(1200,262),(1368,262),(1368,438),(1340,438),(1340,295),(1200,295)],fill=GREEN)
d.polygon([(1368,345),(1407,326),(1407,392),(1368,392)],fill=GREEN)
d.polygon([(1373,313),(1426,313),(1426,930),(1409,930),(1409,329),(1373,347)],fill=ORANGE)
d.rectangle((1462,400,1480,925),fill='#c6d8e8')
for yy in [430,665,888]:d.rectangle((1426,yy,1462,yy+13),fill=YELLOW)
d.rectangle((1340,860,1409,890),fill='#947fac')
arrow(d,(1390,300),(1390,330),GREEN)
text(d,1520,400,'洞洞板',26);d.line([(1505,425),(1480,450)],fill=MUTED,width=2)
text(d,1520,515,'隔柱',26);d.line([(1510,545),(1444,672)],fill=MUTED,width=2)
text(d,1495,865,'靠垫抵住侧面',24);d.line([(1485,891),(1380,877)],fill=MUTED,width=2)
dash(d,(1225,250),(1090,250),RED,4);arrow(d,(1190,250),(1090,250),RED)
lines(d,1120,1010,['顶臂穿带孔：连接跨顶限位绑带。','绑带/对侧固定点需另配，图中未画全。','只靠 L 架摩擦，整套仍可能向外滑脱。'],23,RED,38)
text(d,50,1190,'第 1 盘是试配小样；第 8 盘是额外主架。两者不是另一层连接件。',27,b=True)
finish(im,'01_整体位置与用途.png')

# 02 catalogue, thumbnails directly from real STL meshes.
im,d=canvas('02｜把打印出来的零件认清楚','颜色用于区分图中的部件；全部可以用同一卷 PETG 打印。',1800,1640)
cards=[
 ('A','L 形挂架','L_M',GREEN,'第 2 / 3 / 4 盘；每列选同规格 2 个',['顶臂搭在柜顶，外侧斜扣承接背条。','S / M / L 不能在同一列左右混用。']),
 ('B','头部背条 242 mm','rail_head_242',ORANGE,'第 5 盘；每列 2 根',['一端有突出的反向斜钩，装在最上面。','正面朝板，带六角螺母槽的一面朝柜体。']),
 ('C','续接背条 202 mm','rail_extension_202',ORANGE,'第 6 盘；每加一块板用 2 根',['没有顶部斜钩，接在头部背条下面。','加长整列，支撑下一块洞洞板。']),
 ('D1','前连接盖板 8 mm','splice_front_160',BLUE,'第 6 盘；每个接头 1 块',['四个孔有大圆沉孔，朝向洞洞板。','螺栓头收进沉孔，避免顶到板背。']),
 ('D2','后连接盖板 6 mm','splice_back_160',BLUE,'第 6 盘；每个接头 1 块',['只有小通孔，放在背条的柜体一侧。','与前盖板共同夹住背条接缝。']),
 ('E','板背隔柱 10 mm','board_spacer_10',YELLOW,'第 7 盘；每块板 4 个',['厚圆筒，夹在洞洞板与背条之间。','为挂件插入和连接盖板留出空间。']),
 ('F','锁紧薄垫圈 1 mm','lock_spacer_1',YELLOW,'第 7 盘；每个顶部挂扣 1 个',['很薄的圆环，不是板背隔柱。','放在顶部 M4×25 螺栓的金属平垫下面。']),
 ('G','底部靠垫 25 / 27 / 29 mm','back_pad_27','#947fac','第 7 盘；每列选对应长度 2 个',['S 配 25，M 配 27，L 配 29 mm。','抵住家具侧面，减少晃动并保持间距。']),
 ('H','挂扣试配小样','fit_male_S',GREEN,'第 1 盘；第 7 盘也含备用小样',['公扣、母扣先试尺寸与螺母槽。','试配通过后收起来，不装进正式支架。']),
]
for i,(letter,title,name,color,where,desc) in enumerate(cards):
    x=45+(i%3)*585;y=145+(i//3)*490
    d.line([(x,y+467),(x+540,y+467)],fill='#d5dee8',width=2)
    text(d,x,y,letter+'  '+title,28,b=True)
    m=load(name);render(d,[(m,color)],(x+35,y+48,460,240))
    if letter=='H':render(d,[(load('fit_female'),ORANGE)],(x+325,y+170,185,100))
    text(d,x,y+305,where,23,MUTED)
    lines(d,x,y+348,desc,23,gap=39)
finish(im,'02_全部配件识别.png')

# Drawing helper for true side sections in original u/v assembly coordinates.
def sidepoly(d,pts,ox,oy,s,c,outline=INK):
    p=[(ox+u*s,oy+v*s) for u,v in pts];d.polygon(p,fill=c)
    if outline:d.line(p+[p[0]],fill=outline,width=2)
def rectuv(d,b,ox,oy,s,c):
    u0,v0,u1,v1=b;d.rectangle((ox+u0*s,oy+v0*s,ox+u1*s,oy+v1*s),fill=c,outline=INK,width=2)
def cleat(d,ox,oy,s,rail_shift=0,bolt=False):
    sidepoly(d,[(0,22),(12,22),(12,66),(28,50),(28,80),(12,80),(12,100),(0,100)],ox,oy,s,GREEN)
    # white nut slot with the nut seated; actual hex nut axis is perpendicular to side face.
    rectuv(d,(16,68.25,19.6,75.75),ox,oy,s,BG)
    rectuv(d,(16.2,68.5,19.4,75.5),ox,oy,s,YELLOW)
    pts=[(12.4,40),(36.4,40),(36.4,116),(28.4,116),(28.4,49.6),(12.4,65.6)]
    sidepoly(d,[(u,v+rail_shift) for u,v in pts],ox,oy,s,ORANGE)
    if bolt:
        rectuv(d,(36.4,66,37.4,78),ox,oy,s,YELLOW)
        rectuv(d,(37.4,67.5,38.4,76.5),ox,oy,s,METAL)
        rectuv(d,(13.4,70,38.4,74),ox,oy,s,METAL)
        rectuv(d,(38.4,68,42.4,76),ox,oy,s,METAL)
    return lambda u,v:(ox+u*s,oy+v*s)

im,d=canvas('03｜顶部挂扣怎么装：先放螺母，再落座，最后锁紧','侧面剖视放大；绿色是 L 架，橙色是头部背条。示例尺寸对应 M 号。',1800,1110)
for i,title in enumerate(['① 螺母从 L 架侧槽放入','② 背条从上往下挂入','③ 用 M4×25 防抬脱锁紧']):text(d,50+i*590,155,title,27,b=True)
p=cleat(d,150,190,4.3,-25,False)
arrow(d,(430,480),p(18,72),YELLOW)
lines(d,55,745,['金色块表示 M4 普通六角螺母。','从架子侧面送入，而不是塞进圆孔。','螺母槽深度按普通薄螺母设计。'],24,gap=44)
text(d,350,420,'侧向放入',24,YELLOW,b=True)
p=cleat(d,740,190,4.3,-20,False)
arrow(d,p(42,28),p(42,48),RED)
lines(d,645,745,['头部背条有斜钩的一端朝上。','向下放，让两片斜面接触承压。','先确认落座，再拧锁紧螺栓。'],24,gap=44)
p=cleat(d,1300,190,4.3,0,True)
arrow(d,(1700,650),p(40,72),METAL)
lines(d,1230,745,['从板这一侧拧入 M4×25。','顺序：螺栓 → 金属平垫 →','1 mm 打印薄垫圈 → 背条 → 螺母。'],24,gap=44)
text(d,60,925,'斜面承担主要竖向压力；锁紧螺栓防止背条抬起、松脱。',29,b=True)
lines(d,60,981,['顶部锁紧孔在洞洞板上方。这里不要使用 10 mm 厚隔柱，也不要换成 M4×10。','这颗螺栓锁的是“背条和 L 架”；家具端还需要另配跨顶绑带或其他可靠限位。'],25,RED,44)
finish(im,'03_顶部挂扣三步安装.png')

# 04 board fastening: readable axial stack + actual 25 mm engagement section.
im,d=canvas('04｜洞洞板怎么固定：每块板四角各一颗 M4×25','背条的六角螺母先装好；再放隔柱、洞洞板，最后从板正面拧螺栓。',1800,1090)
text(d,60,155,'从使用者这一侧 → 向柜体方向',29,b=True)
items=[('M4×25',METAL),('金属平垫',METAL),('洞洞板',BLUE),('10 mm 隔柱',YELLOW),('背条',ORANGE),('M4 螺母',YELLOW)]
for i,(name,col) in enumerate(items):
    x=70+i*285;text(d,x,240,name,27,col,True)
    if i==0:
        d.rectangle((x+20,355,x+190,371),fill=METAL);d.rectangle((x+10,338,x+36,388),fill=METAL)
    elif i==1:
        d.ellipse((x+40,320,x+130,410),fill=METAL);d.ellipse((x+71,350,x+101,380),fill=BG)
    elif i==2:
        d.rectangle((x+65,310,x+105,425),fill=BLUE);d.ellipse((x+72,350,x+98,380),fill=BG)
    elif i==3:render(d,[(load('board_spacer_10'),YELLOW)],(x+25,307,170,135))
    elif i==4:
        d.rectangle((x+50,303,x+110,430),fill=ORANGE);d.ellipse((x+66,348,x+94,376),fill=BG)
    else:
        pts=[(x+80+48*math.cos(a*math.pi/3),365+48*math.sin(a*math.pi/3)) for a in range(6)]
        d.polygon(pts,fill=YELLOW);d.ellipse((x+62,347,x+98,383),fill=BG)
    if i<5:arrow(d,(x+209,366),(x+259,366),MUTED,3)
text(d,1490,465,'螺母嵌进背条背面，',22)
text(d,1490,501,'不是悬在外面。',22)
text(d,60,520,'拧紧后的侧面剖视（螺母藏在背条内）',29,b=True)
ox,oy,sc=300,735,13
# positive axis runs from front toward cabinet; lengths in mm.
def r(x0,y0,x1,y1,c):d.rectangle((ox+x0*sc,oy+y0*sc,ox+x1*sc,oy+y1*sc),fill=c,outline=INK,width=2)
r(0,-8,1,8,METAL);r(1,-11,6,11,BLUE);r(6,-7,16,7,YELLOW);r(16,-13,24,13,ORANGE)
r(20.4,-4.3,24,-4.3+8.6,BG);r(20.7,-3.5,23.9,3.5,YELLOW)
r(0,-2,25,2,METAL);r(-4,-4,0,4,METAL)
arrow(d,(185,735),(240,735),METAL)
text(d,110,635,'螺栓头',24);text(d,315,920,'板厚 5',23,BLUE);text(d,430,920,'隔柱 10',23,YELLOW);text(d,557,965,'背条厚 8',23,ORANGE)
arrow(d,(853,625),(ox+22*sc,oy-3*sc),YELLOW)
lines(d,900,610,['每块板固定四个角孔。','左右孔距、上下孔距均为 175 mm。','隔柱留出板背空间，不能省略。','先放螺母，否则挂到柜上后不易操作。'],27,gap=58)
text(d,60,1023,'请使用平底头配金属平垫；锥形沉头不能直接强拧进本版平底承压位置。',25,RED)
finish(im,'04_洞洞板四角固定.png')

# 05 splice: actual STL exploded view and dimensional section.
im,d=canvas('05｜怎么向下接第二块板：每根背条都用前后盖板夹住接缝','一列有左右两根背条，所以这样的接头要做两套；共用 8 颗 M4×25。',1800,1200)
text(d,55,150,'爆炸图：拆开看，前后盖板各一块',28,b=True)
objects=[]
for name,depth,col in [('splice_front_160',45,BLUE),('splice_back_160',-45,BLUE)]:
    m=load(name);a=m.vertices.copy();m.vertices=np.c_[a[:,1]-12,np.full(len(a),depth)+a[:,2],-a[:,0]];objects.append((m,col))
# Show actual STL portions near the joint, preserving holes and their positions.
for top,col in [(True,ORANGE),(False,'#e8a052')]:
    m=load('rail_extension_202')
    m=m.slice_plane([122 if top else 80,0,0],[1,0,0] if top else [-1,0,0])
    a=m.vertices.copy();m.vertices=np.c_[a[:,1]-12,4-a[:,2],-(a[:,0]-122 if top else a[:,0]+80)]
    objects.append((m,col))
render(d,objects,(50,225,785,575),view=(1,1.7,1.0))
text(d,80,325,'后盖板',25,BLUE,b=True);d.line([(185,357),(337,380)],fill=BLUE,width=3)
text(d,595,451,'两段背条',25,ORANGE,b=True);d.line([(586,483),(444,518)],fill=ORANGE,width=3)
text(d,621,701,'前盖板',25,BLUE,b=True);d.line([(612,728),(528,693)],fill=BLUE,width=3)
lines(d,60,845,['前盖板：8 mm 厚，四个大圆沉孔朝板。','中间：两段背条端面对齐。','后盖板：6 mm 厚，朝柜体一侧。'],26,gap=47)
text(d,980,150,'接头孔位：四颗螺栓跨过接缝',28,b=True)
x=1215;y=250;s=2.7
d.rectangle((x-33,y,x+33,y+160*s),fill=BLUE,outline=INK,width=2)
dash(d,(1000,y+80*s),(1590,y+80*s),RED,4)
for q in [20,40,120,140]:d.ellipse((x-10,y+q*s-10,x+10,y+q*s+10),fill=METAL,outline=INK,width=2)
text(d,1390,y+80*s-35,'背条接缝',26,RED)
text(d,1320,720,'接缝两侧各两颗',26,b=True)
text(d,1320,764,'离接缝 40 / 60 mm',24)
# Side stack with head sunk into first plate; axial order front to back.
text(d,980,855,'穿过顺序',27,b=True)
lines(d,980,905,['M4×25 → 前盖板 → 背条 → 后盖板','→ 金属平垫 → M4 螺母','螺栓头收进前盖板的大圆沉孔。'],26,gap=44)
text(d,60,1105,'两块洞洞板之间留 2 mm 缝；背条端面本身对齐。不要把前后盖板当成第三根背条。',26,RED)
finish(im,'05_背条续接与盖板.png')

# 06 foot accurate section, plus selection/position inset.
im,d=canvas('06｜底部靠垫怎么装：抵住柜体，减少整列晃动','每列底部左右各一个；靠垫不是挂钩，也不替代顶部承重结构。',1800,1120)
text(d,55,150,'侧面剖视：以 M 号＋27 mm 靠垫为例',28,b=True)
ox,oy,s=115,290,10
def rr(b,c):rectuv(d,b,ox,oy,s,c)
rr((-5,0,0,46),WOOD)
rr((0,10,1.4,34),'#b8ada0')
rr((1.4,10,28.4,34),'#947fac')
rr((28.4,0,36.4,46),ORANGE)
rr((36.4,17.5,37.4,26.5),METAL)
rr((21.4,20,37.4,24),METAL);rr((37.4,18,41.4,26),METAL)
rr((22.8,18.4,26.4,25.6),YELLOW)
# re-draw shaft through the nut to make screw path explicit.
rr((21.4,20,37.4,24),METAL)
text(d,70,815,'柜体',26,MUTED);text(d,247,815,'靠垫 27 mm',27,'#947fac',True);text(d,450,865,'背条',26,ORANGE)
arrow(d,(750,472),(ox+40*s,oy+22*s),METAL)
text(d,700,409,'M4×16 从正面拧入',27,b=True)
arrow(d,(685,640),(ox+24.6*s,oy+25*s),YELLOW)
text(d,640,674,'M4 螺母先从靠垫侧槽放入',25)
text(d,65,949,'柜体与靠垫之间贴约 1–1.5 mm 软垫，按实际接触调节。',25)
text(d,1000,155,'选长度',29,b=True)
for j,(name,h) in enumerate([('S',25),('M',27),('L',29)]):
    text(d,1020,225+j*65,f'{name} 号主架  →  {h} mm 靠垫一对',27)
text(d,1000,465,'装在哪里',29,b=True)
lines(d,1000,525,['最下面一段 202 mm 续接背条。','从这段上端向下量 162 mm 的孔。','该孔距下端 40 mm；左右各安装一个。','继续加板时，把靠垫移到新的最底段。'],26,gap=58)
text(d,1000,833,'先在柜外装好，再把整列挂上去。',26,b=True)
text(d,55,1040,'所有尺寸都是名义配合；家具边角、软垫厚度不同，实际接触情况也会不同。',25,RED)
finish(im,'06_底部靠垫安装.png')

titles=[('01_整体位置与用途.png','先看整体位置'),('02_全部配件识别.png','认清每个配件'),('03_顶部挂扣三步安装.png','挂扣如何挂入和锁紧'),('04_洞洞板四角固定.png','洞洞板和隔柱怎么固定'),('05_背条续接与盖板.png','背条怎么向下续接'),('06_底部靠垫安装.png','靠垫怎么安装')]
body='\n'.join(f'<section id="p{i}"><h2>{i}. {html.escape(t)}</h2><a href="{html.escape(n)}" target="_blank"><img src="{html.escape(n)}" alt="{html.escape(t)}"></a></section>' for i,(n,t) in enumerate(titles,1))
nav=' · '.join(f'<a href="#p{i}">{i} {html.escape(t)}</a>' for i,(_,t) in enumerate(titles,1))
(OUT/'装配图解.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>洞洞板挂架中文装配图解</title><style>body{margin:24px auto;max-width:1400px;padding:0 18px;background:#f7f9fc;color:#23384e;font:18px/1.65 system-ui,sans-serif}h1{font-size:30px}h2{font-size:23px;margin-top:40px}img{display:block;width:100%;height:auto}a{color:#08786c}nav{line-height:2.2}p{max-width:1000px}@media print{section{break-before:page}nav{display:none}body{margin:0;padding:0}h2{margin:0}}</style><h1>洞洞板挂架：中文装配图解</h1><p>以同一尺寸的两个主架、上下两块洞洞板为例。先做试配，然后在柜外装背条、盖板、靠垫和洞洞板，最后挂入顶部主架并锁紧。点击图片可以放大查看。</p><nav>'''+nav+'</nav>'+body+'''<p>此图解对应当前 M4 原型套件。结构尚未进行实物承重评级；家具端防外拉绑带、对侧固定点或夹具需另配。金属件图形为示意，装配尺寸以配套说明为准。</p></html>''',encoding='utf8')
(OUT/'阅读顺序.md').write_text('''# 中文装配图解

打开「装配图解.html」连续查看六张图，也可以单独打开 PNG 放大。

1. 先看整套装好后的正面和侧面。
2. 用配件识别图对照打印出的零件；同一列只选同规格的一对主架。
3. 顶部反向斜钩先从上往下落座，再用 M4×25 锁紧。
4. 每块洞洞板四角：M4×25 → 金属平垫 → 板 → 10 mm 隔柱 → 背条内的螺母。
5. 每个续接处：前盖板＋两段背条＋后盖板，四颗 M4×25 锁紧。
6. 对应尺寸的靠垫用 M4×16 固定在最下面的背条，贴软垫后抵住柜体。

第 1 盘和第 7 盘的试配小样不装进成品；第 8 盘是额外主架。正式挂载前必须完成家具端防外拉限位。
'''.replace('\n+','\n'),encoding='utf8')
readme=ROOT/'README-打印说明.md';s=readme.read_text(encoding='utf8')
link='装配不清楚时，请先打开 [六张中文装配图解](中文装配图解/装配图解.html)。\n\n'
if link not in s:readme.write_text(link+s,encoding='utf8')
shutil.copy2(Path(__file__),ROOT/'source'/Path(__file__).name)
for name in ['洞洞板挂架_P1S_PETG_M4_中文分盘打印包.zip','MSkadis_P1S_PETG_M4_SML_print-kit.zip']:
    with zipfile.ZipFile(ROOT.parent/name,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob('*')):
            if p.is_file():z.write(p,'洞洞板挂架打印包/'+p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(ROOT.parent/'洞洞板挂架_六张中文装配图解.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.iterdir()):z.write(p,'中文装配图解/'+p.name)
print(json.dumps({'images':len(titles),'folder':str(OUT.resolve())},ensure_ascii=True))
