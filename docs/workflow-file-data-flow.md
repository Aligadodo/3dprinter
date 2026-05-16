# 工作流数据流与文件流设计文档

> 版本: 1.0 | 日期: 2026-05-14 | 项目: 3D Print Pipeline

## 目录

1. [架构概览](#1-架构概览)
2. [目录结构与命名规则](#2-目录结构与命名规则)
3. [Context 数据结构](#3-context-数据结构)
4. [端口系统与边映射](#4-端口系统与边映射)
5. [输入解析链路 `_resolve_input`](#5-输入解析链路-_resolve_input)
6. [六种节点执行器详解](#6-六种节点执行器详解)
7. [输出文件收集与端口映射](#7-输出文件收集与端口映射)
8. [DAG 拓扑执行模型](#8-dag-拓扑执行模型)
9. [Fork / Merge 场景分析](#9-fork--merge-场景分析)
10. [边界情况与已知限制](#10-边界情况与已知限制)
11. [文件生命周期](#11-文件生命周期)

---

## 1. 架构概览

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  server.py   │────→│ workflow_engine │────→│    scheduler     │
│  入口/API    │     │  DAG拓扑+执行    │     │  子进程+GPU锁    │
└──────────────┘     └─────────────────┘     └──────────────────┘
                            │                        │
                      ┌─────┴─────┐            ┌─────┴─────┐
                      │ node_types│            │  scripts/ │
                      │ 端口定义   │            │ Python脚本 │
                      └───────────┘            └───────────┘
                            │
                      ┌─────┴─────┐
                      │inline_nodes│
                      │ PIL 处理   │
                      └───────────┘
```

**三套文件存储体系**：

| 体系 | 路径 | 用途 |
|------|------|------|
| 任务隔离目录 | `output/tasks/YYYY-MM-DD-<id8>-<abbr>-<stem>/` | 每个 pipeline 节点的独立工作区 |
| 工作流实例目录 | `output/tasks/workflows/<inst_id>/` | 整个工作流共享的用户文件和 inline 产物 |
| 脚本输出子目录 | `output/<pipeline_type>/` | 旧版脚本直接调用时的输出（不走 scheduler 时） |

---

## 2. 目录结构与命名规则

### 2.1 任务隔离目录

**定义**：`models.py:67-95` `make_task_dir_name()`

```
格式:  YYYY-MM-DD-<uuid8>-<abbreviation>-<stem>
示例:  2026-05-10-a1b2c3d4-rlf-photo
       ├── input.jpg          # 固定名称，始终是 input{ext}
       ├── relief/
       │   └── input_relief.stl
       └── ...
```

- `<abbreviation>`：pipeline 类型的 2-4 字符缩写（`rlf`=relief, `tri`=triposr, `layr`=layered_relief）
- `<stem>`：输入文件名的净化版本（仅保留字母数字中文，最长 20 字符）
- 输入文件始终重命名为 `input{ext}`
- 脚本的输出子目录（`relief/`、`output/` 等）在 task_dir 内部，天然隔离

### 2.2 工作流实例目录

**定义**：`server.py:613-614`

```
格式:  output/tasks/workflows/<inst_id>/
示例:  output/tasks/workflows/a1b2c3d4e5f6/
       ├── photo.jpg                    # 用户上传文件（保留原名）
       ├── prompt_3.txt                 # text_input 节点持久化
       ├── inline_f7e8d9c0.png          # inline 节点输出（uuid8）
       └── inline_aabbccdd.stl
```

- `inst_id` = `uuid4().hex[:12]`
- 同一工作流的所有 inline 节点共享此目录
- 每次运行创建新目录，运行间完全隔离

### 2.3 文件命名冲突防护

| 场景 | 防护手段 |
|------|---------|
| 不同工作流运行 | `inst_id` 独立（uuid 12-char） |
| 不同 pipeline 节点的 task_dir | `task_id` 独立（uuid 12-char） |
| 同一工作流内多个 inline 节点 | 文件名嵌入 `uuid4().hex[:8]` |
| 多个 text_input 节点 | 文件名带 `nid`：`prompt_{nid}.txt` |
| 上传文件在同实例内多节点引用 | `shutil.copy2` 各自复制，不共享可变文件 |

---

## 3. Context 数据结构

Context（`ctx` dict）是工作流引擎的**唯一共享状态**，在节点间传递数据。

### 3.1 顶层结构

```python
ctx = {
    # ── 系统保留键（以 _ 开头）──
    "_work_dir":     "output/tasks/workflows/a1b2c3d4e5f6/",  # 工作流实例目录
    "_inputs": {                                              # 外部输入（上传文件/文本）
        "1": {"file": "/path/to/photo.jpg"},
        "2": {"text": "user prompt text"},
    },
    "_node_params": {                                         # 运行时参数覆盖
        "3": {"width": 200},
    },
    "_node_inputs": {                                         # 运行时边覆盖
        "4": {"image": {"source_node": "1", "source_port": "file"}},
    },

    # ── 节点输出（键名为 node ID 字符串）──
    "1": {
        "file": "/path/to/photo.jpg",           # 端口名: 文件路径
        "_inputs": {"file": "/path/to/photo.jpg"},
        "_params": {},
        "_upstream": {},
    },
    "3": {
        "stl": "/path/to/output.stl",
        "color_preview": "/path/to/preview.png",
        "_inputs": {"file": "/path/to/input.jpg"},
        "_params": {"width": 160.0, "height": 120.0},
        "_upstream": {
            "1": {"file": "/path/to/photo.jpg", "_inputs": {...}},
            "2": {"image": "/path/to/inline.png", "_params": {...}},
        },
    },
}
```

### 3.2 每个节点 ctx 条目的字段

| 字段 | 写入者 | 含义 |
|------|--------|------|
| `<port_name>` | 各执行器 | 节点的输出文件路径，key 为端口名（如 `stl`, `image`, `file`, `mesh`） |
| `_inputs` | `_enrich_ctx` / 各执行器 | 本节点使用的输入映射 |
| `_params` | `_enrich_ctx` / 各执行器 | 本节点使用的参数合并结果 |
| `_upstream` | `_enrich_ctx` | 所有上游节点的 ctx 扁平合并（BFS 收集，含传递闭包） |

### 3.3 `_upstream` 构建逻辑

`workflow_engine.py:242-311` `_build_upstream`：

1. 通过 `edge_map` BFS 遍历所有入边
2. 对每条入边 `(tgt_id, tgt_port) → (src_id, src_port)`，如果 `tgt_id == nid`：
   - 将源节点完整 ctx 合并进 `upstream[src_id]`
   - 将源节点的 `_upstream` 也传递合并（传递闭包）
3. 最终写入 `ctx[nid]["_upstream"]`

这保证了任意节点可以访问**所有上游链路上任意节点的端口输出**，不仅是直接上游。

---

## 4. 端口系统与边映射

### 4.1 端口类型系统

**`node_types.py:10-20`** `PortSpec`：

| 端口类型 | 文件扩展名 | 用途 |
|---------|-----------|------|
| `image` | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`, `.tiff`, `.tif` | 图像输入/输出 |
| `stl` | `.stl` | STL 3D 模型 |
| `mesh` | `.stl`, `.obj`, `.glb`, `.gltf`, `.3mf`, `.ply` | 通用 3D 网格 |
| `file` | 上述全部 + `.json`, `.txt` | 泛用文件传递 |
| `string` | N/A | 文本数据（prompt） |
| `dir` | N/A | 目录路径 |
| `any` | 任意 | 不校验类型 |

### 4.2 各节点类型端口清单

**生成类节点**（输入 image，输出 3D 文件）：

| 节点类型 | 输入端口 | 输出端口 | GPU |
|---------|---------|---------|-----|
| `relief` | `image` (image) | `stl` (stl), `color_preview` (image, 可选) | - |
| `lithophane` | `image` (image) | `stl` (stl), `color_preview` (image, 可选) | - |
| `layered_relief` | `image` (image) | `stl` (stl), `3mf` (file, 可选), `color_map` (json), `color_preview` (image, 可选) | - |
| `triposr` | `image` (image) | `mesh` (stl), `preview` (image, 可选) | ✓ |
| `hunyuan` | `image` (image) | `mesh` (stl), `preview` (image, 可选) | ✓ |

**处理类节点**（输入 mesh，输出处理后的 mesh）：

| 节点类型 | 输入端口 | 输出端口 |
|---------|---------|---------|
| `repair` | `mesh` (stl) | `repaired_mesh` (stl) |
| `model_prep` | `mesh` (stl) | `mesh` (stl), `preview` (image, 可选) |
| `mesh_simplify` | `mesh` (stl) | `mesh` (stl) |
| `mesh_smooth` | `mesh` (stl) | `mesh` (stl) |
| `mesh_scale` | `mesh` (stl) | `mesh` (stl) |
| `views` | `mesh` (stl) | `grid` (image), `views_dir` (dir, 可选) |

**Inline 图像处理节点**（输入 image，输出 image）：

| 节点类型 | 输入端口 | 输出端口 |
|---------|---------|---------|
| `image_resize` | `image` (image) | `image` (image) |
| `image_grayscale` | `image` (image) | `image` (image) |
| `image_crop` | `image` (image) | `image` (image) |
| `image_adjust` | `image` (image) | `image` (image) |
| `image_convert` | `image` (image) | `image` (image) |
| `remove_background` | `image` (image) | `image` (image), `mask` (image, 可选) |

**特殊节点**：

| 节点类型 | 输入端口 | 输出端口 | 说明 |
|---------|---------|---------|------|
| `file_input` | （无） | `file` (file) | 外部文件入口 |
| `text_input` | （无） | `text` (string) | 外部文本入口 |
| `text_to_image` | `prompt` (string) | `image` (image) | AI 文生图 |
| `output_file` | `file` (any) | （无） | 输出收集终点 |

### 4.3 主输入端口映射

`node_input_port_map()` (`node_types.py:755-765`) 定义了每种节点的**首要输入端口**名称：

```python
"relief" → "image",  "lithophane" → "image",  "triposr" → "image",
"repair" → "mesh",   "views" → "mesh",         "mesh_simplify" → "mesh",
...
```

`_run_pipeline` 遍历节点的全部输入端口，找到第一个类型匹配且有有效文件值的端口作为 `input_file`。

### 4.4 边映射构建 `_build_port_edge_map`

`workflow_engine.py:204-233`：

```
输入: node_map + LiteGraph edges (含 slot index)
输出: edge_map: {(target_nid, target_port_name): (source_nid, source_port_name)}
```

关键行为：

1. **LiteGraph slot index → port name 翻译**：通过 `NodeType.outputs[src_slot]` 和 `NodeType.inputs[tgt_slot]` 将数字索引转为端口名
2. **支持字符串端口名**：如果 slot 本身就是字符串（新版 LiteGraph），直接使用
3. **以 `(target_nid, target_port_name)` 为 key**：dict 结构，每个目标端口只能有一条边
4. **多条边指向同一目标端口 → 后者覆盖前者**：无警告
5. **边指向不存在的节点 → 静默丢弃**：`if src_nid not in node_map or tgt_nid not in node_map: continue`
6. **slot index 超出端口定义范围 → 静默丢弃**：port_name 为 None，不加入 edge_map

---

## 5. 输入解析链路 `_resolve_input`

`workflow_engine.py:694-722` — 三级优先级查找：

```
优先级 1: 运行时边覆盖 (_node_inputs)
    ↓ 未命中
优先级 2: 保存的图边 (edge_map)
    ↓ 未命中
优先级 3: 外部输入 (_inputs)
    ↓ 未命中
返回 None
```

```python
def _resolve_input(self, node_id, port_name, edge_map, ctx):
    nid = str(node_id)

    # 1. 运行时覆盖
    node_inputs = ctx.get("_node_inputs", {})
    if nid in node_inputs and port_name in node_inputs[nid]:
        override = node_inputs[nid][port_name]
        src_node = str(override.get("source_node", ""))
        src_port = override.get("source_port", "")
        if src_node and src_port:
            src_ctx = ctx.get(src_node, {})
            val = src_ctx.get(src_port)
            if val is not None:
                return val

    # 2. 保存的图边
    key = (nid, port_name)
    if key in edge_map:
        src_node, src_port = edge_map[key]
        src_ctx = ctx.get(src_node, {})
        val = src_ctx.get(src_port)
        if val is not None:
            return val

    # 3. 外部输入
    ext = ctx.get("_inputs", {}).get(nid, {})
    return ext.get(port_name)
```

**注意**：每级都检查 `val is not None`，这意味着**上游产出 None/falsy 值时会被跳过**，继续尝试下一优先级。

---

## 6. 六种节点执行器详解

### 6.1 执行调度

`workflow_engine.py:410-423` 根据 `node_type` 分派到不同执行器：

```python
if node_type == "file_input":
    await self._run_file_input(...)
elif node_type == "text_input":
    await self._run_text_input(...)
elif node_type == "text_to_image":
    await self._run_text2img(...)
elif node_type == "output_file":
    await self._run_output(...)
elif node_type in nt.node_pipeline_map():
    await self._run_pipeline(...)
elif nt_def and nt_def.inline and node_type in inline_nodes.INLINE_HANDLERS:
    await self._run_inline(...)
else:
    raise ValueError(f"Unknown node type: {node_type}")
```

### 6.2 `_run_file_input` — 文件入口

`workflow_engine.py:506-516`

```
输入: ctx["_inputs"][nid]["file"]  ← 用户上传或外部指定
输出: ctx[nid] = {"file": dest_path}
```

- 从 `_inputs` 读取源文件路径
- 如果 work_dir 已设置，copy 到实例目录
- 写入 ctx，产出 `file` 端口值

### 6.3 `_run_text_input` — 文本入口

`workflow_engine.py:521-533`

```
输入: ctx["_inputs"][nid]["text"]  ← 用户输入文本
输出: ctx[nid] = {"text": text}
```

- 将文本持久化为 `prompt_{nid}.txt` 到 work_dir
- 文本内容同时保存在 ctx 中

### 6.4 `_run_text2img` — AI 文生图

`workflow_engine.py:458-483`

```
输入: prompt (来自上游 text_input 或运行时参数)
输出: ctx[nid] = {"image": result.image_path}
```

- 通过 `providers.get_provider()` 调用 AI 接口
- 输出图像路径写入 ctx

### 6.5 `_run_pipeline` — Pipeline 节点（核心执行器）

`workflow_engine.py:538-685`

这是最重要的执行器，所有 3D 处理节点（relief, triposr, repair, mesh_simplify 等）都走此路径。

**执行流程**：

```
1. 查找主输入端口 → 解析上游文件路径 (_resolve_input)
2. 文件类型校验 (_validate_file_for_port) → 仅 warning
3. 参数合并: 默认值 + 运行时覆盖 (_node_params)
4. 生成 task_id (uuid12)
5. 创建 task_dir: output/tasks/<make_task_dir_name(...)>/
6. 复制输入文件: task_dir/input{ext}
7. 提交 scheduler.submit()
8. 轮询 event_queue (0.5s 间隔)
   - 转发进度/预览/日志事件
   - 检查取消标志
   - done → 退出轮询
   - error → 抛出 RuntimeError
9. 获取 task 结果 + output_files
10. 输出文件 → 端口名映射
11. 写入 ctx[nid]
```

**参数合并优先级**：`运行时 _node_params > 图定义 params > 节点类型默认值`

### 6.6 `_run_inline` — PIL 图像处理

`workflow_engine.py:488-504` + `inline_nodes.py`

```
输入: 上游 ctx 中的 image/file 路径
输出: ctx[nid] = {"image": out_path, "mask": mask_path(可选)}
```

- 不创建 task_dir，直接写入 work_dir
- 输出文件名 `inline_{uuid8}.png`
- 所有 inline 节点共享 work_dir，uuid 保证无冲突
- 通过 `inline_nodes.py:_resolve_input_file` + `_resolve_input` 双通道查找上游输入

### 6.7 `_run_output` — 输出收集

`workflow_engine.py:687-692`

```
输入: 上游 ctx 中任意端口的文件
输出: ctx[nid] = {"file": input_path}
```

- 仅收集一个 file 端口的输入
- 不产生新文件
- 用于工作流末尾的输出标记

---

## 7. 输出文件收集与端口映射

### 7.1 Scheduler 端 `_collect_output_files`

`scheduler.py:255-314`

脚本输出通过三步收集：

1. **预览类 key**（`color_preview`, `grid`, `preview`）→ category `"preview"`
2. **结果类 key**（`output`, `stl`, `colored_obj`, `final_output` 等）→ category `"result"`
3. **目录 key**（`views_dir`）→ 扫描目录内所有文件
4. **嵌套子结果**（`generate`, `repair`, `views` 子 dict）→ 递归收集

每个文件通过 `models.add_output_file(task_id, ext, path, category)` 注册。

### 7.2 引擎端 输出文件→端口映射

`workflow_engine.py:628-681` — 两种策略依次执行：

**策略 A: 扩展名→端口类型映射**

```python
# 从 node_type 定义构建映射
ext_port_map = {}  # {".stl": "stl", ".png": "color_preview", ...}
for port in nt_def.outputs:
    exts = PORT_TYPE_EXTENSIONS.get(port.type, [])
    for file_ext in exts:
        ext_port_map.setdefault(file_ext, port.name)  # ← setdefault: 第一个匹配的端口胜出
```

然后遍历 `output_files`，将每个文件按其扩展名分配到对应端口名。

**策略 B: Result JSON key→端口名映射（补充）**

```python
result_path_keys = {
    "stl": ["output", "stl", "colored_obj"],
    "3mf": ["output_3mf"],
    "mesh": ["output", "stl"],
    "repaired_mesh": ["final_output"],
    "grid": ["grid"],
    "preview": ["preview"],
    "views_dir": ["views_dir"],
    "color_preview": ["color_preview"],
    "color_map": ["color_map"],
}
```

对策略 A 未填充的端口，检查 result dict 中是否有对应 key 的值。

### 7.3 文件校验

`workflow_engine.py:49-64` `_validate_file_for_port`：

仅对 `image`, `stl`, `mesh`, `file` 四种类型做校验。校验失败时**返回 warning 字符串但不阻塞执行**。

---

## 8. DAG 拓扑执行模型

### 8.1 执行模型

`workflow_engine.py:316-449`：

```
1. 解析图 → node_map (id → node)
2. 规范化边 → _normalize_edges (兼容 LiteGraph links 格式)
3. 构建 DAG → 邻接表 adj + 入度 in_degree
4. 拓扑排序 → BFS Kahn 算法
5. 构建端口边映射 → _build_port_edge_map
6. 恢复上下文 → ctx = preserved_ctx or persisted
7. 确定执行列表 → 支持 start_node 重放
8. 预创建所有 node_run 记录
9. 串行遍历 exec_list → 逐个节点调度执行
```

### 8.2 串行执行，非并行

当前实现是**串行遍历拓扑序**（for 循环，非 asyncio.gather），即使拓扑允许并行的节点也顺序执行。GPU 锁在 scheduler 内部串行化 GPU 使用。

### 8.3 错误传播

一个节点失败 → 所有后续节点标记为 `skipped`（`workflow_engine.py:435-442`）：

```python
for later_nid in exec_list[idx + 1:]:
    wm.update_node_run(..., status="skipped",
                       error="Skipped due to upstream failure")
```

整个工作流实例标记为 `failed`。

### 8.4 取消机制

`workflow_engine.py:377-385`：每个节点执行前检查 `cancel_flags[instance_id]`。取消时，剩余未执行节点标记为 `cancelled`，实例状态设为 `cancelled`。

### 8.5 重放（Replay）

`workflow_engine.py:361-363`：支持指定 `start_node`，从该节点开始执行。前置节点的 ctx 从 `preserved_ctx` 恢复，不重新执行。

### 8.6 Context 持久化时机

**每个节点完成后立即持久化**（`workflow_engine.py:428`）：

```python
wm.update_node_run(nr["id"], status="completed", finished_at=time.time())
wm.update_workflow_context(instance_id, ctx)  # 立即写入 DB
```

ctx 写入 `workflow_instances.context_json` 列，确保：
- 任务详情页可实时显示已完成节点的中间输出
- 工作流中途崩溃时已完成节点的数据不丢失
- API `/api/tasks/{id}/workflow` 和 `/api/workflows/instances/{id}` 返回的 context 包含最新节点输出

**注意**：工作流结束时（成功/失败/取消）不再单独调用 `update_workflow_context`——每个节点完成后已经保存了最新状态。

---

## 9. Fork / Merge 场景分析

### 9.1 Fork（一对多分叉）

```
        ┌──→ B (relief)    → stl_b
A(upload)──→ C (triposr)   → mesh_c
        └──→ D (repair)    → repaired_d
```

**完全安全**。每条边对应不同的 `(target_nid, target_port_name)` key，各自独立加入 edge_map。每个下游节点通过 `_resolve_input` 读取同一个上游路径字符串，然后各自在 task_dir 内 `shutil.copy2` 一份副本。不存在文件竞态。

### 9.2 Merge（多对一汇聚）

```
B(stl) ──→ D
C(mesh) ──→ D
```

**严格依赖端口名**。`edge_map` 中最多只有一条边能命中 D 的特定端口：

- 如果 B 的 `stl` 口连到 D 的 `mesh` 口，C 的 `mesh` 口也连到 D 的 `mesh` 口 → **后者覆盖前者**，C 的值胜出，B 被忽略
- 如果 B 连到 D 的 `mesh` 口，C 连到 D 的 `file` 口 → 两者共存，D 的不同端口各自拿到对应文件

**`_run_pipeline` 的实际行为**：遍历节点输入端口，取**第一个**命中文件的端口作为 `input_file`（`workflow_engine.py:546-552`）。即使 edge_map 中有多条入边对应不同端口，也只有第一个端口被使用。

```python
for port in nt_def.inputs:
    if port.type in ("image", "stl", "mesh", "file", "any"):
        val = self._resolve_input(nid, port.name, edge_map, ctx)
        if val and os.path.exists(val):
            input_file = val      # ← 只取第一个命中
            resolved_port_type = port.type
            break
```

**结论**：Pipeline 节点本质上只接受一个输入文件。当前的数据模型不支持"将多个上游文件合并处理"的语义。

### 9.3 文件扩散

链式处理 A→B→C→D 中，每个 pipeline 节点都会 copy2 一份输入文件。100MB 文件经 10 个 pipeline 节点 = 约 1GB 磁盘占用。Inline 节点不产生副本（直接读写 work_dir）。

---

## 10. 边界情况与已知限制

### 10.1 静默丢弃的边

以下三种情况边被跳过且**不产生任何警告**：

| 场景 | 位置 | 后果 |
|------|------|------|
| 边引用了不存在的节点 ID | `_build_port_edge_map:214-215` | 数据流断开 |
| slot index 超出端口数量 | `_build_port_edge_map:222-223, 227-228` | 边不加入映射 |
| node type 未在 node_types 注册 | `_build_port_edge_map:218-219` | src_nt/tgt_nt 为 None，port_name 为 None |

### 10.2 上传文件只分配给第一个 file_input

`server.py:629-631`：

```python
for fnid in file_input_nodes:
    if fnid not in inputs_dict or "file" not in inputs_dict.get(fnid, {}):
        inputs_dict.setdefault(fnid, {})["file"] = file_path
        break  # ← 只分给第一个
```

多 file_input 场景下，其余节点收不到文件。

### 10.3 Pipeline 节点单输入约束

`_run_pipeline` 只取第一个匹配端口（`break`），不支持多文件输入。

### 10.4 文件校验仅 Warning

`_validate_file_for_port` 返回 warning 字符串但不阻塞，文件类型不匹配时节点仍继续执行。

### 10.5 `_run_output` 不传递 `_params`

`_run_output` 创建 ctx 时不包含 `_params`，与 pipeline 节点不同。依赖 `_params` 的下游代码可能遇到 KeyError。

### 10.6 无自动文件清理

- 删除任务 (`models.delete_task`) 会清理 task_dir
- 工作流实例目录 (`workflows/<inst_id>/`) 无自动清理
- Retry 创建新 task_dir，旧目录不自动删除

### 10.7 输出文件 URL 构造规则

`workflow_models.py:_get_task_output_files` 从绝对路径构造 `/api/files/` URL：

```python
# 路径: D:\projects\3dprint\output\tasks\<dir>\file.jpg
# split("output/", 1) → ['D:/projects/3dprint/', 'tasks/<dir>/file.jpg']
f["url"] = "/api/files/output/" + fp.replace("\\", "/").split("output/", 1)[1]
# 结果: /api/files/output/tasks/<dir>/file.jpg
```

**关键点**：URL 必须以 `output/` 开头，因为 `server.py:229` 的文件服务使用 `os.path.join(PROJECT_ROOT, file_path)` 解析路径，而 `PROJECT_ROOT` = `D:\projects\3dprint`，文件实际位于 `output/tasks/...` 下。

**前端同步规则**：`node-detail.js:fileToUrl()` 使用 marker 优先级 `['/output/tasks/', '/tasks/', '/output/']`，其中 `/output/tasks/` 优先匹配，`n.slice(idx + 1)` 保留 `output/tasks/` 前缀，与后端 URL 格式一致。

---

## 11. 文件生命周期

```
创建阶段
  │
  ├─ 用户上传 ──→ workflows/<inst_id>/<original_name>    [server.py:619-620]
  ├─ file_input ──→ workflows/<inst_id>/<copy>             [engine:_run_file_input]
  ├─ text_input ──→ workflows/<inst_id>/prompt_{nid}.txt   [engine:_run_text_input]
  ├─ inline节点 ──→ workflows/<inst_id>/inline_{uuid8}.ext [inline_nodes:_output_path]
  ├─ pipeline节点 ──→ tasks/<dir_name>/input{ext}           [engine:_run_pipeline:587-588]
  └─ 脚本输出 ──→ tasks/<dir_name>/<subdir>/<output>       [scripts: image-to-*.py]

读写阶段
  │
  ├─ 节点读上游 ── _resolve_input 返回路径字符串
  ├─ 节点写 ctx ── ctx[nid][port_name] = 绝对路径
  └─ scheduler 收集 ─ _collect_output_files 扫描 result JSON

消费阶段
  │
  ├─ 下载 ── ZIP 遍历 ctx + node_runs
  ├─ 预览 ── 读取 ctx[nid]["color_preview"] / ctx[nid]["preview"]
  └─ 传递 ── 下游节点通过 ctx 路径字符串读取 + copy2

清理阶段
  │
  ├─ delete_task ── shutil.rmtree(task_dir) [models:272]
  └─ 实例目录 ── 无自动清理（需手动或后续功能）
```

---

## 附录 A：关键文件索引

| 文件 | 内容 |
|------|------|
| `web/workflow_engine.py` | DAG 构建、拓扑排序、边映射、6 种执行器、ctx 管理 |
| `web/scheduler.py` | 任务提交、子进程管理、GPU 锁、输出文件收集 |
| `web/node_types.py` | 端口定义、节点类型注册、参数规格、类型映射 |
| `web/inline_nodes.py` | 6 种 inline PIL 处理器实现 |
| `web/server.py` | API 端点、工作流实例创建、文件上传处理、ZIP 下载 |
| `web/models.py` | 任务/文件 DB 操作、目录命名 `make_task_dir_name`、`delete_task` |
| `web/schemas.py` | Pipeline 类型元数据（script, params, gpu 标志） |
| `scripts/image-to-relief.py` | relief/lithophane 生成脚本 |
| `scripts/image-to-3d.py` | triposr/hunyuan 3D 重建脚本 |
| `scripts/image-to-layered-relief.py` | 分层浮雕脚本 |
| `scripts/mesh-repair.py` | 网格修复脚本 |

## 附录 B：关键常量

| 常量 | 值 | 位置 |
|------|-----|------|
| `TASKS_DIR` | `output/tasks/` | `scheduler.py:15` |
| `PORT_TYPE_EXTENSIONS` | `{".stl": ["stl"], ...}` | `workflow_engine.py:29-37` |
| `_PORT_EXTENSIONS` | `{"image": {".png", ...}, ...}` | `workflow_engine.py:40-46` |
| `result_path_keys` | `{"stl": ["output", "stl", ...], ...}` | `workflow_engine.py:660-670` |
| `preview_keys` | `["color_preview", "grid", "preview"]` | `scheduler.py:257` |
| `result_keys` | `["output", "stl", ...]` | `scheduler.py:258-259` |
| `INLINE_HANDLERS` | `{"image_resize": ..., ...}` | `inline_nodes.py:346-353` |
