# HueForge 生态调研 & 对比分析

> 2026-05-24 | 分析 HueForge 示例文件 + 调研同类工具平台，评估集成/借鉴可行性

---

## 一、HueForge 示例文件逆向分析

### 样本信息

- **文件:** `漫画-你将来会发大财_Front_83x90.3mf` (4.3 MB)
- **来源:** MakerWorld 用户分享，使用 HueForge 制作
- **描述:** 《哆啦A梦》漫画风格双色打印，83×90mm
- **打印机:** Bambu Lab A1 mini, 0.4mm nozzle
- **层高:** 0.08mm (超细层高，关键参数)

### 3MF 内部结构

```
漫画-你将来会发大财_Front_83x90.3mf
├── [Content_Types].xml
├── _rels/.rels
├── 3D/
│   ├── 3dmodel.model              # 3MF build 定义
│   ├── Objects/object_4.model     # 30.9 MB XML 网格 (377,784 面)
│   └── _rels/3dmodel.model.rels
├── Metadata/
│   ├── model_settings.config      # 对象/挤出机/底板配置
│   ├── project_settings.config    # 完整 Bambu Studio 切片配置 (53KB)
│   ├── custom_gcode_per_layer.xml # 换色层高指令 ⭐核心
│   ├── plate_1.png                # 底板预览缩略图
│   ├── slice_info.config
│   └── cut_information.xml
└── Auxiliaries/
    ├── Model Pictures/             # WebP 预览图
    └── .thumbnails/                # 多级缩略图
```

### 关键发现

**1. 换色机制 — 全局 Z 高度换料**

`custom_gcode_per_layer.xml` 内容:
```xml
<custom_gcodes_per_layer>
  <plate>
    <plate_info id="1"/>
    <layer top_z="1.3600000143051147" type="2" extruder="4"
           color="#FFFFFF" extra="" gcode="tool_change"/>
    <mode value="MultiAsSingle"/>
  </plate>
</custom_gcodes_per_layer>
```

- **仅 1 次换色事件**：在 Z=1.36mm 处从挤出机3（黑色 #000000）切换到挤出机4（白色 #FFFFFF）
- **模式 "MultiAsSingle"**：单个模型使用多个虚拟挤出机，但打印时视为单一材料流程
- **核心原理**：所有像素共用一个高度场 STL，换色发生在全局 Z 层高，不同区域的"可见颜色"由该位置被多少层不同颜色覆盖决定

**2. 模型几何 — 高度场编码颜色信息**

```
网格: 377,784 面 (极高细节，83×90mm 打印件)
对象挤出机: 3 (初始使用黑色)
Z 偏移: 1.16mm (source_offset_z)
```

**3. 配置的特征**

| 参数 | 值 | 含义 |
|------|-----|------|
| 层高 | 0.08mm | 极致细节，与 TD 物理模型匹配 |
| 初始层高 | 0.16mm | 首层略厚以保证附着力 |
| 壁循环 | 2 | 薄壁结构 |
| 顶部/底部层 | 9/7 | 足够的覆盖层以遮挡底层颜色 |
| 稀疏填充密度 | 10% | 仅边框填充，大部分为实心 |
| 定义6种耗材 | Silver/Green/Black/White/LightWood/LightPink | 但实际只用 Black+White |

**关键洞察：HueForge 的"多色效果"来自几何高度场 + 全局换色，而非逐像素颜色分配或分区打印。这是一种"光学欺骗"——利用 PLA 的半透明特性实现颜色混合。**

---

## 二、HueForge 核心设计原理

### 2.1 "Filament Painting" (耗材绘画)

HueForge 的本质是一个**光学模拟器**，而非网格生成器。它将 2D 图像转换为 FDM 打印机可执行的层叠方案。

```
        ↑ 环境光 / 背光
┌───────────────────┐  ← Z=2.0mm 顶部 (白色 PLA, TD=4.4)
│  白色 (薄层)       │     光穿透浅层 → 看到下面颜色
├───────────────────┤  ← Z=1.36mm 换色边界
│  黑色 (厚层)       │     光被吸收 → 遮挡背景
├───────────────────┤
│  底板 (基础层)     │     Z=0
└───────────────────┘
```

**光学原理:**
- 明亮区域 = 白色薄层覆盖 → 光线穿透白色层反射回来 → 看起来白/亮
- 暗色区域 = 白色厚层 + 底部黑色 → 光线被黑色吸收 → 看起来黑/暗
- 中间色调 → 不同厚度的白色层产生不同灰阶

### 2.2 Transmission Distance (TD) — 核心物理参数

```
TD = 光线穿透耗材后衰减至 ~10% 的厚度 (mm)
```

**TD 的物理意义:**
```
transmission = 10^(-thickness / TD)
```

| TD 范围 | 类型 | 代表耗材 | 用途 |
|---------|------|---------|------|
| 0.4–1.0 | 高不透明 | 黑色 PLA Matte (0.4) | 阴影、轮廓、底层遮挡 |
| 1.0–2.5 | 中等 | 灰色 PLA (1.5), 蓝色 PLA (2.8) | 中间色调过渡 |
| 2.5–5.0 | 半透明 | 白色 PLA Basic (4.4), 黄色 (5.5) | 亮部、高光、颜色混合 |
| 5.0–12.0 | 高透明 | Natural PLA (6.0), 透明 PETG (12.0) | 光扩散、特殊效果 |

**TD 是 filament painting 的命门——算法再精准，TD 值不准确就一切白费。**

### 2.3 工作流程

```
原始图片 → 图像预处理 → 颜色映射 (Color Core)
    ↓
 拖动颜色滑块到 Luminance 范围
 (底层→顶层：黑色→灰色→白色)
    ↓
 调整滑块高度 → GPU 实时预览 (模拟透光混合)
    ↓
 调整 Mesh Core (几何参数：基础厚度、最大深度、平滑、尖峰去除)
    ↓
 导出: STL 网格 + _describe.txt (换层高度清单)
    ↓
 切片软件: 导入 STL → 设置 0.08mm 层高 → 配置 filament swap 暂停点
    ↓
 打印: AMS/MMU 自动换料 (或手动暂停换料)
```

### 2.4 HueForge 的技术边界

**支持:**
- 平面 lithophane / front-lit relief
- 2-8 种耗材颜色
- 所有 FDM 打印机 (有/无 AMS 均可)
- Stained Glass 技术 (多部件分色组装)

**不支持:**
- 曲面或非平面 lithophane
- 自动一键转换 (需要艺术判断)
- CMYK 全彩 (受限于耗材 TD 色域)
- 非 Windows 平台 (Mac/Linux 开发中)

---

## 三、同类工具平台对比

### 3.1 横评总览

| 工具 | 许可 | 平台 | TD物理 | 自动优化 | 导出格式 | 易用性 |
|------|------|------|--------|---------|---------|--------|
| **HueForge** | 商业 $24-48 | Windows 桌面 | ✅ GPU | ❌ 手动 | STL+txt | ⭐⭐⭐⭐ |
| **Kromacut** | 开源(商用OK) | Web 浏览器 | ✅ Beer-Lambert | ✅ SA+遗传 | STL+3MF | ⭐⭐⭐⭐ |
| **Lumina-Layers** | GPL v3 | Python+WebGL | ✅ 校准LUT | ✅ KD-Tree | 3MF | ⭐⭐⭐ |
| **AutoForge** | CC BY-NC-SA | Python CLI | ✅ 学习优化 | ✅ Gumbel | STL | ⭐⭐⭐ |
| **PrintPal** | 免费 | Web 浏览器 | ❌ 基础 | ❌ 手动 | OBJ | ⭐⭐⭐⭐⭐ |
| **Filapaint** | 免费 | Web 浏览器 | ❌ 基础 | ❌ 手动 | STL | ⭐⭐⭐⭐⭐ |
| **PIXEstL** | 开源 | Windows 应用 | ✅ 自定义 | ❌ 手动 | STL | ⭐⭐⭐ |
| **FullSpectrum** | 开源 | 桌面切片器 | ✅ 继承HF | ❌ | G-code | ⭐⭐ |
| **我们** | 私有 | Python CLI+Web | ✅ Beer-Lambert | ✅ SA+穷举 | STL+3MF | ⭐⭐⭐ |

### 3.2 各工具详细分析

#### Kromacut (vycdev) ⭐ 最值得借鉴

**仓库:** github.com/vycdev/Kromacut  
**技术栈:** React + TypeScript + Three.js (全浏览器端运行)

**核心算法 (与我们高度一致):**
1. 耗材按亮度排序 (暗→亮 = 底→顶)
2. 模拟退火/遗传算法搜索最优排列
3. 过渡区计算：逐层模拟 Beer-Lambert，直到 ΔE < 2.3 或 opacity > 85%
4. 底层耗材分配 TD×1.3 基础区 (~95%不透明)
5. Block-aware Floyd-Steinberg dithering

**亮点功能:**
- **区域权重:** 可选择 center/edge/uniform 三种采样策略，影响优化方向
- **Auto-paint + Manual 双模式:** 自动化处理日常图片，手动精细控制复杂图片
- **校准向导:** 引导式 TD 测量流程
- **层叠预览滑块:** 逐层可视化换色过程

**可借鉴点:**
- 遗传算法优化器 (我们目前只实现了 SA + 穷举)
- Web 端 Three.js 实时预览体验
- 引导式校准流程设计

#### Lumina-Layers (MOVIBALE)

**仓库:** github.com/MOVIBALE/Lumina-Layers  
**技术栈:** Python + WebGL 预览

**差异化特性:**
- **物理校准 + CV 分析:** 打印测试色板 → 拍照 → 计算机视觉提取 RGB → 建立 LUT
- **KD-Tree 颜色匹配:** O(log N) 查找，比我们的 O(N) swatch 匹配更快
- **Manga Mode:** 针对黑白线稿的特殊处理 (边缘检测 + 区域分割)
- **Keychain 生成器:** 内置挂环自动生成

**可借鉴点:**
- **CV 辅助校准:** 这是 TD 准确性的终极方案——不用人工测量亮度，拍照自动分析
- **Manga Mode 思路:** 线稿类型图片需要不同处理策略
- **KD-Tree:** 加速大调色板颜色匹配

#### AutoForge (hvoss-techfak)

**仓库:** github.com/hvoss-techfak/AutoForge  
**技术栈:** PyTorch

**差异化特性:**
- **Gumbel Softmax 优化:** 用可微分松弛逼近离散材料选择，端到端学习优化
- **FlatForge Mode:** 每种颜色生成独立 STL，面朝下打印后组装 → 树脂级光滑表面
- **HueForge 兼容导出:** 可输出 HF 项目文件
- **Neon/Inverted 模式:** 特殊视觉效果

**可借鉴点:**
- **FlatForge 概念:** 分离式打印 + 组装 = 更纯净的颜色分离，无层间混合
- **学习优化思路:** 适合复杂调色板场景

#### FullSpectrum (OrcaSlicer Fork)

**思路:** 将 filament painting 集成到切片器内部，省去"外部工具生成 → 导入切片器"环节。

**限制:** 目前依赖换刀打印机 (Snapmaker U1, Prusa XL)，多材料单元支持有限。

### 3.3 技术路线分类

```
Filament Painting (纵向叠色)
├── 全局换色 (主流路线)
│   ├── HueForge: 手动滑块 + GPU 预览
│   ├── Kromacut: 自动优化 + 手动微调
│   ├── AutoForge: 神经网络自动优化
│   ├── Lumina-Layers: CV 校准 + KD-Tree 匹配
│   └── 我们: Beer-Lambert + SA + Floyd-Steinberg
│
└── 切片器集成 (新兴路线)
    └── FullSpectrum: 切片区内部混合

分区打印 (横向拼色)
├── Lumina-Layers: 多对象 3MF
└── FlatForge: 分离 STL 面朝下打印

全彩方案 (需要专用硬件)
├── CMYK 耗材 + 工具更换器
└── 多喷头独立颜色通道
```

---

## 四、与我们现有实现的对比

### 4.1 对齐点 (我们已具备)

| 能力 | 我们的实现 | 对应 |
|------|----------|------|
| Beer-Lambert 光学模拟 | `color_blending.py:beer_lambert_blend()` | HueForge / Kromacut |
| TD 数据库 | `td_database.py` — 5品牌 100+ 条目 | HueForge 耗材库 |
| 叠层优化 | `layer_optimizer.py` — 穷举 + SA | Kromacut 优化器 |
| 高度映射 | `height_mapper.py` — swatch 匹配 + Floyd-Steinberg | HueForge Mesh Core |
| 3MF 导出 | `export_3mf.py` — Bambu/Orca 兼容 | Lumina-Layers |
| TD 校准 | `calibrate-td.py` — 阶梯试块 + 线性回归 | HueForge FilaScope |
| Web UI 集成 | `web/` — FastAPI + SSE + 任务管理 | — (独有优势) |

### 4.2 差距与不足

| 差距 | 现状 | 影响 |
|------|------|------|
| **无实时预览** | 只有静态 height map PNG | 用户无法在导出前看到预期颜色效果 |
| **无 GPU 加速** | 全 CPU NumPy 计算 | 大图处理慢，无法交互式调整 |
| **TD 校准靠人工** | 需手动测量亮度 → JSON 输入 | 校准门槛高，普通用户做不到 |
| **优化器仅 SA** | 无遗传算法备选 | 5+ 色的复杂调色板可能陷入局部最优 |
| **色域限制** | 2-4 色最佳，更多不稳定 | 不支持 6-8 色复杂场景 |
| **无特殊模式** | 仅 relief/lithophane | 无 Manga/Neon/Stained Glass 等风格化模式 |
| **无 FlatForge** | 仅纵向叠色 | 无法生成光滑面朝下打印件 |

### 4.3 架构差异

```
HueForge 模型:
   颜色滑块 (Color Core) ←→ 网格参数 (Mesh Core)
        ↓                        ↓
   GPU 实时预览 (核心价值)    STL 高度场
        ↓                        ↓
   用户手动调参 ←── 双向反馈 ──→ 导出

我们的模型:
   图片 + 参数 → 一次性计算 → 导出结果
        ↓
   无交互预览 (仅事后看 PNG)
```

**核心差异：HueForge 是交互设计工具，我们是批处理管道。** 两者在算法层面相似度很高，但产品形态完全不同。

---

## 五、集成与借鉴建议

### 5.1 短期 (可直接优化现有代码)

#### 1. 添加遗传算法优化器

从 Kromacut 借鉴，在现有 SA 基础上增加 GA 备选路径。5+ 色场景下 SA 可能收敛到局部最优，GA 的种群搜索有助于跳出。

**改动范围:** `layer_optimizer.py`，新增 `_genetic_algorithm()` 函数  
**参考:** Kromacut `Kromacut_public/src/lib/Optimizer.ts`

#### 2. KD-Tree 加速颜色匹配

当前 `height_mapper.py` 中逐 swatch 暴力搜索 O(N×M)。使用 KD-Tree 将查找降至 O(N log M)，对 6-8 色场景有显著提升。

**改动范围:** `height_mapper.py` 的 `map_colors_to_height()`
**参考:** Lumina-Layers 的 KD-Tree 实现

#### 3. 改进 dithering 为完整 Block-Aware

当前 dithering 已支持 filament 边界感知，但可进一步完善：
- 颜色感知误差扩散 (而非仅在高度上扩散)
- 图案化 dither (蓝噪声/有序 dither 可选)

**改动范围:** `height_mapper.py` 的 `_floyd_steinberg_height()`

#### 4. 完善 TD 校准工具

当前 `calibrate-td.py` 需要手动测量亮度。可增加：
- **CV 辅助模式:** 拍照 → 自动检测阶梯区域 → 提取亮度 (类似 Lumina-Layers)
- **校准报告:** 生成可视化回归曲线图
- **自动入库:** 校准结果自动写入 TD 数据库

**改动范围:** `calibrate-td.py` + 新增 `calibrate_td_cv.py`

### 5.2 中期 (需要架构调整)

#### 5. Web 实时预览

这是 HueForge 的核心价值所在，也是我们 Web UI 最大的缺失。

**技术方案:**
- **方案A (推荐):** Three.js + Web Worker
  - Worker 线程运行 Beer-Lambert 模拟 (CPU)
  - 主线程 Three.js 渲染高度场 + 颜色贴图
  - 不依赖 GPU compute shader，兼容性好

- **方案B:** WebGPU compute shader
  - 直接在 GPU 上并行模拟每个像素的光学混合
  - 可实现 60fps 实时交互预览
  - 浏览器兼容性有限 (Chrome 113+, Edge 113+)

**参考:** Kromacut 的 WebGL + Canvas 预览架构

#### 6. 交互式调色面板

类似 HueForge 的颜色滑块 UI：
- 底部→顶部耗材排列可视化
- 拖动滑块调整每种颜色的 Z 范围
- 实时反馈预览变化

**改动范围:** `web/static/` 新增 `preview.js` 模块

#### 7. Manga/LineArt 模式

针对线稿/漫画的特殊处理：
- Sobel 边缘检测 → 边缘区域用暗色薄层
- 大面积白色区域用白色厚层
- 灰度反转选项

**改动范围:** 新增 `scripts/multi_color/manga_mode.py`

### 5.3 长期 (战略方向)

#### 8. FlatForge 打印模式

借鉴 AutoForge 的思路：
- 每种颜色生成独立薄片 STL (0.6mm 左右)
- 面朝下打印 → 打印板纹理 = 光滑表面
- 用户手动粘合组装

优势：颜色完全不混合，适合高对比度图案。劣势：需要手动组装。

#### 9. 切片器插件

长远来看，可将高度场 → 换色指令的转换集成到 OrcaSlicer/BambuStudio 后处理脚本中，减少用户手动配置换色点的步骤。

**参考:** FullSpectrum 的切片器集成方案

#### 10. 色域分析与可行性预判

并非所有图片都适合 filament painting。可增加：
- 预处理阶段计算图片色域 vs filament 可达色域
- 给出"适合度"评分
- 自动建议最佳耗材组合

**参考:** HueForge 社区经验法则

---

## 六、竞争定位分析

```
                复杂性 →
            简单              中等              复杂
易用性 ↑  ┌──────────┐  ┌──────────┐  ┌──────────┐
         │ PrintPal │  │ HueForge │  │ FullSpec │
         │ Filapaint│  │          │  │          │
         ├──────────┤  ├──────────┤  ├──────────┤
         │          │  │ Kromacut │  │ Lumina   │
         │  我们     │  │          │  │ AutoForge│
         │ (Web UI) │  │          │  │          │
         └──────────┘  └──────────┘  └──────────┘
```

**我们的独特优势:**
1. **集成化 Web 平台** — 唯一同时提供 Web UI + 任务管理 + 异步执行 + 3D 生成 + 浮雕的工具
2. **多引擎支持** — TripoSR/Hunyuan3D + Relief + Repair 一体化
3. **Python CLI 灵活** — 可脚本化批量处理

**我们的主要劣势:**
1. **无实时预览** — 这是 HueForge/Kromacut 的核心竞争壁垒
2. **TD 校准不完善** — 依赖手工测量
3. **优化器不够成熟** — 缺少 GA 和多策略 fallback

---

## 七、结论与优先级建议

### 核心判断

**我们的 multi-color 模块在算法层面与 HueForge/Kromacut 处于同一技术路线，且核心计算逻辑已经基本正确。** 主要差距不在算法，而在**用户体验闭环**——特别是实时预览和交互式调整。

HueForge 的本质不是算法创新（Beer-Lambert 是 1852 年的物理学），而是将算法做成实时可交互的工具，让用户能"看见"打印结果再决定参数。

### 推荐优先级

| 优先级 | 事项 | 工作量 | 影响 |
|--------|------|--------|------|
| P0 | CV 辅助 TD 校准 | 2-3天 | 提升基础数据准确性 |
| P0 | 遗传算法优化器 | 1-2天 | 提升 5+ 色场景质量 |
| P1 | Web 实时预览 (Three.js) | 5-7天 | 弥补最大产品差距 |
| P1 | KD-Tree 颜色匹配 | 0.5天 | 性能优化 |
| P2 | Manga/LineArt 模式 | 2天 | 新使用场景 |
| P2 | FlatForge 模式 | 3天 | 新打印策略 |
| P3 | 色域分析 & 可行性预判 | 2天 | 减少失败打印 |
| P3 | 切片器插件/后处理 | 未知 | 简化用户操作 |

### 不建议的方向

- **强行实现 GPU 实时预览 (WebGPU):** 当前浏览器兼容性有限，投入大收益小。Web Worker + Three.js 方案更适合当前阶段。
- **试图超越 HueForge 的 GUI 体验:** HueForge 有多年积累的交互设计，直接对标不现实。应该走差异化路线（Web 平台 + 集成化流水线）。
- **CMYK 全彩方案:** 需要专用硬件（工具更换器/多喷头），不在当前 Bambu Lab AMS 四色范围内。

---

## 参考资料

- [HueForge 官方](https://www.thehueforge.com/)
- [Kromacut GitHub](https://github.com/vycdev/Kromacut)
- [Lumina-Layers GitHub](https://github.com/MOVIBALE/Lumina-Layers)
- [AutoForge GitHub](https://github.com/hvoss-techfak/AutoForge)
- [FullSpectrum (Hackaday)](https://hackaday.com/2026/03/17/fullspectrum-is-like-hueforge-for-3d-models-but-bring-your-toolchanger/)
- [HueForge 工作原理 (Polymaker Wiki)](https://wiki.polymaker.com/the-basics/applications/hueforge-painting)
- [What Exactly IS HueForge? (开发者博客)](https://devlog.thehueforge.com/p/what-exact-is-hueforge)
- [Tom's Hardware: How to Paint with a 3D Printer Using HueForge](https://www.tomshardware.com/how-to/hugeforge-paint-with-3d-printer)
