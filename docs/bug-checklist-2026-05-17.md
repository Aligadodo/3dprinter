# 前端 Bug 清单

> 审计日期: 2026-05-17 | 范围: `web/static/js/` 全部文件 | 共 17 项

---

## 🔴 CRITICAL

### Bug #1 — wf-runner.js — `graphNodes` 未定义导致 DAG 渲染崩溃

- **文件:** `web/static/js/pages/wf-runner.js`
- **行号:** ~248
- **类型:** 未声明变量 / ReferenceError
- **描述:** `buildRunnerDAG` 中调用了 `getNodeDisplayLabel(n, nt, graphNodes, ntMap)`，但 `graphNodes` 在该函数作用域内从未声明。ES module 严格模式下抛出 `ReferenceError`，外层 try/catch 捕获后 DAG 画布渲染失败。
- **影响:** 工作流运行页 DAG 可视化完全不显示。
- **状态:** ✅ 已修复

---

### Bug #2 — file-browse.js — `cacheFile()` 每次生成新 ID，批量下载/复制永远失败

- **文件:** `web/static/js/pages/file-browse.js`
- **行号:** ~63, ~75
- **类型:** 逻辑错误
- **描述:** 渲染时 `cacheFile(f)` 生成 ID 存入 `selected` Set；批量操作时再次调用 `cacheFile(f)` 生成的是**新 ID**（`_fileSeq` 递增），`selected.has(newFid)` 永远为 `false`。批量下载和批量复制路径功能完全失效。
- **影响:** 文件浏览页"下载选中"和"复制路径"按钮无任何效果。
- **状态:** ✅ 已修复

---

## 🟠 HIGH

### Bug #3 — file-browse.js — `selected`/`updateBatchBar` 在全局 onclick 中不可访问

- **文件:** `web/static/js/pages/file-browse.js`
- **行号:** ~87
- **类型:** 作用域错误 / ReferenceError
- **描述:** "Clear" 按钮使用内联 `onclick="...selected.clear();updateBatchBar()"`。内联 onclick 在全局作用域执行，无法访问模块闭包内的 `let`/`const` 变量。点击清除按钮抛出 ReferenceError 且无效果。
- **影响:** 文件浏览页"清除选择"按钮失效。
- **状态:** ✅ 已修复

---

### Bug #4 — new-task.js — 表单校验完全跳过

- **文件:** `web/static/js/pages/new-task.js`
- **行号:** ~120, ~187
- **类型:** DOM 选择器不匹配
- **描述:** 流水线任务参数字段用 `<div class="form-row">` 包裹，但 `validateField()` 通过 `el.closest('.form-group')` 查找父容器。由于 `.form-group` 不存在，`closest()` 永远返回 `null`，函数直接 `return true` 跳过所有校验（必填检查、数值范围检查等）。
- **影响:** 用户可以提交空必填字段、超出范围的数值而不被拦截。
- **状态:** ✅ 已修复

---

### Bug #5 — workflows.js — XSS：工作流名称注入 onclick

- **文件:** `web/static/js/pages/workflows.js`
- **行号:** ~37
- **类型:** XSS 安全漏洞
- **描述:** `onclick="...deleteWF('${wf.id}','${(wf.name||'').replace(/'/g,"\\'")}')"` 只转义了单引号，双引号可破坏 HTML 属性。且名称随后传入 `confirm.js` 的 `showConfirm` 直接拼入 `innerHTML`。
- **影响:** 恶意工作流名称可执行任意 JavaScript。
- **状态:** ✅ 已修复

---

### Bug #6 — confirm.js — `message` 参数直接插入 innerHTML

- **文件:** `web/static/js/components/confirm.js`
- **行号:** ~17
- **类型:** XSS 安全漏洞
- **描述:** `showConfirm(title, message)` 中 `message` 不经 `escHtml` 转义直接插入 `innerHTML`。所有调用方传入的 message 如果包含 HTML/script 标签，将被执行。
- **影响:** 多处确认弹窗存在 XSS 注入风险。
- **状态:** ✅ 已修复

---

## 🟡 MEDIUM

### Bug #7 — wf-editor.js — 内存泄漏：window resize 监听器未移除

- **文件:** `web/static/js/pages/wf-editor.js`
- **行号:** ~334-337
- **类型:** 内存泄漏
- **描述:** 每次进入工作流编辑器，`initLiteGraph()` 挂一个新的 `window.resize` 事件监听器。离开页面时 `_pageCleanup` 未移除监听器。累积的旧监听器引用已置 null 的 `wfCanvas`，每次窗口调整大小都抛出 TypeError。
- **影响:** 反复进出编辑器后性能下降，控制台报错累积。
- **状态:** ✅ 已修复

---

### Bug #8 — task-detail.js — `f.path` 为 null 时 `.split()` 报 TypeError

- **文件:** `web/static/js/pages/task-detail.js`
- **行号:** ~351 (standalone 任务 `buildOutputFiles`)
- **类型:** 空值安全
- **描述:** `const fileName = f.filename || f.path.split(/[\\/]/).pop();` — 如果后端返回的 output file 条目只有 URL 没有 path，`f.path` 为 `null`/`undefined`，`.split()` 抛出 TypeError。
- **影响:** 特定条件下任务详情页渲染崩溃。
- **状态:** ✅ 已修复

---

### Bug #9 — api.js — provider 状态缓存永久化

- **文件:** `web/static/js/api.js`
- **行号:** ~95-103
- **类型:** 逻辑错误
- **描述:** `fetchProviderStatuses()` 首次请求失败后，`_providerStatuses` 被设为 `{}`（空对象缓存）。后续所有调用命中缓存直接返回 `{}`，永远不会重试。必须刷新页面才能重新获取。
- **影响:** 文生图 provider 不可用状态被永久化。
- **状态:** ✅ 已修复

---

### Bug #10 — wf-editor.js — 绕过 litegraph-adapter 安全层

- **文件:** `web/static/js/pages/wf-editor.js`
- **行号:** ~165
- **类型:** 架构违规
- **描述:** 模板加载函数直接调用 `wfGraph.clear()`，而非 `clearGraph(wfGraph)`（来自 `litegraph-adapter.js`）。adapter 的 `clearGraph` 包含 LiteGraph 0.7.14 的 bug 修复（`_links` 重新初始化），跳过它可能导致后续连线操作遇到 `null` 引用。
- **影响:** 加载模板后可能无法正常连线。
- **状态:** ✅ 已修复

---

### Bug #11 — dashboard.js — 重叠的 async refresh 竞争

- **文件:** `web/static/js/pages/dashboard.js`
- **行号:** ~219
- **类型:** 竞态条件
- **描述:** 30 秒间隔轮询 `setInterval(refresh, 30000)`，`refresh` 是 async 函数。如果某次刷新超过 30 秒，下一次 interval 触发时前一次尚未完成，可能导致 DOM 重写交错。
- **影响:** 慢网络下工作台展示可能错乱。
- **状态:** ✅ 已修复

---

## 🔵 LOW

### Bug #12 — wf-runner.js — 死代码中 CSS 选择器写错

- **文件:** `web/static/js/pages/wf-runner.js`
- **行号:** ~469 (`refreshNodeTab`)
- **类型:** 死代码
- **描述:** `document.querySelector('#wf-tab-overview .wf-node-card:nth-child(...)')` 选择器写错，实际 CSS class 为 `.wf-overview-card`。该函数目前体为空（只有注释），但如果后续激活将静默失效。
- **影响:** 无实际影响（死代码），仅代码质量问题。
- **状态:** ✅ 已修复

---

### Bug #13 — task-detail.js — "发送到工作流"节点类型缺少 `wf_` 前缀

- **文件:** `web/static/js/pages/task-detail.js`
- **行号:** ~387
- **类型:** 逻辑错误
- **描述:** `{ type: 'output_file', ... }` 创建工作流时未加 `wf_` 前缀。编辑器加载此工作流时，节点类型查找 `wf_output_file` 匹配不上 `output_file`，节点可能无法渲染。
- **影响:** "发送到工作流"创建的工作流在编辑器中节点可能显示异常。
- **状态:** ✅ 已修复

---

### Bug #14 — wf-runner.js — 未使用的 import

- **文件:** `web/static/js/pages/wf-runner.js`
- **行号:** ~4
- **类型:** 代码清理
- **描述:** `import { escHtml, toast, showImageModal } from '../utils.js'` 中 `showImageModal` 从未被使用。
- **影响:** 无功能影响，增加少许打包体积。
- **状态:** ✅ 已修复

---

### Bug #15 — 多文件 — 工具函数重复定义

- **文件:** `wf-editor.js`, `wf-runner.js`, `task-detail.js`, `new-task.js`
- **类型:** 代码重复
- **描述:**
  - `getBilingualLabel` 在 wf-editor.js、wf-runner.js、task-detail.js 各定义一次
  - `_isTypeCompatible` 在 wf-editor.js、new-task.js 各定义一次
- **影响:** 修改时容易漏改，行为可能逐渐分化。
- **状态:** ✅ 已修复

---

### Bug #16 — wf-editor.js — 模板标题硬编码

- **文件:** `web/static/js/pages/wf-editor.js`
- **行号:** ~158-161
- **类型:** 硬编码
- **描述:** 模板预设标题如 `'文件输入 File Input #1'` 硬编码，未使用 `generateNodeTitle()` 函数。如果标题格式变更，需同时修改多处。
- **影响:** 维护性差，编号可能与已有节点冲突。
- **状态:** ✅ 已修复

---

### Bug #17 — wf-editor.js — 脆弱的空值守卫

- **文件:** `web/static/js/pages/wf-editor.js`
- **行号:** ~856-863 (`showRunParamsDialog`)
- **类型:** 代码健壮性
- **描述:** `rp-drop-zone`、`rp-file-input` 元素仅在没有 `file_input` 节点时不存在，守卫 `if (rpDrop && rpFileInput)` 正确但依赖渲染条件匹配。后续 `updateRPFile()` 也引用 `rp-file-chosen` 元素，同样依赖此守卫不崩溃。
- **影响:** 目前无 bug，但如果渲染逻辑变更可能暴露。
- **状态:** ✅ 已修复

---

## 统计

| 严重度 | 数量 |
|--------|------|
| CRITICAL | 2 |
| HIGH | 4 |
| MEDIUM | 5 |
| LOW | 6 |
| **总计** | **17** |
