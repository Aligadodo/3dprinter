# 3D 模型二创（修改与创意设计）—— 长期规划

> 当前状态：mesh 节点基础能力已实现，但缺乏 AI 层和交互式可视化，难以实用。本文档记录方向性决策。

## 目标

让用户通过**自然语言 + 参考素材**描述想要的修改，系统自动完成：
- 定位（模型哪部分要改）
- 切割（分离目标区域）
- 生成（AI 生成替换件）
- 融合（布尔运算 + 缝合）
- 输出（二创模型）

## 当前能力

| 组件 | 状态 | 说明 |
|------|------|------|
| mesh_boolean | ✅ 可用 | union/diff/intersect via manifold3d |
| mesh_stitch | ✅ 可用 | HC smoothing + repair via pymeshlab |
| mesh_cut | ✅ 可用 | trimesh slice_plane |
| mesh_align | ✅ 可用 | boundary-based alignment |
| mesh_decorate | ✅ 可用 | UV displacement + vertex colors |
| Web 节点注册 | ✅ 完成 | 7个节点类型已注册 |

## 缺失的关键能力

### 1. 语义理解层（Semantic Understanding）

**问题：** 系统不知道模型哪部分是什么（头部、手柄等）。

**原因：**
- STL/OBJ 无语义信息（无顶点组、无命名特征）
- glTF 有 named mesh primitives，但导入 trimesh 后丢失

**可能的方案：**
- glTF 优先：用户上传 glTF 时保留语义信息
- 用户交互：3D preview 中点选区域（需要 WebGL 交互）
- LLM 辅助：根据几何特征推测部件类型（实验性）

### 2. 3D 可视化交互（3D Viewer Integration）

**问题：** 没有交互式 3D 预览，用户无法点选区域、确认边界。

**当前：** 工作流编辑器里用的是 LiteGraph 2D canvas，无 3D 预览。

**可能的方案：**
- 基于 `Three.js` 或 `forge-core` 在 Web UI 中嵌入 3D viewer
- 支持：旋转、缩放、点击选取（ray casting）
- 点击后高亮选中区域 → 自动填充 bounding box 参数

### 3. AI 规划层（LLM-Powered Planning）

**问题：** 即使能分割区域，也需要手动指定切割平面、对齐参数。

**愿景：**
```
用户: "把机器人的头换成猫头"
LLM理解: → "识别出模型中头部所在的bounding box"
       → "在颈部画一个切割平面"
       → "生成一个猫头mesh"
       → "缝合到原模型"
```

**限制：** 2026 年尚无成熟的多模态 LLM 能可靠地完成这套规划，GPT-4V 也只能做简单的几何推断。

**务实的中间路线：** 让 LLM 做参数建议而非全自动控制，最终由用户确认。

### 4. 端到端工作流串联

**当前：** 各节点独立工作，无串联测试。

**需要验证的链路：**
```
mesh_cut(分离头部) → mesh_align(对齐新头部) → mesh_boolean union → mesh_stitch → 输出
```

## 技术债务

| 问题 | 说明 |
|------|------|
| Blender 未被实际使用 | 原计划用 Blender bisect，因 API 缺失改用 trimesh，功能等效但计划偏离 |
| UV decoration 受限 | mesh_decorate 要求 UV 坐标，STL 无 UV，需要 Blender UV unwrap 或降级方案 |
| 缺乏边界测试 | mesh_align 在测试中对齐两个 box 时因 boundary vertices 检测问题无法对齐 |

## 推荐优先级

### P0（可完成，效果明确）
1. **完善 mesh_decorate 的 Blender UV unwrap**：让没有 UV 的 mesh 也能装饰
2. **mesh_align + mesh_boolean + mesh_stitch 串联测试**：验证工作流可用
3. **折叠不常用节点**（mesh_ops 分类）

### P1（有价值，需要投入）
4. **3D Viewer 嵌入**：允许用户在 Web UI 中预览、旋转、点击选取模型区域
5. **语义分割参考**：基于参考图 + LLM 做区域类型推测

### P2（长期目标，不紧急）
6. **LLM 全自动规划**：参数自动计算 + 用户确认机制
7. **多部件组合**：支持多个替换件的协调对齐

## 已知限制

1. **manifold3d 要求 watertight 输入**：非流形 mesh 会导致 boolean 失败
2. **mesh_align 检测 boundary vertices**：依赖 sharp edge angle threshold，阈值敏感
3. **Blender headless API 缺失**：`bpy.ops.import_mesh.stl` 在 `--background` 模式下不可用
4. **3D 交互需要 WebGL**：目前前端无 3D viewer 组件

## 关联文档

- `wf-editor-node-panel-optimization.md` — 节点面板折叠方案
- `../iterations/2026-05-16-151137-3D-Model-二创-修改与创意设计-技术方案.md` — 技术方案详情