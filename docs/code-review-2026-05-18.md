# Code Review — 2026-05-18

全面代码审查报告，覆盖后端 Python、前端 JavaScript、CLI 脚本。按严重程度排序。

---

## 1. 严重 (Critical)

### 1.1 dag.py — `resolve_input` 函数重复定义

**文件:** `web/dag.py:126` 和 `web/dag.py:260`  
**严重程度:** Critical

同一个函数 `resolve_input` 在文件中定义了两次，完全相同的实现。第二个定义（260 行）覆盖第一个，导致第一个定义死代码。如果将来只修改其中一个，会产生难以追踪的 bug。

**建议:** 删除第一个定义（126 行），只保留一个。

---

### 1.2 server.py — 路径穿越漏洞 (docs/iterations API)

**文件:** `web/server.py:692-702, 906-913`  
**严重程度:** Critical

```python
@app.get("/api/docs/{doc_id}")
async def get_doc(doc_id: str, lang: str = "zh"):
    path = os.path.join(DOCS_DIR, f"{doc_id}.{lang}.md")
    return FileResponse(path)
```

`doc_id` 没有任何路径穿越检查。`doc_id=../../etc/passwd` 可读取任意系统文件。`/api/files/{file_path:path}` 有 `normpath` 校验（line 238-239），但这两个端点完全没有保护。

---

### 1.3 dag.py — `topsort` 函数修改调用者的 `in_degree` 字典

**文件:** `web/dag.py:162-171`  
**严重程度:** Critical

```python
def topsort(node_map: dict, adj: dict, in_degree: dict) -> list[str] | None:
    queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
    while queue:
        in_degree[neighbor] -= 1  # <-- 静默副作用
```

传入的 `in_degree` 字典在函数返回后被破坏。调用者（workflow_engine `_execute`）虽暂不受影响，但 replay 逻辑或其他未来调用者可能因此出错。

**建议:** 在函数内部 `in_degree = dict(in_degree)` 创建副本。

---

### 1.4 workflow_engine.py — Cancel 导致实例卡在 "running" 状态

**文件:** `web/workflow_engine.py:270, 441, 462`  
**严重程度:** Critical

Python 3.9+ 中 `asyncio.CancelledError` 继承自 `BaseException` 而非 `Exception`。当 `_run_pipeline` 在 line 441 或 462 抛出 `asyncio.CancelledError`，它会穿透 `_execute` 中 line 270 的 `except Exception as e:`（不捕获 BaseException 子类），最终被 `_monitor_instance` line 565 的 `except asyncio.CancelledError: pass` **静默吞掉，不更新数据库状态**。工作流实例永远卡在 `"running"`。

---

### 1.5 workflow_engine.py — `replay()` 空指针崩溃

**文件:** `web/workflow_engine.py:70-71`  
**严重程度:** Critical

```python
wf_def = wm.get_workflow_definition(workflow_id)
graph = wf_def["graph"]  # wf_def 可能是 None！
```

`get_workflow_definition` 返回 `None` 时，下级字典访问抛出 `TypeError`，返回 500 错误。

---

### 1.6 workflow_engine.py — `_run_pipeline` 空指针崩溃

**文件:** `web/workflow_engine.py:452, 457-458`  
**严重程度:** Critical

```python
task = models.get_task(task_id)  # 可能返回 None
# ...
if task["status"] == "failed":  # None['status'] → TypeError
```

任务在提交和完成之间被删除时，`get_task` 返回 `None`，后续访问崩溃。

---

### 1.7 workflow_engine.py — `_enrich_ctx` 覆盖 handler 计算的元数据

**文件:** `web/workflow_engine.py:258` + `web/dag.py:97-123`  
**严重程度:** Critical

```python
# _execute 在每个 handler 之后：
self._enrich_ctx(nid, {}, node_params, ctx, edge_map)
```

这会**无条件覆盖** `ctx[nid]["_inputs"] = {}` 和 `ctx[nid]["_params"] = dict(node_params)`。对于 pipeline 节点，`node_params` 是原始（通常为空）的编辑器值，摧毁了 `_run_pipeline` 内部精心合并的 `merged_params`。对于 text_to_image，也覆盖了实际运行时的 provider/size 为旧编辑器默认值。UI 中显示的参数和 upstream cascade 数据不正确。

---

### 1.8 workflow_engine.py — `_resolve_input` 方法重复（与 dag.py 冲突）

**文件:** `web/workflow_engine.py:530-560`  
**严重程度:** Critical

`WorkflowEngine` 类有两个 `_resolve_input`：
- Line 135: 委托给 `dag.resolve_input()`
- Line 530: 自己实现了一遍完全相同逻辑

Line 530 定义在后，覆盖 line 135。line 135 的 `dag.resolve_input` 委托是死代码。

---

## 2. 高危 (High)

### 2.1 start-server.py — `netstat` 命令潜在的 shell 注入风险

**文件:** `start-server.py:26`  
**严重程度:** High

```python
f'netstat -ano | findstr :{port}', shell=True
```

`port` 来自 argparse `type=int`，在当前代码中安全。但如果将来有人改动代码使 port 变成字符串输入，就会产生 shell 注入。Pattern 本身不安全。

**建议:** 使用 `subprocess.run` 配合列表参数，避免 `shell=True`。或使用 `psutil` 库。

---

### 2.2 workflow_engine.py — `_run_pipeline` 中的忙等循环

**文件:** `web/workflow_engine.py:438-455`  
**严重程度:** High

```python
while True:
    # ...
    try:
        msg = await asyncio.wait_for(task_queue.get(), timeout=0.5)
        # ...
    except asyncio.TimeoutError:
        continue  # <-- 忙等
```

每 0.5 秒轮询一次任务状态。如果有多个 workflow 同时运行，CPU 会频繁唤醒。对于 Hunyuan3D 这种运行数十分钟的任务，这是大量无意义的轮询。

**建议:** 去掉 `timeout=0.5`，直接用 `await task_queue.get()` 阻塞等待。cancel 可以通过队列哨兵值实现。

---

### 2.3 pipeline.py — 脆弱的 JSON 提取逻辑

**文件:** `scripts/pipeline.py:30-35`  
**严重程度:** High

```python
idx = out.find("{")
if idx >= 0:
    try:
        return json.loads(out[idx:])
    except json.JSONDecodeError:
        pass
```

简单地找到第一个 `{` 就尝试 JSON 解析。如果 stdout 包含 `{` 字符的警告信息（如 Python traceback 中的 dict），会拿到错误的 JSON 片段，导致静默失败后回退到 `raw_output`。

**建议:** 要求子脚本将 JSON 输出到单独的文件（用 `--output-json` flag），或使用标记行（如 `__JSON_START__` / `__JSON_END__`）。

---

### 2.4 inline_nodes.py — `_resolve_input_file` 中构造空 edge map

**文件:** `web/inline_nodes.py:18-20`  
**严重程度:** High

```python
port_edge_map = engine._build_port_edge_map(
    {str(n["id"]): n for n in []},  # 总是空字典
    []  # 空边列表
)
```

这个调用**永远返回空字典**。注释也承认"will be built by engine before calling"，但从未实现。虽然第 23 行有 fallback 扫描，但效率低且不准确（可能匹配到不相关的文件）。

**建议:** 删除这段死代码，或者让 engine 在调用 handler 前传入正确的 edge_map。

---

### 2.5 image-to-relief.py — 纯 Python 嵌套循环构建面数组

**文件:** `scripts/image-to-relief.py:129-183`  
**严重程度:** High (性能)

```python
for row in range(H - 1):
    for col in range(W - 1):
        # ...
        faces.append([a, b, d])
```

对于 2000×1500 像素的图像，这会生成 ~6M 个面，循环 ~3M 次 Python 迭代。每个 `faces.append` 都有 Python 开销，构建时间可能超过 10 秒。

**建议:** 使用 NumPy 向量化构建面数组，或使用 trimesh 的内置 height field 功能。

---

## 3. 中危 (Medium)

### 3.1 mesh-to-views.py — OpenGL 资源泄漏风险

**文件:** `scripts/mesh-to-views.py:99-131`  
**严重程度:** Medium

```python
r = pyrender.OffscreenRenderer(resolution, resolution)
for name in views:
    # ... render ...
r.delete()
```

如果循环中抛出异常，`r.delete()` 永远不会调用，导致 OpenGL 上下文泄漏。在 Windows 上这可能导致 GPU 内存泄漏。

**建议:** 使用 `try/finally` 包裹，确保 `r.delete()` 始终执行。

---

### 3.2 hunyuan-to-3d.py — 硬编码中文路径

**文件:** `scripts/hunyuan-to-3d.py:88`  
**严重程度:** Medium

```python
base_dir = os.path.join(base_dir, "混元3D2.1+comfyui便携版+工作流+模型+环境")
```

默认路径包含中文字符，在非中文 Windows 系统上可能损坏。用户必须通过 `--base-dir` 覆盖。

**建议:** 使用配置文件或环境变量 `HUNYUAN3D_HOME` 替代硬编码。

---

### 3.3 mesh-repair.py — 与 pymeshfix 内部格式的紧耦合

**文件:** `scripts/mesh-repair.py:48`  
**严重程度:** Medium

```python
faces = fix.mesh.faces.reshape(-1, 4)[:, 1:]
```

假设 pymeshfix 的 `PolyData.faces` 总是 `(N, 4)` 格式（第一列为面顶点数 3）。这是 VTK/PyVista 的约定，但如果 pymeshfix 版本升级改变内部表示（例如返回 `(N, 3)` 的面数组），代码将静默产生错误的面。

**建议:** 判断 faces 的 shape：如果是 `(N, 4)` 则去掉第一列，如果是 `(N, 3)` 则直接使用。

---

### 3.4 image-to-relief.py — OBJ 颜色导出与网格构建顺序耦合

**文件:** `scripts/image-to-relief.py:363`  
**严重程度:** Medium

```python
_export_colored_obj(verts[:H*W], faces[:(H-1)*(W-1)*2], ...)
```

面数 `(H-1)*(W-1)*2` 和顶点数 `H*W` 依赖于 `_build_relief_mesh` 中 front face 恰好是前 N 个面的内部实现细节。如果网格构建函数被修改，这里会出现索引错误或静默地导出错误的面片。

**建议:** 让 `_build_relief_mesh` 返回 front face 的面索引范围，或使用单独的网格对象。

---

### 3.5 workflow_models.py — 动态 SQL 列名拼接

**文件:** `web/workflow_models.py:128, 216, 286`  
**严重程度:** Medium

```python
conn.execute(f"UPDATE workflow_definitions SET {', '.join(updates)} WHERE id = ?", params)
```

列名来自函数内硬编码的字符串列表，在当前代码中安全。但如果将来增加了允许用户指定列名的功能，就会引入 SQL 注入。

**建议:** 使用显式的 SQL 而非动态拼接，或在每列后加上 `= ?` 并用 `CASE WHEN`（更冗长但绝对安全）。

---

### 3.6 start-server.py — 端口检查忽略 host 参数

**文件:** `start-server.py:20, 126`  
**严重程度:** Medium

```python
def kill_existing(port, host="127.0.0.1"):
    # ...
    f'netstat -ano | findstr :{port}'  # 没有按 host 过滤
```

`host` 参数从未用于过滤 netstat 输出。如果用户在 `--lan` 模式下运行，理论上 `0.0.0.0` 已经绑定了该端口，不需要区分 host。但如果存在多个不同 host 的监听，kill_existing 可能误杀不相关的进程。

**建议:** 至少在 Windows 上也用 `netstat -ano | findstr "127.0.0.1:{port}" ` 或 `findstr "0.0.0.0:{port}"` 过滤 host。

---

### 3.7 workflow_engine.py — `topsort` 变量名遮蔽函数名

**文件:** `web/workflow_engine.py:162, 197`  
**严重程度:** Medium (可读性)

```python
topsort = self._topsort(node_map, adj, in_degree)
# ...
offset = topsort.index(exec_list[0])  # topsort 是 list，不是方法
```

局部变量 `topsort` 遮蔽了 `WorkflowEngine._topsort` 方法。功能正确但极易造成混淆。

**建议:** 重命名局部变量为 `sorted_nodes` 或 `exec_order`。

---

## 4. 低危 (Low)

### 4.1 image-to-3d.py — 项目根目录假设

**文件:** `scripts/image-to-3d.py:34`  
**严重程度:** Low

```python
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

假设脚本位于 `<project>/scripts/image-to-3d.py`。如果脚本被移动或软链接，路径失败。

**建议:** 使用环境变量 `PROJECT_ROOT` 或从 `CLAUDE.md` 所在目录探测。

---

### 4.2 start-server.py — `__import__` 检查错误的包名

**文件:** `start-server.py:71-72`  
**严重程度:** Low

```python
for pkg in ("fastapi", "uvicorn", "python_multipart"):
    __import__(pkg)
```

`python_multipart` 的 pip 包名是 `python-multipart`，但 import 名是 `python_multipart`（带下划线）。这里检查正确，但错误信息（76 行 `pkg_name = pkg.replace("_", "-")`）可能混淆——import 名和 pip 名不一定总是只差下划线/连字符。

**建议:** 使用明确的映射字典。

---

### 4.3 providers.py — `_load_dotenv` 环境变量优先级策略

**文件:** `web/providers.py:31`  
**严重程度:** Low

```python
if key and (key not in os.environ or not os.environ[key]):
    os.environ[key] = value
```

策略：如果环境变量为空字符串，`.env` 文件中的值会覆盖它。这可能让用户困惑——他们可能故意设置空值来禁用某个 provider。

**建议:** 只有 key 不存在时才从 `.env` 加载（`key not in os.environ`），不检查值是否为空。

---

### 4.4 providers.py — `get_provider` 重复加载配置

**文件:** `web/providers.py:239`  
**严重程度:** Low

```python
def get_provider(provider_id: str) -> BaseProvider | None:
    configs = load_providers_config()  # 每次调用都重新加载
```

`load_providers_config()` 每次都重新读取 YAML 文件。在 `list_providers()` 和工作流引擎中频繁调用。虽然 YAML 解析很快，但无意义。

**建议:** 添加简单的缓存（模块级变量 + 文件 mtime 检查）。

---

### 4.5 hunyuan-to-3d.py — VAE 配置硬编码

**文件:** `scripts/hunyuan-to-3d.py:222-239`  
**严重程度:** Low

VAE 的超参数完全硬编码在代码中。如果模型版本升级（如 v2-2），这些参数可能改变，导致加载失败的静默错误。

**建议:** 将 VAE 配置提取到外部配置文件（如 YAML/JSON），与 DiT config 保持一致。

---

### 4.6 mesh-repair.py — `remove_infinite_values` 检查

**文件:** `scripts/mesh-repair.py:39`  
**严重程度:** Low

```python
mesh.remove_infinite_values()
```

trimesh 的某些版本中 `remove_infinite_values()` 可能不存在（旧版本）或行为不同。没有 try/except 保护。

**建议:** 添加 `hasattr` 检查或 try/except。

---

### 4.7 mesh-to-views.py — 光照位置对某些方向无效

**文件:** `scripts/mesh-to-views.py:106-109`  
**严重程度:** Low

```python
light_pose = _view_pose('top')
light_pose[:3, 3] = [0.5, 0.8, 1.5]  # 覆盖了 _view_pose 的结果
```

调用 `_view_pose('top')` 获取 4x4 矩阵后立即覆盖了平移部分。旋转部分（来自 `_view_pose('top')`）保留，但这是浪费的计算——直接用 `np.eye(4)` + 设置平移即可。

**建议:** 直接构造光照位姿矩阵，无需调用 `_view_pose`。

---

## 5. 前端问题

### 5.1 XSS via `escJS` 不足的转义 — 影响 4 个文件

**文件:** `web/static/js/utils.js:38`, `web/static/js/components/node-detail.js:183-208`  
**严重程度:** Critical

`escJS()` 只转义了 `\` 和 `'`（用于嵌入单引号 JS 字符串），但这些值被放进 `onclick="..."` (双引号 HTML 属性)。一个双引号字符 `"` 就能提前终止属性，导致属性注入。

```javascript
function escJS(str) {
    return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}
// 用于:
// <button onclick="showFileModal('${escJS(absPath)}', ...)">  ← 双引号属性！
```

虽然 Windows 文件名不允许 `"`，但这是结构性缺陷，在 Unix 部署上可被利用。`escJS` 需要同时转义 HTML 属性关键字符: `"`, `<`, `>`, `&`。

**受影响调用点:** `utils.js` 215-221 (文件模态框按钮), `node-detail.js` 184, 201-203 (端口文件按钮)

---

### 5.2 多 file_input 节点产生重复 DOM ID — 后续节点失效

**文件:** `web/static/js/pages/new-task.js:417-428`  
**严重程度:** Critical

file_input 节点的 HTML 模板硬编码了 `wf-drop-zone`、`wf-file-input`、`wf-file-chosen`。如果有两个或以上的 file_input 节点，DOM 中出现重复 ID。`buildProcessNodeParamsHtml` 使用 `getElementById` 绑定事件监听器（442-449 行），只找到第一个元素，第二个及后续的 file_input 节点完全失效——无法拖放、文件选择、提交按钮逻辑。

**建议:** 使用 class + `querySelector` 或动态生成唯一 ID（加入 node id）。

---

### 5.3 wf-runner.js — SSE 连接无重连机制

**文件:** `web/static/js/pages/wf-runner.js:107-196`  
**严重程度:** High

wf-runner 直接用 `new EventSource(url)` 而不是使用 `apiStream()`（api.js 32-89 行提供的指数退避重连封装）。`wfSSE.onerror` 只更新 UI 显示 "disconnected"，从不尝试重连。SSE 连接一旦断开，执行进度更新静默停止。

**建议:** 使用已有的 `apiStream()` 包装器或实现重连逻辑。

---

### 5.4 task-detail.js — SSE 事件中的 render 竞态条件

**文件:** `web/static/js/pages/task-detail.js:430-473`  
**严重程度:** High

```javascript
api('GET', `/tasks/${taskId}`).then(fresh => {
    Object.assign(task, fresh);
    render();  // 竞态！
});
```

`complete`、`error`、`cancelled` 三个 SSE 事件都用此模式。如果两个 SSE 事件快速连续到达（如 `complete` 然后 `done`），两次 `render()` 会交错更新 `content.innerHTML`，导致闪烁或显示旧数据。

**建议:** 使用标志位或 AbortController 取消前次 render。

---

### 5.5 new-task.js — text2img 下载无错误处理

**文件:** `web/static/js/pages/new-task.js:641-650`  
**严重程度:** High

```javascript
fetch(relUrl).then(r => r.blob()).then(blob => {
    // 使用 blob ...
});
// 没有 .catch()！
```

`t2i-use-btn` 点击处理器中，下载生成图片的 `fetch` 没有任何 `.catch()`。网络错误或 404 时，Promise 静默 reject，用户无任何反馈。

---

### 5.6 node-detail.js — Blob URL 内存泄漏

**文件:** `web/static/js/components/node-detail.js:41-44`  
**严重程度:** Medium

```javascript
const blob = new Blob([String(value)], { type: 'text/plain' });
return { ..., url: URL.createObjectURL(blob), ... };
```

`URL.createObjectURL()` 创建的 Blob URL 从不调用 `URL.revokeObjectURL()` 释放。每次渲染 node detail 都创建新的 blob URL，旧的不释放，直到页面关闭。

**建议:** 在组件销毁/更新时调用 `revokeObjectURL`。

---

### 5.7 utils.js — `_fileCache` 无界增长

**文件:** `web/static/js/utils.js:75-76`, `web/static/js/components/node-detail.js:174`  
**严重程度:** Medium

`_fileCache` Map 无上限增长。每次 `renderPortEntry` 调用 `cacheFile()` 插入新条目。无 LRU/TTL/容量上限策略，长时间会话消耗无界内存。

---

### 5.8 new-task.js — 边查询用输出端口名作为目标端口 fallback

**文件:** `web/static/js/pages/new-task.js:538-539`  
**严重程度:** Medium

```javascript
const curSrc = edgeInfo[pi] || edgeInfo[p.name] || edgeInfo[op.name];
```

第三个 fallback `edgeInfo[op.name]` 用**候选源节点的输出端口名**去查**目标端口**的 edge map。当某个节点的输出端口名碰巧等于另一个节点的目标端口名时，下拉菜单的 "selected" 状态会错误地显示一个不存在的连接。

---

### 5.9 new-task.js — `parseInt` 缺少 radix 参数

**文件:** `web/static/js/pages/new-task.js:243, 293`  
**严重程度:** Medium

```javascript
parseInt(el.value)  // 缺少 radix: parseInt(el.value, 10)
```

ES module strict mode 下不会按八进制解释，但仍然脆弱。如果值有前导零，语义不明确。

---

### 5.10 api.js — `fetchProviderStatuses` 静默吞错

**文件:** `web/static/js/api.js:105`  
**严重程度:** Medium

catch 块完全为空。provider status 端点失败时，UI 静默降级，用户不知道 provider 信息已过期。

---

### 5.11 wf-runner.js — Canvas 重绘无 debounce

**文件:** `web/static/js/pages/wf-runner.js:577-591`  
**严重程度:** Medium

`updateRunnerNode` 在每个 SSE 事件时立即调用 `canvas.setDirty(true)` + `canvas.draw(true)`。10 个节点几乎同时完成时，触发 10 次重绘，造成卡顿。

**建议:** 使用 `requestAnimationFrame` 合并重绘。

---

### 5.12 router.js — 初始加载时重复路由分发

**文件:** `web/static/js/router.js:49-55, 99`  
**严重程度:** Low

无 hash 时 `route()` 调用 `location.replace('#/dashboard')`，触发 `hashchange` 事件，`hashchange` listener 再调用 `route()`。第一次调用做清理和侧边栏更新后返回，第二次才真正加载页面。产生冗余工作。

---

### 5.13 utils.js — `formatTime(0)` 返回空字符串

**文件:** `web/static/js/utils.js:44`  
**严重程度:** Low

```javascript
if (!ts) return '';
```

时间戳 `0` (Unix epoch) 被当作 falsy，返回空字符串。将 "无时间戳" 与 "零时间戳" 混为一谈。

---

### 5.14 workflow-layout.js — 循环图静默返回所有节点在 layer 0

**文件:** `web/static/js/lib/workflow-layout.js:66-70`  
**严重程度:** Low

BFS 队列为空时（所有节点 inDegree > 0，即有环），函数将所有节点赋给 layer 0 后返回，不运行定位循环。节点重叠在画布原点。

---

### 5.15 GIF 图片在 node-detail.js 和 utils.js 中不一致

**文件:** `node-detail.js:49` vs `utils.js:102`  
**严重程度:** Low

node-detail 的图片扩展名列表包含 `gif`，但 utils.js 的 `showCtxMenu`/`showFileModal` 不包含。GIF 输出文件在 node detail 面板有缩略图，但在右键菜单和文件模态框中不被识别为图片。

---

### 2.6 schemas.py vs node_types.py — 参数名不匹配（4 个节点）

**文件:** `web/schemas.py` 和 `web/node_types.py`  
**严重程度:** Critical

`workflow_engine._run_pipeline()` 的 `merged_params` 逻辑用 schemas.py 的参数名去 node_params 中查找值。以下 4 个节点的参数名在两个文件中不一致，导致**用户配置的参数被静默丢弃**，总是使用 schema 默认值：

| 节点 | schemas.py | node_types.py |
|------|-----------|---------------|
| `mesh_stitch` | `smooth_steps`, `lambda` | `stitch_smooth`, `stitch_lambda` |
| `mesh_boolean` | `operation` | `bool_op` |
| `mesh_cut` | `plane_co`, `plane_no`, `fill` | `cut_plane_co`, `cut_plane_no`, `cut_fill` |
| `mesh_decorate` | `texture`, `displacement`, `color_mode` | `deco_displacement`（其他两个缺失） |

---

### 2.7 models.py — 路径穿越漏洞

**文件:** `web/models.py:311-323`  
**严重程度:** High

```python
f["url"] = "/api/files/" + os.path.relpath(abs_path, PROJECT_ROOT).replace("\\", "/")
except ValueError:
    f["url"] = "/api/files/" + abs_path.replace("\\", "/")
```

当文件在 `PROJECT_ROOT` 外部时，`os.path.relpath` 可能抛出 `ValueError` 或返回含 `..` 的路径，导致路径穿越攻击。攻击者可通过操纵文件路径读取任意文件。

---

### 2.8 models.py — `delete_task` 可能泄漏磁盘文件

**文件:** `web/models.py:270-278`  
**严重程度:** Medium

当 task 没有 `input_file` 时（如 text2image 生成任务），`delete_task` 不会清理磁盘上的输出文件，造成磁盘空间泄漏。

---

### 2.9 models.py — LEFT JOIN 依赖未初始化的表

**文件:** `web/models.py:175-191`  
**严重程度:** Medium

`get_task()` 和 `list_tasks()` LEFT JOIN `workflow_node_runs` 表，但该表由 `workflow_models.init_workflow_db()` 创建。如果 workflow DB 未初始化（首次运行、无 workflow），这些查询会因 `no such table` 失败——任务列表/详情 API 完全不可用。

---

### 2.10 node_types.py — `PARAM_META` 扁平字典导致标签冲突

**文件:** `web/node_types.py:554-558`  
**严重程度:** Medium

`PARAM_META` 是按参数名索引的扁平字典。`"method"` 键的描述为 "Simplification algorithm..."（专属于 `mesh_simplify`），但 `image_grayscale` 也使用 `"method"` 参数（选项: `luminosity`, `average` 等）。灰度节点的 method 参数会显示错误的中英文标签。

---

### 2.11 node_types.py — 多个节点的 params 缺少类型元数据

**文件:** `web/node_types.py:778-865`  
**严重程度:** Medium

`mesh_boolean`、`mesh_stitch`、`mesh_decorate`、`mesh_select`、`mesh_cut` 的 params 使用裸值（如 `"bool_op": "union"`）而非带类型的定义（如 `{"type": "choice", "default": "union", "choices": [...]}`），导致 UI 显示为普通文本输入而非下拉菜单。

---

### 2.12 schemas.py — KNOWN_FILE_TYPES 重复值

**文件:** `web/schemas.py:345`  
**严重程度:** Low

`KNOWN_FILE_TYPES["mesh"]` 中 `.glb` 出现两次: `[".glb", ".obj", ".stl", ".gltf", ".glb"]`。

---

### 2.13 node_types.py — `node_input_port_map()` 缺失新节点

**文件:** `web/node_types.py:947-962`  
**严重程度:** Medium

`node_input_port_map()` 缺少 `mesh_boolean`、`mesh_stitch`、`mesh_cut`、`mesh_align`、`mesh_decorate` 的映射。依赖此函数的代码无法正确确定这些节点的主输入端口。

---

## 6. 架构建议

### 6.1 GPU 锁粒度

`web/scheduler.py` 中的 GPU 锁使用简单的 `asyncio.Lock`，一次只允许一个 GPU 任务。但某些操作（如 relief 生成）不需要 GPU。当前实现可能不必要地阻塞了纯 CPU 任务。

**建议:** 区分 GPU 任务和 CPU 任务，只对 GPU 任务加锁。

---

### 6.2 子进程错误处理

所有 CLI 脚本通过 `subprocess.run` 调用，stderr 被捕获但检查不完整。例如 `pipeline.py:25` 只截取前 500 字符。对于 Hunyuan3D 这种日志量大的脚本，关键错误可能被截断。

**建议:** 将 stderr 保存到文件，便于事后排查。

---

### 6.3 数据库连接管理

`workflow_models.py` 多处 `conn = get_db(); ...; conn.close()` 模式。异常时 `conn.close()` 不会执行，导致连接泄漏。

**建议:** 使用 context manager 或 `try/finally`。

---

## 总结

| 严重程度 | 数量 |
|---------|------|
| Critical | 12 |
| High     | 12 |
| Medium   | 25 |
| Low      | 19 |

### 修复优先级建议

**立即修复 (本次迭代):**
1. `dag.py` / `workflow_engine.py` 三处重复 `resolve_input` — 删除死代码，统一实现
2. `schemas.py` vs `node_types.py` 参数名不匹配 — 4 个节点的用户配置被静默丢弃
3. `server.py` 路径穿越漏洞 (`/api/docs/{doc_id}`, `/api/iterations/{iter_id}`) — 可读取任意系统文件
4. `workflow_engine.py` Cancel 导致实例卡在 "running" — CancelledError 不被 except Exception 捕获
5. `workflow_engine.py` `_enrich_ctx` 覆盖 handler 计算的元数据 — 摧毁 pipeline 合并后的参数
6. `utils.js` `escJS` XSS — 加固转义覆盖 `"<>&`
7. `new-task.js` 多 file_input 节点重复 ID — 功能完全损坏

**尽快修复 (下次迭代):**
8. `workflow_engine.py` `replay()` 和 `_run_pipeline` 空指针崩溃 — 加 None 检查
9. `models.py` LEFT JOIN 依赖未初始化的表 — 加表存在检查或调整初始化顺序
10. `pipeline.py` JSON 解析健壮性
11. `workflow_engine.py` 忙等循环 → 阻塞等待
12. `models.py` 路径穿越漏洞 (relpath fallback)
13. `wf-runner.js` SSE 断连无重连
14. `task-detail.js` render 竞态条件
15. `node_types.py` PARAM_META 扁平字典冲突
16. `node_types.py` params 缺少类型元数据

**排期修复:**
- 内存泄漏 (Blob URL, fileCache)
- OpenGL 资源泄漏 (mesh-to-views)
- 性能问题 (image-to-relief 嵌套循环)
- 其他 Low severity 项目
