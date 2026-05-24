# 多色3D打印技术调研 & 实施方案

> 2026-05-22 | 调研 hicolors-3d / Kromacut / Lumina-Layers / HueForge

---

## 一、技术路线对比总览

FDM 多色打印目前有两条主流技术路线：

| 路线 | 原理 | 代表工具 | 需要的硬件 |
|------|------|---------|-----------|
| **纵向叠色** | Z轴方向分层堆叠不同颜色，利用PLA半透明特性混合 | HueForge, Kromacut, hicolors-3d | 单喷头即可（手动换料） |
| **横向拼色** | 同一层内不同区域用不同颜色，类似像素画 | Lumina-Layers | AMS / 多喷头 |

我们的浮雕/透光浮雕场景更契合**纵向叠色**路线。

---

## 二、四个关键系统的深度分析

### 2.1 hicolors-3d（叠影3D）— 闭源 Web 应用

**状态:** 闭源，无公开代码，网站 hicolors3d.com

**核心技术:**
- **颜色区域匹配** — 用色彩+区域匹配代替灰度映射，确保每个区域找到目标颜色
- **TD 物理叠色** — Beer-Lambert 定律计算多层叠加后的视觉颜色
- **精准层高分配** — 在 0.08mm 层高中物理模拟所有颜色叠加组合
- **3MF 内置换色指令** — 导出文件直接包含换色层高信息
- **无需 AMS** — 手动在特定层高换料

**可借鉴点:**
- 颜色区域匹配 + 区域分块的思路（不是逐像素灰度映射）
- 3MF 换色指令的嵌入方式
- 用户体验设计（面向小白用户的简化操作流）

**不可直接复用:** 闭源，无 API，仅能通过 Web UI 使用。

---

### 2.2 Kromacut — 开源 HueForge 替代（React + TypeScript + Three.js）

**仓库:** github.com/vycdev/Kromacut | **许可:** 免费开源（个人+商用）

#### 核心算法流程

```
用户定义每种 filament 的 RGB 颜色 + TD 值
                    ↓
         【Step 1】Filament 排序
   默认: 亮度排序（暗→亮，底部→顶部）
   高级: 模拟退火/遗传算法搜索最优排列
                    ↓
         【Step 2】Transition Zone 计算
   对每对相邻 filament，逐层模拟 Beer-Lambert 混合
   直到 DeltaE < 2.3（人眼不可分辨）或 不透明度 > 85%
   最底层 filament 额外分配 TD×1.3 的基础区（~95%不透明）
                    ↓
         【Step 3】高度压缩（如需要）
   如果理想高度超过 Max Height，均匀压缩所有区域
                    ↓
         【Step 4】Virtual Swatch 生成
   在每个层高增量处采样混合颜色 → 生成虚拟色板
   每个像素匹配到混合色最近的层 → 生成高度图
                    ↓
         【Step 5】Floyd-Steinberg 抖动
   对量化高度图做误差扩散 → 消除阶梯状色带
   块感知（block-aware），保护不同高度之间的边缘像素
                    ↓
         【Step 6】Greedy Meshing
   异步生成（每 8ms yield 给浏览器）
   边界顶点二分搜索过滤
   非索引三角形（每层颜色块有完整垂直侧壁）
                    ↓
         【Export】STL + 文字换色说明 / 3MF（Preview）
```

#### Beer-Lambert 光学混合公式

```
透射率 T = 10^(-厚度 / TD)

混合颜色计算（逐层叠加）:
  for each layer i (从底向上):
    透过率 = 10^(-layer_height / TD[i])
    出射光 = 入射光 × 透过率 + filament_color[i] × (1 - 透过率)
    入射光 = 出射光  (作为下一层的输入)
```

#### 优化器设计

| 算法 | 适用 | 原理 |
|------|------|------|
| 穷举搜索 | 1-4 色 | 评估所有 n! 种排列 |
| 模拟退火 | 5-8 色 | 概率性接受较差解，逃离局部最优 |
| 遗传算法 | 9+ 色 | 种群交叉变异 |
| 额外交换 | 任意 | 贪心插入最多 4 次重复换色（如白底上薄红=粉） |

优化评分权重: DeltaE 准确度 > 高度分布 > 层数 > 过渡浪费

#### TD 校准向导

1. 打印 3-5 个不同厚度的测试样品（如 0.3, 0.6, 1.0, 1.5, 2.0 mm）
2. 手机拍照/测光表测量亮度
3. 指数回归计算最优 TD 值
4. 输出置信度评分（高/中/低/极低）

#### 区域权重

- **Uniform** — 所有像素等权
- **Center** — 中心高斯衰减
- **Edge** — Sobel 边缘检测优先

---

### 2.3 Lumina-Layers — 开源物理校准多色系统（Python + Gradio + Trimesh）

**仓库:** github.com/MOVIBALE/Lumina-Layers | **版本:** v1.6.7 | **许可:** GPL v3.0

#### 核心创新：LUT 查表法代替理论计算

Kromacut/HueForge 依赖 TD 理论值计算 → 但实际打印受染料浓度、温度、附着力影响

Lumina-Layers 的做法：
```
打印物理校准板（全排列）→ 拍照提取 RGB → 生成 LUT(.npy) → KD-Tree 匹配
```

#### 校准板设计

| 颜色模式 | 总色数 | 使用的 filament |
|---------|--------|----------------|
| 4-Color RYBW | 1024 | 白、红、黄、蓝 |
| 4-Color CMYW | 1024 | 白、青、品红、黄 |
| 6-Color | 1296 | 白、青、品红、黄、柠绿、黑 |
| 8-Color | 2738 | 上述 + 2 种自定义 |
| BW | 32 灰度 | 黑、白 |

每种模式 = N 种 filament × 5 层深度的全排列

#### 三大模块

**模块 1: Calibration Generator（校准板生成器）**
- 生成校准板 STL：每个颜色块都是一个小长方体
- 人脸朝下优化（光滑表面）
- 实体背板（颜色一致性 + 结构强度）
- 防重叠几何（0.02mm 微缩，防止切片器线段宽度冲突）

**模块 2: Color Extractor（颜色提取器）**
- 拍照 → 透视变换 + 镜头畸变校正 → 网格对齐
- 人机协作：交互式探针工具手动修正颜色块读数
- 8 色模式：提取 Page 1 → 手动修正 → 提取 Page 2 → 合并 LUT

**模块 3: Image Converter（图像转换器）**
- KD-Tree 最近邻匹配：每个图像像素 → LUT 中最近的可打印颜色
- 在 3MF 中，每个颜色作为独立 object，命名为实际颜色名（如 "Cyan"）
- WebGL 实时 3D 预览
- 钥匙扣环生成器

#### 打印参数
- 颜色层：0.08mm
- 背板层：0.2mm
- 人脸朝下打印（光滑表面）

#### 与 Kromacut 的关键区别

| | Kromacut | Lumina-Layers |
|---|---|---|
| 颜色模型 | 理论计算（TD + Beer-Lambert） | 经验测量（校准板 + LUT） |
| 颜色排列 | 纵向堆叠（一层一色） | 横向排列（同一层多色） |
| 需要 AMS | 不需要 | 需要 |
| 颜色精度 | 受 TD 理论偏差影响 | 实测 RGB，物理准确 |
| 校准成本 | 低（测试条） | 高（全排列校准板） |
| 技术栈 | 浏览器 JS | Python + Gradio |

---

### 2.4 HueForge（参考基准）— 闭源商业软件

**核心技术要点（从 Wiki 提取）:**

- **Mesh Core** — 自定义亮度函数，将每个像素颜色映射到 Z 高度
- **一层一色** — 每层只用一种颜色（基本约束）
- **不需要 AMS** — M600 手动换料
- **输出** — STL + `_describe.txt`（非 3MF），用户在切片器中手动设置换色
- **TD 值** — 每种 filament 的透光距离（阻断 95% 光线所需的厚度，单位 mm）
- **颜色模式：**
  - Standard Luminance：标准灰度映射
  - Color Pop：灰度底层 + 颜色顶层
  - Color Aware：RGB 通道分 3 层
  - Color Match：手动拖拽定义颜色→层映射

---

## 三、Bambu Studio 3MF 换色格式（逆向分析）

3MF 文件本质是 ZIP 包：

```
project.3mf
├── 3D/
│   └── 3dmodel.model          ← geometry + basematerials (pid/pindex)
├── Metadata/
│   ├── project_settings.config ← JSON: filament_colour[], filament_type[], filament_ids[]
│   ├── model_settings.config   ← XML: <object> extruder="1" (1-based slot)
│   └── custom_gcode_per_layer.xml ← XML: 每层 tool_change 事件
├── [Content_Types].xml
└── _rels/.rels
```

### 关键文件详解

**project_settings.config（JSON）:**
```json
{
  "filament_colour": ["#FF0000", "#FFFFFF", "#0000FF"],
  "filament_type": ["PLA", "PLA", "PLA"],
  "filament_ids": ["GFB98A2CA6", "GFB98A2CA6", "GFB98A3A2F"]
}
```

**custom_gcode_per_layer.xml:**
```xml
<custom_gcodes_per_layer>
  <plate>
    <layer top_z="0.88" extruder="1" color="#000000" gcode="tool_change"/>
    <layer top_z="1.36" extruder="2" color="#FF0000" gcode="tool_change"/>
    <layer top_z="2.24" extruder="3" color="#FFFFFF" gcode="tool_change"/>
  </plate>
</custom_gcodes_per_layer>
```
- `extruder` 是 1-based 的 slot 号
- `top_z` 是换色发生的层高（mm）

**model_settings.config:**
```xml
<config>
  <object id="1">
    <metadata key="name" value="relief_model"/>
    <metadata key="extruder" value="1"/>
  </object>
</config>
```

### 生成兼容 3MF 的策略

有两个方案：

**方案 A: 标准 3MF basematerials（通用）**
```xml
<basematerials id="1">
  <base name="Black PLA" displaycolor="#000000"/>
  <base name="Red PLA" displaycolor="#FF0000"/>
</basematerials>
<object id="2" pid="1" pindex="0">...</object>
```
优点：标准格式，跨切片器兼容
缺点：切片器对 pindex 映射 extruder 的行为不一致

**方案 B: Bambu/Orca 私有 metadata（推荐）**
直接写入 `project_settings.config` + `custom_gcode_per_layer.xml`
优点：Bambu Studio 直接识别，无需用户手动设置换色
缺点：绑定 Bambu/Orca 生态

---

## 四、与我们现有工作流的差距分析

### 我们已有的能力（image-to-relief.py）

```
✅ 图像加载 & 预处理（resize + 亮度提取）
✅ 高度图生成（高斯模糊 base/detail 分离）
✅ Watertight mesh 构建（前面+背面+侧壁）
✅ K-means 颜色量化（--colors N）
✅ Vertex-colored OBJ 导出
✅ STL 导出（decimation 后）
✅ 浮雕 & 透光浮雕两种模式
```

### 缺失的能力

```
❌ 颜色分层逻辑（每个颜色对应一个 Z 高度范围）
❌ Beer-Lambert 叠色物理模拟
❌ TD 值管理与校准
❌ 逐层换色方案计算（哪个 Z 高度换到哪个颜色）
❌ 3MF 导出（含 filament 配置 + 换色指令）
❌ 最优 filament 排序优化
❌ 抖动处理（消除阶梯色带）
❌ 区域权重控制
```

---

## 五、执行方案

### 总体架构

```
新模块: scripts/multi-color-layers.py
  ├── td_calibration.py     — TD 值校准工具
  ├── layer_optimizer.py    — 叠色层序优化器
  ├── color_blending.py     — Beer-Lambert 物理模拟
  ├── height_mapper.py      — 颜色→高度映射（含抖动）
  ├── mesh_builder.py       — 多层 mesh 构建
  └── export_3mf.py         — Bambu 兼容 3MF 导出

改造: scripts/image-to-relief.py
  └── 新增 --multi-color 模式，调用 multi-color-layers 模块
```

### Phase 1: 核心叠色引擎（预计 3-5 天）

#### Step 1.1: TD 校准模块 `td_calibration.py`

```
输入: N 种 filament 在 M 个厚度下的实测亮度值
输出: 每种 filament 的 TD 值 + 置信度

算法:
  对每个 filament:
    收集 (厚度_i, 亮度_i) 样本
    拟合: 亮度 = exp(-厚度 / TD)  → 线性回归 log(亮度) vs 厚度
    输出: TD = -1/slope, R² 置信度
```

简化版：先支持手动输入已知 TD 值（Bambu PLA Basic 系列有社区数据），校准工具后续迭代。

#### Step 1.2: Beer-Lambert 叠色模拟 `color_blending.py`

```python
def beer_lambert_blend(layers, layer_height=0.08):
    """
    layers: [(color_rgb, thickness_mm), ...] 从底向上
    返回: 混合后的 RGB 颜色
    """
    # 从底部开始，光线穿过每层
    transmitted = np.array([1.0, 1.0, 1.0])  # 入射白光
    for color_rgb, thickness in layers:
        transmission = 10 ** (-thickness / td_for_color(color_rgb))
        transmitted = transmitted * transmission + color_rgb * (1 - transmission)
    return transmitted
```

#### Step 1.3: 最优层序优化 `layer_optimizer.py`

```
输入: N 种颜色 + TD 值, 目标图片, 最大高度
输出: 最优 filament 排列 + 每种颜色的层数

简化版（N ≤ 4）:
  穷举所有 n! 种排列
  对每种排列:
    计算 transition zone（DeltaE < 2.3 收敛判断）
    计算高度占用
    计算与目标图片的 DeltaE 误差
  选择误差最小的排列

高级版（N ≥ 5）:
  模拟退火搜索
```

#### Step 1.4: 颜色→高度映射 `height_mapper.py`

```
输入: 最优层序, 目标图片
输出: 高度图 (H×W float array, mm)

对每个像素:
  在 virtual swatch 中找最近似的混合颜色
  映射到对应 Z 高度
应用 Floyd-Steinberg 抖动消除阶梯
```

#### Step 1.5: 集成到 image-to-relief.py

新增参数:
```bash
python scripts/image-to-relief.py photo.jpg \
  --multi-color \
  --filaments '[
    {"color":"#000000","td":0.6,"name":"Black PLA"},
    {"color":"#FF0000","td":3.5,"name":"Red PLA"},
    {"color":"#FFFFFF","td":5.0,"name":"White PLA"}
  ]' \
  --layer-height 0.08 \
  --max-thickness 3.0
```

### Phase 2: 3MF 导出（预计 2-3 天）

#### Step 2.1: Bambu 兼容 3MF 生成 `export_3mf.py`

```
输入: STL mesh + 换色方案 [(z_mm, filament_index), ...]
输出: .3mf 文件

流程:
  1. 构建 3MF ZIP 包结构
  2. 生成 3D/3dmodel.model（含 basematerials）
  3. 生成 Metadata/project_settings.config（filament 配置）
  4. 生成 Metadata/custom_gcode_per_layer.xml（换色事件）
  5. 打包为 .3mf
```

#### Step 2.2: 换色方案格式

```json
{
  "filaments": [
    {"index": 0, "color": "#000000", "type": "PLA", "name": "Bambu Basic Black"},
    {"index": 1, "color": "#FF0000", "type": "PLA", "name": "Bambu Basic Red"},
    {"index": 2, "color": "#FFFFFF", "type": "PLA", "name": "Bambu Basic White"}
  ],
  "layer_height": 0.08,
  "first_layer_height": 0.16,
  "swaps": [
    {"z_mm": 0.0,  "filament": 0},
    {"z_mm": 0.88, "filament": 1},
    {"z_mm": 1.84, "filament": 2}
  ],
  "total_thickness_mm": 2.24
}
```

### Phase 3: 校准 & 测试（预计 2-3 天）

#### Step 3.1: 已知 TD 值库

先收集社区已有数据，建立内置 TD 库：
```python
KNOWN_TD = {
    "Bambu PLA Basic": {
        "Black": 0.6,
        "Blue Gray": 3.1,
        "Red": 3.5,
        "Yellow": 5.5,
        "Jade White": 5.0,
        "White": 4.4,
    },
    # ...更多品牌
}
```

#### Step 3.2: 测试用例

1. 4 色照片浮雕（黑+红+黄+白）
2. 3 色透光浮雕（黑+灰+白）
3. 2 色简约风格（黑+白）
4. 与单色 STL 对比打印效果

### Phase 4: Web UI 集成（预计 1-2 天）

在现有 `web/` 前端中新增 "多色打印" 节点类型：
- 上传图片 → 选择颜色/Filament → 预览 → 下载 3MF

---

## 六、关键设计决策

### 决策 1: 叠色路线选择

**选纵向叠色，不选横向拼色。**

理由：
- 纵向叠色不需要 AMS，单喷头手动换料即可，适配面更广
- 我们的浮雕/透光浮雕场景天然适合纵向叠色（Z 方向有高度变化）
- 横向拼色（Lumina-Layers 方案）需要 AMS 频繁换料，废料多

### 决策 2: TD 理论计算 vs LUT 实测

**先用 TD 理论计算快速上线，后续加 LUT 校准增强精度。**

理由：
- TD 理论计算（Kromacut 方案）开发快，社区有大量已知 TD 值
- LUT 实测（Lumina-Layers 方案）精度更高但校准成本大（用户需打印+拍照）
- 可以先上线理论计算版，用户反馈精度不够时再加 LUT 校准

### 决策 3: 3MF 导出策略

**生成 Bambu/Orca 兼容的 3MF（含 metadata），同时提供纯 STL + 换色说明文本作为通用方案。**

理由：
- Bambu Studio 是我们的目标打印机平台
- 通用 STL + 文本方案确保其他切片器也能用
- 3MF 格式有详细逆向文档可以参考

### 决策 4: 与现有管线的关系

**新增为 image-to-relief.py 的 `--multi-color` 模式，不破坏现有单色功能。**

```
现有: image → height map (luminance) → single mesh → STL
新增: image → color quantize → TD blend → per-color height → layered mesh → 3MF+STL
```

---

## 七、文件结构规划

```
scripts/
├── image-to-relief.py          # 改造：新增 --multi-color 模式
├── multi_color/
│   ├── __init__.py
│   ├── td_database.py          # 已知 TD 值库
│   ├── td_calibration.py       # TD 校准工具
│   ├── color_blending.py       # Beer-Lambert 叠色模拟
│   ├── layer_optimizer.py      # 最优层序优化（穷举/模拟退火）
│   ├── height_mapper.py        # 颜色→高度映射 + Floyd-Steinberg 抖动
│   ├── mesh_builder.py         # 多层 mesh 构建
│   └── export_3mf.py           # Bambu 兼容 3MF 导出
└── calibrate-td.py             # 独立 TD 校准脚本

output/
└── multi-color/                # 多色输出目录
    ├── *.stl
    ├── *.3mf
    └── *_swaps.txt
```

---

## 八、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| TD 理论值与实际偏差大 | 颜色不准确 | 内置已知品牌 TD 库 + 后续加 LUT 校准 |
| 3MF 格式细节与 Bambu 版本不兼容 | 3MF 打不开 | 先做 STL+文本方案保底，多版本测试 |
| 0.08mm 层高打印时间过长 | 用户体验差 | 基础层用 0.16mm，hybrid 层高策略 |
| 4 色限制（AMS） | 颜色不够用 | 手动换料模式突破限制，动态颜色数 |
| Floyd-Steinberg 抖动引入噪点 | 表面不光滑 | 加可调抖动强度参数 + 后处理平滑选项 |

---

## 九、参考资源

- Kromacut: https://github.com/vycdev/Kromacut
- Lumina-Layers: https://github.com/MOVIBALE/Lumina-Layers
- HueForge Wiki: https://hueforge.wiki/
- hicolors-3d: https://hicolors3d.com/
- 3MF 格式逆向: https://printago.io/blog/3mf-file-format
- 3MF 规范: https://3mf.io/spec/

---

## 十、实施清单

### Phase 1: 核心叠色引擎

| # | 文件 | 功能 | 状态 |
|---|------|------|------|
| 1.1 | `scripts/multi_color/__init__.py` | 包初始化 + 公共 API | ✅ |
| 1.2 | `scripts/multi_color/td_database.py` | 已知 filament TD 值库 (~120 entries) | ✅ |
| 1.3 | `scripts/multi_color/color_blending.py` | Beer-Lambert 光学叠色模拟 + CIEDE2000 | ✅ |
| 1.4 | `scripts/multi_color/layer_optimizer.py` | 最优 filament 排列搜索 (exhaustive + SA) | ✅ |
| 1.5 | `scripts/multi_color/height_mapper.py` | 颜色→高度映射 + Floyd-Steinberg 抖动 | ✅ |
| 1.6 | `scripts/multi_color/mesh_builder.py` | 多层 mesh 构建 | ✅ |
| 1.7 | `scripts/multi_color/export_3mf.py` | Bambu 兼容 3MF 导出 | ✅ |

### Phase 2: 集成

| # | 文件 | 功能 | 状态 |
|---|------|------|------|
| 2.1 | `scripts/image-to-relief.py` | 新增 `--multi-color` 模式 | ✅ |
| 2.2 | `scripts/calibrate-td.py` | 独立 TD 校准脚本 | ✅ |

### Phase 3: 测试验证

| # | 内容 | 状态 |
|---|------|------|
| 3.1 | 单元测试：Beer-Lambert 混合计算 | ✅ |
| 3.2 | 集成测试：端到端 image → 3MF | ✅ |
| 3.3 | 3MF 兼容性验证（Bambu Studio 打开） | ✅ |

### 完成标准

- [x] `image-to-relief.py --multi-color` 可从图片生成多色 3MF
- [x] 3MF 文件可在 Bambu Studio 中正常打开，filament 配置正确
- [x] 换色指令自动嵌入，无需用户手动设置
- [x] 输出 STL + 换色文本作为通用方案备份
- [x] 不破坏现有单色 `--lithophane` / `--colors` 功能

### 测试结果: 46/46 PASSED (2026-05-22)

详见 [Multi-Color Pipeline — Functional Test Report](multi-color-test-report-20260522.md)
