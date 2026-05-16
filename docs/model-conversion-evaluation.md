# 3D 模型转换方案评估报告

> 评估日期：2026-05-14
> 背景：TripoSR / Hunyuan3D 生成的 GLB/OBJ 格式模型无法直接用于 3D 打印，需要转换为 STL（或 3MF）格式。

---

## 一、问题分析

### 1.1 当前流程

```
[图片输入] → TripoSR/Hunyuan → GLB/OBJ → ??? → 打印机(STL/3MF)
```

现有的 `mesh-repair.py` 脚本已经通过 trimesh 实现了 GLB→STL 的隐式转换（加载 GLB，修复后导出 STL），但存在以下问题：

1. **修复节点不是必选**：用户在工作流编辑器中可能不连接 repair 节点，导致输出为原始 GLB/OBJ
2. **无独立格式转换节点**：不同于图片的 `image_convert` 节点，3D 模型没有专属的格式转换节点
3. **转换可能失败**：非流形几何体、超大面数、材质丢失等情况缺乏处理
4. **缺少模型预处理链**：简化 → 修复 → 缩放 → 格式转换 这一常见管线没有便捷的模板

### 1.2 打印机兼容性

| 打印机/切片软件 | 支持格式 | 备注 |
|----------------|----------|------|
| 主流 FDM 打印机 (Ender, Prusa, Bambu) | STL, 3MF | STL 最通用 |
| OrcaSlicer / PrusaSlicer / Cura | STL, 3MF, OBJ | 3MF 支持逐渐普及 |
| 光固化打印机 | STL | 仅 STL |
| 工业级打印机 | STL, 3MF, AMF | 因厂商而异 |

**STL 是最大公约数**，几乎所有打印机和切片软件都支持。

---

## 二、候选方案

### 方案 A：Trimesh（Python 原生）

**描述**：使用项目中已有的 `trimesh` 库，通过 `trimesh.load()` → 可选处理 → `.export()` 完成格式转换。

```python
import trimesh
mesh = trimesh.load("input.glb")
mesh.export("output.stl")
```

**API 示例（完整处理管线）**：
```python
def convert_model(input_path, output_path, simplify=0, repair=True, scale=None):
    mesh = trimesh.load(input_path, force='mesh')
    if simplify > 0:
        mesh = mesh.simplify_quadric_decimation(simplify)
    if repair:
        trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_normals(mesh)
    if scale:
        mesh.apply_scale(scale)
    mesh.export(output_path)
```

| 维度 | 评价 |
|------|------|
| **功能完整性** | 支持 40+ 格式读写（GLB/GLTF/OBJ/STL/PLY/3MF/OFF...），基础修复、简化、缩放 |
| **安装难度** | `pip install trimesh`，纯 Python，已集成 |
| **性能** | 依赖 numpy/scipy，10 万面模型转换 <1s，百万面 <5s |
| **Windows 兼容** | 原生支持，无额外依赖 |
| **维护活跃度** | GitHub 3k+ stars，持续更新 |
| **局限性** | 高级修复（如 PyMeshFix）需额外安装；纹理/材质在 STL 导出时丢失 |

### 方案 B：PyMeshLab（MeshLab 的 Python 封装）

**描述**：MeshLab 是学术界和工业界广泛使用的网格处理工具，PyMeshLab 提供 Python API。

```python
import pymeshlab
ms = pymeshlab.MeshSet()
ms.load_new_mesh("input.glb")
ms.apply_filter('meshing_decimation_quadric_edge_collapse', targetfacenum=50000)
ms.save_current_mesh("output.stl")
```

| 维度 | 评价 |
|------|------|
| **功能完整性** | 极强 — 数百种滤镜（重网格化、孔洞填充、平滑、UV 展开、布尔运算） |
| **安装难度** | `pip install pymeshlab` 自动下载 Meshlab 核心（约 50MB） |
| **性能** | 原生 C++ 底层，处理百万面模型高效 |
| **Windows 兼容** | 良好，pip 安装即可 |
| **维护活跃度** | 中等，MeshLab 历史悠久但更新缓慢 |
| **局限性** | 依赖较重（~50MB）；API 文档不够完善；滤镜参数学习曲线陡峭 |

### 方案 C：Blender Headless（命令行 + Python）

**描述**：通过 Blender 的 Python API 在 headless 模式下执行模型处理和转换。

```python
# blender --background --python convert.py
import bpy
bpy.ops.import_scene.gltf(filepath="input.glb")
bpy.ops.export_mesh.stl(filepath="output.stl")
```

| 维度 | 评价 |
|------|------|
| **功能完整性** | 最强 — 完整的 3D 建模功能，支持所有格式 |
| **安装难度** | 需要完整 Blender 安装（1GB+），需配置 PATH |
| **性能** | 启动慢（每次冷启动 3-5s），但处理能力最强 |
| **Windows 兼容** | 良好，但 CLI 路径管理复杂 |
| **维护活跃度** | 非常活跃，Blender 基金会持续维护 |
| **局限性** | 体积极大（1GB+）；冷启动慢；每个操作需独立进程；资源消耗高 |

### 方案 D：Assimp（Open Asset Importer Library）

**描述**：C++ 库，支持 40+ 格式，有 Python 绑定（`pyassimp` / `assimp`）。

```python
import assimp
scene = assimp.import_file("input.glb")
assimp.export_scene(scene, "output.stl", "stl")
```

| 维度 | 评价 |
|------|------|
| **功能完整性** | 强大 — 40+ 格式读写，专注于格式转换 |
| **安装难度** | 需安装 C 库（Windows 上需预编译 DLL），pyassimp 年久失修 |
| **性能** | 非常快（C++ 原生） |
| **Windows 兼容** | 一般 — 需要 MSVC 运行库或预编译 wheel |
| **维护活跃度** | Assimp 本身活跃，但 Python 绑定（pyassimp）更新停滞 |
| **局限性** | Python 绑定不成熟；不支持高级处理（仅转换+基本操作） |

### 方案 E：轻量组合（pygltflib + numpy-stl）

**描述**：使用专用的轻量库分别处理 GLB/GLTF 和 STL。

```python
from pygltflib import GLTF2
from stl import mesh as stl_mesh
import numpy as np

gltf = GLTF2().load("input.glb")
# ... 手动解析顶点和面 ...
vertices = np.array([...])
faces = np.array([...])
mesh = stl_mesh.Mesh(np.zeros(faces.shape[0], dtype=stl_mesh.Mesh.dtype))
mesh.save("output.stl")
```

| 维度 | 评价 |
|------|------|
| **功能完整性** | 最弱 — 仅做格式解析，无修复/简化能力 |
| **安装难度** | `pip install pygltflib numpy-stl`，极轻量 |
| **性能** | 取决于实现，可能需手动优化 |
| **Windows 兼容** | 良好 |
| **维护活跃度** | 低，两个库都很小众 |
| **局限性** | 无 OBJ 支持（需额外库）；无任何处理能力；需大量手写代码 |

### 方案 F：Open3D（Intel）

**描述**：Intel 的 3D 数据处理库，侧重点云和 RGB-D 图像，也有网格处理能力。

```python
import open3d as o3d
mesh = o3d.io.read_triangle_mesh("input.glb")
mesh = mesh.simplify_quadric_decimation(50000)
o3d.io.write_triangle_mesh("output.stl", mesh)
```

| 维度 | 评价 |
|------|------|
| **功能完整性** | 中等 — 点云能力强，网格处理有限 |
| **安装难度** | `pip install open3d`，约 200MB，有预编译 wheel |
| **性能** | 非常好（C++ 后端 + CUDA 可选） |
| **Windows 兼容** | 良好 |
| **维护活跃度** | 非常活跃 |
| **局限性** | 体积大（200MB）；网格处理不如 trimesh 全面；侧重可视化 |

---

## 三、对比矩阵

| 维度 | Trimesh (A) | PyMeshLab (B) | Blender (C) | Assimp (D) | 轻量组合 (E) | Open3D (F) |
|------|:-----------:|:-------------:|:-----------:|:----------:|:------------:|:----------:|
| 格式支持 | ★★★★★ | ★★★★ | ★★★★★ | ★★★★ | ★★ | ★★★ |
| 修复能力 | ★★★ | ★★★★★ | ★★★★★ | ★ | ★ | ★★ |
| 简化/减面 | ★★★ | ★★★★★ | ★★★★★ | ★ | ★ | ★★★ |
| 安装体积 | ~5MB | ~50MB | ~1GB | ~10MB | ~1MB | ~200MB |
| Windows 兼容 | ★★★★★ | ★★★★ | ★★★ | ★★ | ★★★★ | ★★★★ |
| API 易用性 | ★★★★★ | ★★★ | ★★★ | ★★ | ★ | ★★★★ |
| 已有依赖 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 社区活跃度 | ★★★★ | ★★★ | ★★★★★ | ★★ | ★ | ★★★★★ |
| 适合本项目 | ✅✅✅ | ✅✅ | ❌ | ❌ | ❌ | ✅ |

---

## 四、推荐方案

### 首选：Trimesh（方案 A）+ PyMeshFix（补充修复）

**理由**：
1. **已有依赖**：项目已经安装了 `trimesh`，`pymeshfix` 也已在 repair 脚本中使用
2. **零额外安装**：无需引入新依赖
3. **功能足够**：GLB/OBJ → STL 转换 + 修复 + 简化 + 缩放，覆盖 90% 打印准备场景
4. **Windows 原生**：纯 Python，无 C 库/运行时依赖

### 备选：PyMeshLab（方案 B）

**适用场景**：当 Trimesh 无法处理某些复杂模型时（如严重非流形、需要高级重网格化），作为后备方案。

### 实施建议

#### 阶段 1：新增 `model_prep` 节点（基于 Trimesh）

在 `node_types.py` 中新增节点类型，在 `scripts/` 中新增对应脚本：

```
节点: model_prep（模型打印准备）
├── 输入: mesh (GLB/OBJ/STL/PLY)
├── 输出: printable_mesh (STL), preview (PNG)
├── 参数:
│   ├── output_format: stl (默认) / 3mf / obj
│   ├── simplify: 目标面数 (0=不简化, 默认 50000)
│   ├── repair: bool (默认 true, 调用 pymeshfix)
│   ├── fill_holes: bool (默认 true)
│   ├── target_size_mm: 目标最大尺寸 (0=保持原始, 默认 100)
│   └── ground: bool (默认 true, 将模型底部移至 z=0)
```

#### 阶段 2：增强 TripoSR/Hunyuan 节点的输出格式

在 `triposr` 和 `hunyuan` 节点中增加 `auto_prep` 参数：
- `auto_prep=true`：生成后自动执行修复+转换，直接输出 STL
- `auto_prep=false`：保持原始输出（GLB/OBJ），由用户手动连接 prep 节点

#### 阶段 3（可选）：PyMeshLab 后备通道

为 `model_prep` 添加 `engine` 参数：`trimesh`（默认）/ `pymeshlab`，在复杂模型上可切换引擎。

---

## 五、关键技术细节

### 5.1 GLB→STL 转换的核心挑战

| 问题 | Trimesh 处理 | PyMeshLab 处理 |
|------|-------------|---------------|
| 非流形边 | `trimesh.repair.fix_normals()` | `remove_duplicate_faces` + `remove_non_manifold_edges` |
| 孔洞 | `trimesh.repair.fill_holes()` | `close_holes` 滤镜 |
| 重复顶点 | `mesh.merge_vertices()` | `merge_close_vertices` |
| 自相交面 | 检测到但修复有限 | `remove_self_intersections` |
| 法线翻转 | `trimesh.repair.fix_normals()` | `re_orient_faces_coherentely` |
| 超大面积 | `mesh.simplify_quadric_decimation()` | `meshing_decimation_quadric_edge_collapse` |
| 纹理/颜色 | STL 不支持，导出时丢失 | 同上 |

### 5.2 推荐的处理管线

```
GLB/OBJ 输入
    │
    ├──→ 1. 合并顶点 (merge_vertices)
    ├──→ 2. 移除退化面 (nondegenerate_faces)
    ├──→ 3. 填充孔洞 (fill_holes)
    ├──→ 4. 修复法线 (fix_normals)
    ├──→ 5. PyMeshFix 水密化 (make_watertight)
    ├──→ 6. 简化减面 (simplify, 目标 50k 面)
    ├──→ 7. 缩放至目标尺寸 (target 100mm)
    ├──→ 8. 落地 (ground, z_min = 0)
    └──→ 导出 STL (binary, 用于打印)
```

### 5.3 现有 `mesh-repair.py` 的可用部分

当前的 `scripts/mesh-repair.py` 已经实现了上述管线的大部分步骤（merge_vertices → unique_faces → nondegenerate_faces → remove_unreferenced_vertices → remove_infinite_values → PyMeshFix → scale → center → ground → export）。可复用其核心逻辑来构建新的 `model_prep` 脚本。

---

## 六、总结

| 结论 | 说明 |
|------|------|
| **推荐方案** | Trimesh（方案 A），已集成，零成本 |
| **备选方案** | PyMeshLab（方案 B），按需引入 |
| **不建议** | Blender（太重）、Assimp（Python 绑定差）、轻量组合（太弱） |
| **实施优先级** | 先新增 `model_prep` 节点，再增强生成节点 |
| **风险** | 极端复杂模型（百万面+严重破损）可能需要人工介入，自动处理无法 100% 覆盖 |
