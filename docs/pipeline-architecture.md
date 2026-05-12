# 管线架构文档

## 总览

```
                    用户输入
                图片 + 参数选择
                       │
     ┌─────────────────┼─────────────────┐
     ▼                 ▼                  ▼
  单图模式         批量模式           直接修复
  (default)       (--batch)         (--skip-generate)
     │                 │                  │
     ▼                 ▼                  │
┌─────────────┐  ┌─────────────┐         │
│  Stage 1    │  │  遍历图片    │         │
│  Image→3D   │  │  for each:  │         │
│  TripoSR    │  │  Stage 1    │         │
│             │  └──────┬──────┘         │
│  输入:      │         │                │
│  .jpg/.png  │         ▼                │
│  .webp      │  ┌─────────────┐         │
│             │  │  汇总结果    │         │
│  输出:      │  └──────┬──────┘         │
│  .glb       │         │                │
│  (顶点色)   │         │                │
└──────┬──────┘         │                │
       │                │                │
       ▼                ▼                ▼
┌─────────────────────────────────────────┐
│  Stage 2: Mesh Repair                  │
│  Trimesh + PyMeshFix                   │
│                                        │
│  输入: .glb / .obj / .stl             │
│  Pipeline:                             │
│    load → clean → PyMeshFix →         │
│    scale → center → ground → export   │
│                                        │
│  输出: _print.stl (watertight)         │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Stage 3: Slice (手动 / OrcaSlicer)    │
│                                        │
│  orcaslicer --orient 1 --arrange 1     │
│    --slice 0 --export-3mf output.3mf   │
│    input.stl                           │
│                                        │
│  输出: .3mf (含 gcode)                 │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Stage 4: Print (手动 / Bambu Studio)  │
│                                        │
│  通过 Bambu Studio 或 MCP Server       │
│  发送 .3mf 到打印机                     │
└─────────────────────────────────────────┘
```

## Stage 1: Image → 3D 详解

### 引擎: TripoSR

**模型架构**:
```
Input Image (RGB, any resolution)
    │
    ▼
[Background Removal]  rembg (u2net)
    │
    ▼
[Foreground Resize]   居中 + padding → 512×512
    │
    ▼
[DINO ViT Encoder]    图像 → token embeddings (768-dim)
    │
    ▼
[Transformer-1D]      16 layers × 16 heads × 64 dim
    │                  交叉注意力到图像 tokens
    ▼
[Triplane Decoder]    tokens → triplane (3×64×64×40)
    │
    ▼
[NeRF MLP]            采样点 → density + color
    │
    ▼
[Marching Cubes]      density grid → mesh surface
    │                  分辨率: 64–384 (默认 256)
    ▼
Output: Trimesh (vertices + faces + vertex_colors)
```

**VRAM 估算 (fp32)**:
| 组件 | VRAM |
|------|------|
| DINO ViT-B/16 | ~350 MB |
| Transformer (16L) | ~400 MB |
| Triplane (64² × 40 × 3) | ~50 MB |
| NeRF MLP | ~20 MB |
| Marching Cubes (256³ grid) | ~1.7 GB |
| **Total** | **~2.5 GB** |

### 预处理管线

```python
# 1. 背景去除 (rembg)
image = remove_background(image, rembg_session)

# 2. 前景缩放居中
image = resize_foreground(image, ratio=0.85)

# 3. 填充灰色背景 (R=G=B=0.5)
image_arr = rgb * alpha + 0.5 * (1 - alpha)
```

## Stage 2: Mesh Repair 详解

### 修复管线

```python
# 1. 加载
mesh = trimesh.load(input_path, force="mesh")

# 2. 多体 → 取最大
if isinstance(mesh, trimesh.Scene):
    mesh = max(meshes, key=lambda m: len(m.vertices))

# 3. 清理
mesh.update_faces(mesh.unique_faces() & mesh.nondegenerate_faces())
mesh.remove_unreferenced_vertices()
mesh.remove_infinite_values()

# 4. 深度修复 (PyMeshFix)
fix = pymeshfix.MeshFix(mesh.vertices, mesh.faces)
fix.repair()
# pymeshfix 0.18+ returns pyvista PolyData
mesh = trimesh.Trimesh(vertices=fix.mesh.points, faces=fix.mesh.faces.reshape(-1,4)[:,1:])

# 5. 后处理
mesh.apply_scale(scale)
mesh.vertices -= mesh.centroid
mesh.vertices[:, 2] -= mesh.vertices[:, 2].min()  # 落地
mesh.export(out_path)
```

### 输出格式

| 格式 | 用途 | 颜色 |
|------|------|------|
| .stl | 3D 打印标准 (推荐) | 无 |
| .3mf | 现代 3D 打印 (含元数据) | 有 |
| .obj | 通用交换格式 | 有 (mtl) |

## Stage 3: 切片 (规划中)

OrcaSlicer CLI 自动化切片:
```bash
orcaslicer --orient 1 --arrange 1 \
  --load-settings "printer.json;process.json" \
  --slice 0 --export-3mf output.3mf input.stl
```

## 数据流

```
input.jpg (any size)
  → output/input_3d.glb (~5–50 MB, 10K–200K faces)
  → output/input_3d_print.stl (~2–20 MB, watertight)
  → output/input_3d_print.3mf (~5–50 MB, sliced)
```

## 扩展点

1. **多引擎支持**: pipeline.py 已支持通过 --engine 切换 TripoSR / Hunyuan3D
2. **批量处理**: 遍历输入目录，自动处理所有图片
3. **自动切片**: 集成 OrcaSlicer CLI
4. **打印队列**: MCP Server 直接发送到打印机
