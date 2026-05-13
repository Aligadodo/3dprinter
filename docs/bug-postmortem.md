# Bug Post-Mortem Report — 2026-05 文件操作与节点展示修复

## 概述

本次修复涉及两大类共 9 个 bug：**节点详情展示问题**（3 个）和**文件操作按钮失效**（6 个）。根因分析覆盖前端路径解析、字符串转义、HTTP 错误处理、后端阻塞调用等层面。

---

## Bug 列表与根因分析

### 1. 工作流节点显示为"无输入根节点"

**症状**：任务运行页面的每个节点都显示 "No inputs (root node)"，即使有上游连接。

**根因**：LiteGraph 的边（edge）使用数值 slot index（0, 1, 2...）而非端口名称（"image", "stl", "file"）。代码直接用 `e.sourcePort`（整数）去查找 `ctx[sourceNodeId][sourcePort]`，无法匹配到端口名。

**修复**：用 `ntMap` 中的 `PortSpec` 定义将 slot index 翻译为端口名称：
```javascript
const srcPortName = srcNT.outputs[e.sourcePort]?.name;
const tgtPortName = nt.inputs[e.targetPort]?.name;
```

**涉及文件**：`task-detail.js`、`wf-runner.js`

---

### 2. 工作流任务页存在重复信息

**症状**：节点卡片已显示完整信息，但页面底部还有独立的"任务结果"和"输出文件"区块，造成重复。

**根因**：`buildCompletedResult`/`buildFailedResult` 和 `buildOutputFiles` 函数独立于节点卡片渲染，用于非工作流任务。切换到工作流上下文时，这些函数的结果依然被追加到 HTML。

**修复**：在工作流上下文路径中删除独立的结果和输出文件区块渲染，信息统一由 `renderNodeDetailPanel` 在节点卡片中展示。

**涉及文件**：`task-detail.js`

---

### 3. 产出物文件下载按钮不可用

**症状**：点击下载按钮提示"无法从该网站下载文件"，所有文件下载均失败。

**根因**：三个递进问题：
1. **`fileToUrl()` 路径匹配顺序错误**：DB 存储的路径是 `D:\projects\3dprint\output\tasks\...`，`fileToUrl` 用 `/tasks/` 匹配时先匹配到 `output` 之后的位置，导致 `/api/files/` 后的路径缺少 `output/` 前缀。应优先匹配 `/output/tasks/`。
2. **`fileMeta()` 对纯文本值无处理**：prompt 文本等非文件路径的值直接传给 `fileToUrl()`，生成无效的 API URL。
3. **DB 中的 `path` 字段为 Windows 绝对路径**：`fileToUrl()` 未正确处理以盘符开头的绝对路径。

**修复**：
- 调整 `fileToUrl()` 匹配顺序（`/output/tasks/` → `/tasks/` → `/output/`）
- `fileMeta()` 增加文本值检测，生成 Blob URL
- `renderNodeDetailPanel()` 使用 API 返回的 `url` 和 `filename` 字段

**涉及文件**：`node-detail.js`

---

### 4. "打开文件"按钮（📄）无反应

**症状**：点击端口条目上的 📄 按钮没有任何反应。

**根因**：动态 import 路径为相对路径 `import('../utils.js')`。在 HTML onclick 属性中，动态 `import()` 的模块路径相对于**文档 URL**（`http://127.0.0.1:8080/`）而非**脚本 URL**（`/static/js/components/node-detail.js`），导致 `../utils.js` 解析为 `http://127.0.0.1:8080/utils.js` → 404。import 失败后 `.then()` 回调不执行，且无 `.catch()`，表现为静默失败。

**修复**：所有 inline 动态 import 改为绝对路径 `/static/js/utils.js`。

**涉及文件**：`node-detail.js`、`utils.js`、`task-detail.js`、`file-browse.js`、`wf-runner.js`

---

### 5. "打开文件所在目录"按钮（📂）无反应

**症状**：点击 📂 按钮同样无反应。

**根因**：两个叠加问题：
1. **同 Bug #4 的 import 路径问题** — 如果是通过模块函数调用
2. **Windows 路径反斜杠被 JS 转义**：`filePath` 直接嵌入到 onclick 的字符串字面量中，如 `'D:\projects\3dprint\output\tasks\...'`。反斜杠 `\t`、`\f`、`\n` 被 JavaScript 解释为转义序列（制表符、换页符、换行符），路径被严重破坏，发送到 `/api/open-path` 后端后返回 404。

**修复**：
- 添加 `escJS()` 函数：先 `\` → `\\`，再 `'` → `\'`
- 所有嵌入 onclick JS 字符串的路径值都经 `escJS()` 处理
- 将 `import()` 改为绝对路径

**涉及文件**：`node-detail.js`、`utils.js`

---

### 6. 文件详情弹窗底部按钮全部无反应

**症状**：打开文件详情弹窗后，弹窗底部的"打开文件"、"下载"、"复制路径"、"打开所在目录"、"在命令行打开"按钮全部无反应。

**根因**：多个问题叠加：

| 按钮 | 实现方式 | 问题 |
|------|----------|------|
| 打开文件 | `import('/static/js/utils.js').then(m=>m.handleCtxAction('open',m.modalFile()))` | 无 `.catch()`，import 失败或 `modalFile()` 返回 null 时静默失败 |
| 下载 | 同上，调用 `handleCtxAction('download',...)` | 同上 |
| 复制路径 | 同上，调用 `handleCtxAction('copypath',...)` | 同上 |
| 打开所在目录 | `fetch('/api/open-path', ...)` | 无 `.then()` 检查 `response.ok`，HTTP 4xx/5xx 被静默忽略；无成功反馈 |
| 在命令行打开 | 同上 | 同上 |

此外，`handleCtxAction` 中 'open' 动作对图片文件调用 `showFileModal(file)` 只是重新渲染同一个弹窗，形成无意义的循环。

**修复**：重写弹窗底部按钮，改为直接内联实现：
- **打开文件**：直接 `fetch('/api/open-path', {action:'open'})` 调用后端打开文件
- **下载**：直接创建 `<a>` 元素设置 `href` 和 `download` 触发下载
- **复制路径**：直接调用 `navigator.clipboard.writeText()`
- **打开所在目录/命令行**：直接 `fetch('/api/open-path', ...)` 并检查 `response.ok` + 成功/错误 toast

所有 fetch 调用添加 `response.ok` 检查和 `.catch()` 错误处理，所有嵌入值经 `escJS()` 转义，成功操作显示 toast 反馈。

**涉及文件**：`utils.js`

---

### 7. `os.startfile()` 阻塞事件循环

**症状**：后端 `/api/open-path` 的 `action: 'open'` 请求超时（curl --max-time 10 返回 exit code 28）。

**根因**：`server.py` 中 `async def open_path` 直接调用 `os.startfile(full_path)`。虽然文档声称 `os.startfile()` 异步返回，但在本机环境中（Windows 11 + 特定文件关联），该调用阻塞等待关联程序处理完毕才返回，导致 FastAPI 事件循环被阻塞。

**修复**：将 `os.startfile(full_path)` 替换为 `subprocess.Popen(["cmd", "/c", "start", "", full_path])`，利用 `start` 命令的天然异步特性。

**涉及文件**：`server.py`

---

### 8. 上下文菜单与端口条目点击也有同样的 import 路径问题

**症状**：右键菜单和端口条目整体点击（`onclick` 和 `oncontextmenu`）同样使用相对路径 `import('../utils.js')`。

**根因**：与 Bug #4 相同 — relative import 在 inline event handler 中按文档 URL 解析。

**修复**：所有 inline event handler 中的动态 import 路径统一改为绝对路径。

**涉及文件**：`node-detail.js`、`task-detail.js`、`file-browse.js`、`wf-runner.js`

---

### 9. workflow runner 重放按钮同样失效

**症状**：工作流运行页面的 Replay 按钮和下载全部输出按钮无反应。

**根因**：`wf-runner.js` 中 `import('../pages/wf-runner.js')` 同样为相对路径。

**修复**：改为 `import('/static/js/pages/wf-runner.js')`。

---

## 根因分类总结

| 类别 | 数量 | 典型表现 |
|------|------|----------|
| **路径解析错误** | 3 | import 相对路径、fileToUrl 匹配顺序、slot index → port name |
| **字符串转义缺失** | 2 | Windows 路径反斜杠嵌入 JS 字符串、HTML 属性中的 JS 字面量 |
| **错误处理缺失** | 2 | import 无 .catch()、fetch 无 response.ok 检查 |
| **阻塞调用** | 1 | os.startfile() 在 async handler 中同步阻塞 |
| **架构冗余** | 1 | 独立渲染函数与节点卡片重复展示 |

---

## 测试覆盖

本次修复新增 16 个 API 测试用例（`tests/test_api.py` → `test_file_actions`）：

| 端点 | 测试场景 | 预期 |
|------|----------|------|
| `GET /api/files/{path}` | 已知文件 | 200 + 正确 content-type |
| | 路径穿越 | 403 |
| | 不存在文件 | 404 |
| `POST /api/open-path` | 打开文件 | 200 |
| | 打开文件所在目录（文件） | 200 |
| | 打开文件所在目录（目录） | 200 |
| | 在命令行打开 | 200 |
| | 相对路径 | 200 |
| | 空路径 | 400 |
| | 项目外路径 | 403 |
| | 不存在路径 | 404 |
| | 未知 action | 400 |

测试全量通过：**151 API + 13 引擎 = 164 tests, 0 failures**。

---

## 经验教训

1. **Inline event handler 中的相对 import 不可靠**：HTML onclick 属性中的 `import()` 按文档 URL 解析，非脚本 URL。一律使用绝对路径 `/static/js/...`。

2. **Windows 路径必须先转义再嵌入 JS 字符串**：反斜杠是 JS 转义字符，必须 `\` → `\\` 后再嵌入字符串字面量。封装 `escJS()` 统一处理。

3. **fetch 响应的 `ok` 检查不可省略**：`fetch()` 仅在网络错误时 reject，HTTP 4xx/5xx 会正常 resolve。业务逻辑必须检查 `response.ok`。

4. **动态 import 必须添加 `.catch()`**：inline handler 中无法使用 try/catch，`.then()` 后必须跟 `.catch()`。

5. **文件打开使用 `cmd /c start` 代替 `os.startfile()`**：后者可能阻塞事件循环，前者天然异步。

6. **LiteGraph 使用数值 slot index，应用层需要端口名称映射**：必须维护 `node_types` 的 PortSpec 作为翻译层。
