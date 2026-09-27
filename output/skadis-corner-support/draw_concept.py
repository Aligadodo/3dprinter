from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
im = Image.new('RGB', (1600, 1080), '#f7f8fa')
d = ImageDraw.Draw(im)
font = 'C:/Windows/Fonts/msyh.ttc'
bold = 'C:/Windows/Fonts/msyhbd.ttc'
navy, teal, orange, gray = '#20344d', '#16877c', '#d87732', '#8b97a5'
def text(x, y, s, size=23, fill=navy, heavy=False):
    d.text((x,y), s, fill=fill, font=ImageFont.truetype(bold if heavy else font,size))
def line(pts, fill=navy, width=3): d.line(pts, fill=fill, width=width)
def arrow(a,b,fill=orange):
    import math
    line([a,b],fill,5)
    t=math.atan2(b[1]-a[1],b[0]-a[0])
    p=[b,(b[0]-16*math.cos(t-.45),b[1]-16*math.sin(t-.45)),(b[0]-16*math.cos(t+.45),b[1]-16*math.sin(t+.45))]
    d.polygon(p,fill=fill)

text(55,30,'MSkadis 200｜可续接承重挂架',40,heavy=True)
text(55,89,'概念示意 · 非加工图 · 尺寸待按家具与负载定版',22,gray)
text(55,150,'01 侧视：顶部承压，额外结构防拉脱',27,heavy=True)
# Furniture to left, outside to right; L remains outside the furniture envelope.
d.rectangle((70,315,380,745),fill='#dfe3e8')
text(115,550,'柜体 / 桌板',25,gray)
d.polygon([(160,285),(412,285),(430,303),(430,486),(400,486),(400,315),(160,315)],fill=teal)
d.rectangle((170,315,365,322),fill='#7ac6b5')
text(75,222,'顶部搭接约 100 mm',22)
line([(225,253),(225,281)],gray)
text(480,258,'外侧圆角 / 加强',22)
line([(475,290),(429,303)],gray)
# Cleat with bolt pin and keeper, to outside of L
d.polygon([(430,370),(446,370),(446,425),(482,425),(482,398),(498,398),(498,443),(430,443)],fill=teal)
d.rectangle((457,382,474,728),fill=orange)
d.ellipse((452,403,478,429),fill=navy)
line([(438,391),(493,391)],navy,8)
text(520,350,'宽钩座 + 横销 + 防抬挡片',21)
line([(515,383),(486,411)],gray)
text(520,455,'承重背条',22,orange)
line([(513,477),(474,490)],orange)
# panel and standoffs
d.rectangle((510,500,525,735),fill='#b9cadb')
for yy in [530,692]:
    d.rectangle((474,yy,510,yy+12),fill=navy)
    d.rectangle((380,yy,457,yy+12),fill='#8b97a5')
text(545,594,'板独立固定',22)
line([(540,628),(522,648)],gray)
arrow((560,688),(560,744))
text(583,704,'重量',21,orange)
# anti-slip strap schematic
line([(180,278),(77,278)],navy,5)
arrow((130,278),(72,278),navy)
text(55,782,'柜顶：跨顶到对侧限位；桌沿：加下夹爪',22)
text(55,818,'软垫只用于保护，不能替代防外拉连接。',21,gray)
# front assembly view
text(830,150,'02 背视：每列双背条，每板四点固定',27,heavy=True)
scale=0.86; x0=930; y0=267; sz=200*scale; gap=8
for j in range(3):
    y=y0+j*(sz+gap)
    d.rounded_rectangle((x0,y,x0+sz,y+sz),radius=7,fill='#e0e8f0',outline='#8ba1b7',width=2)
    for col in range(1,9):
        for row in range(4):
            xx=x0+col*20*scale; yy=y+20+row*40*scale+(17 if col%2 else 0)
            d.rounded_rectangle((xx-2,yy,xx+2,yy+12),radius=2,fill='#fff')
for xx in [x0+12.5*scale,x0+187.5*scale]:
    d.rectangle((xx-9,230,xx+9,y0+3*sz+2*gap),fill=orange)
    d.rounded_rectangle((xx-18,202,xx+18,255),radius=5,fill=teal)
    for j in range(3):
        y=y0+j*(sz+gap)
        for yy in [y+12.5*scale,y+187.5*scale]: d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=navy)
    for j in [1,2]:
        yy=y0+j*(sz+gap)-gap/2
        d.rectangle((xx-13,yy-39,xx+13,yy+39),fill='#52697f')
        for off in [-28,-15,15,28]: d.ellipse((xx-3,yy+off-3,xx+3,yy+off+3),fill='white')
text(1160,211,'每列两个 L 挂架',22,teal)
line([(1150,240),(1110,230)],teal)
text(1160,312,'安装孔距 175 mm',22)
text(1160,352,'单板 200 × 200 × 5',22)
text(1160,438,'双面盖板续接',22)
line([(1150,470),(1100,445)],gray)
text(1160,516,'贯穿螺栓锁紧',22)
text(1160,602,'新增板接背条',22)
text(1160,642,'载荷向上传到挂架',22,orange)
arrow((879,694),(879,278),orange)
text(835,813,'横向每增加一列，也增加一对顶部支点。',21,gray)
line([(55,879),(1545,879)],'#d0d8e1',2)
text(55,910,'打印方向',26,heavy=True)
text(55,953,'L / J 侧剖面平放热床，连续轮廓绕过转角；背条和盖板大面平放。',25)
text(55,1000,'已测量源模型；未进行承载试验。此图不代表额定载荷或最终装配尺寸。',21,gray)
im.save(OUT/'concept.png')
