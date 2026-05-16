# 工作流编辑器 Bug 复盘分析报告

**日期**: 2026-05-15  
**严重程度**: 🟡 中（功能阻断，无数据丢失）  
**涉及文件**: `web/static/js/pages/wf-editor.js`  
**影响范围**: 工作流编辑器 — 模板加载、组件拖拽、画板渲染

---

## 一、故障概述

用户在使用工作流编辑器时遇到以下症状：

| 症状 | 实际表现 | 控制台报错 |
|------|---------|-----------|
| 点击模板只显示 1 个节点 | 模板定义使用不存在的节点类型名，只有 `wf_file_input` 能正确创建 | `Cannot set properties of undefined` (litegraph.js:1286) |
| 拖拽组件到画板不显示 | 级联故障：LiteGraph 内部状态损坏后画板渲染失败 | `getBounding is not a function` (litegraph.js:7632) |
| 点击节点无详情 | `_links` 未初始化导致 forEach 崩溃 | `Cannot read properties of undefined (reading 'forEach')` (wf-editor.js:408/426) |
| Fit 按钮无效 | 调用了 LiteGraph 中不存在的方法 | `fitToContent is not a function` (wf-editor.js:194) |

---

## 二、根因分析

### Bug 1: 模板节点类型名不匹配 🔴 核心原因

**代码位置**: `wf-editor.js:82-89`（`_wfTemplate` 函数内的 templates 对象）

```javascript
// ❌ 修复前 — 类型名不存在于 node_types.py
wf_generate_relief  → createLiteGraphNodeClass 查找 'generate_relief' → null，节点被静默跳过
wf_text2img         → createLiteGraphNodeClass 查找 'text2img' → null
wf_3dgenerate       → createLiteGraphNodeClass 查找 '3dgenerate' → null

// ✅ 修复后 — 使用正确的节点类型名
wf_relief           → createLiteGraphNodeClass 查找 'relief' → NodeType 找到
wf_text_to_image    → createLiteGraphNodeClass 查找 'text_to_image' → NodeType 找到
wf_triposr          → createLiteGraphNodeClass 查找 'triposr' → NodeType 找到
```

**根本原因**: 模板定义中的类型名是手工编写的字符串常量，与 `node_types.py` 中注册的类型 ID 不一致。两者之间没有任何编译时或运行时验证，导致不匹配被静默忽略。

### Bug 2: `wfGraph._links` 未初始化

**代码位置**: `wf-editor.js:408, 426, 531`（`buildUpstreamOptions`、`buildOutputConnections`、`_wfInspChange`）

LiteGraph 0.7.14 的 `LGraph` 构造函数或 `clear()` 方法在某些情况下不会初始化 `_links` 为空数组。代码直接调用 `wfGraph._links.forEach()` 而不做空值检查。

```javascript
// ❌ 修复前
wfGraph._links.forEach(link => { ... });

// ✅ 修复后
(wfGraph._links||[]).forEach(link => { ... });
```

**根本原因**: 对外部库（CDN 加载的 LiteGraph）的内部状态假设过于乐观，缺少防御性编程。

### Bug 3: `fitToContent` 不存在于 LiteGraph 0.7.14

**代码位置**: `wf-editor.js:194`

LiteGraph 0.7.14 的 `LGraphCanvas` 没有 `fitToContent` 方法，正确的方法是 `zoomToFit`。

**根本原因**: 开发时可能参考了不同版本（ComfyUI fork）的 API，但实际部署的是 npm 上的 `litegraph.js@0.7.14`（jagenjo 原始版本），API 有差异。

### Bug 4: 链接创建使用了错误的 API 格式

**代码位置**: `wf-editor.js:108, 532`（模板加载和 inspector 连接变更）

```javascript
// ❌ 修复前 — 使用了不被 LiteGraph 识别的属性名
wfGraph.add({source: srcNode, target: tgtNode, sourcePort: srcOut, targetPort: tgtIn});

// ✅ 修复后 — 使用标准 LiteGraph API
srcNode.connect(srcOut, tgtNode, tgtIn);
```

LiteGraph 的 `LGraph.add` 方法对于链接对象期望的属性名是 `origin_id` / `origin_slot` / `target_id` / `target_slot`，而非 `source` / `sourcePort` / `target` / `targetPort`。传入不认识的属性名后，LiteGraph 可能错误地将该对象当作节点处理，导致后续渲染循环中的 `getBounding` 崩溃。

**根本原因**: 对 LiteGraph 内部 API 的理解偏差。代码使用了直觉式的属性命名，而非阅读库文档确认正确的属性名。

### Bug 5: 节点类型重复注册警告

**代码位置**: `wf-editor.js:247`

每次进入编辑器页面时 `initLiteGraph` 无条件重新注册所有节点类型，LiteGraph 发出 `replacing node type` 警告。虽然只是 warning 级别，但表明缺少状态管理——`initLiteGraph` 不是幂等的。

**根本原因**: 没有在注册前检查是否已存在，缺少防御性判断。

### Bug 6: 端口查找方法返回值格式不统一

**代码位置**: `wf-editor.js:106-107`（模板边缘创建）

`LGraphNode.findOutputSlot` / `findInputSlot` 在不同 LiteGraph 版本中可能返回 `number` 或 `{slot: number}`。代码直接与 `>= 0` 比较，对象返回值会导致 `false`。

**根本原因**: 对外部库 API 返回值格式缺乏防御性适配。

---

## 三、Bug 引入溯源

根据 git 历史和迭代记录分析，这些问题是在以下阶段分批引入的：

| 迭代阶段 | 日期 | 引入的 Bug | 变更背景 |
|---------|------|-----------|---------|
| **初始工作流系统** | 2026-05-11 | Bug 2, 3, 4 | 工作流编辑器首次实现，集成 LiteGraph。此时模板类型名使用占位符（如 `wf_3dgenerate`），链接格式参考了错误的 API 文档 |
| **前端重构** | 2026-05-13 | Bug 5, 6 | 从 3689 行单文件拆分为 ES 模块。`initLiteGraph` 被独立为函数但未做幂等处理 |
| **节点扩展** | 2026-05-13 | Bug 1 加剧 | 新增 `model_prep`、`triposr`、`hunyuan` 等节点类型，模板中的 `wf_3dgenerate` 本应改为 `wf_triposr` 但被遗漏 |
| **参数级联** | 2026-05-12 | Bug 2 暴露 | `buildUpstreamOptions` 和 `buildOutputConnections` 新增对 `_links` 的依赖，但未考虑 `_links` 可能未初始化 |

所有 bug 的共同特征：**引入了新代码路径，但未同步更新相关的模板定义和 API 调用模式**。

---

## 四、为什么测试没有发现这些问题

### 现有测试覆盖分析

| 测试文件 | 覆盖内容 | Bug 检出能力 |
|---------|---------|------------|
| `tests/test_scripts.py` | CLI 脚本 JSON 输出、错误契约、路径逻辑 | ❌ 无 — 完全不涉及前端 |
| `tests/test_workflow_engine.py` | 拓扑排序、边标准化、端口映射 | ❌ 无 — 纯 Python 逻辑 |
| `tests/test_api.py` | REST API 端点、工作流 CRUD、执行 | ⚠️ 部分 — 测试了 API 返回的 node_types，但未验证其与前端的集成 |

### 覆盖率盲区

```
┌─────────────────────────────────────────────────────────────┐
│  前端 JavaScript                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 模板加载  │  │ 画板渲染  │  │ 拖拽交互  │  │ 节点检查  │  │ ← 0% 覆盖
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
├─────────────────────────────────────────────────────────────┤
│  后端 Python                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ CLI 脚本  │  │ 工作流引擎│  │ API 端点  │  │ 数据库    │  │ ← 已有测试
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 具体缺失的测试用例

1. **模板定义验证**: 没有测试确认模板中的 `type` 字段与 `/api/node-types` 返回的 ID 一致性
2. **前端单元测试**: `wf-editor.js` 中 `_wfTemplate`、`createLiteGraphNodeClass` 等函数没有单元测试
3. **E2E 浏览器测试**: 没有用 Playwright/Cypress 验证模板点击→节点出现在画板→可拖拽→节点详情展示的完整流程
4. **LiteGraph 集成测试**: 没有验证我们自定义的 `WFNode` 类与 LiteGraph 0.7.14 版本的兼容性
5. **API schema 一致性测试**: 没有自动验证 `node_types.py` 的端口定义与模板中的 `sourcePort`/`targetPort` 引用的端口名一致

---

## 五、工作流程优化方案

### 5.1 短期（立即执行）

#### A. 前端代码质量基础设施

```
npm init -y
npm install --save-dev vitest jsdom @playwright/test
```

**vitest 单元测试** — 测试独立的前端函数：

```javascript
// tests/frontend/wf-editor.test.js
import { describe, it, expect } from 'vitest';

describe('createLiteGraphNodeClass', () => {
  it('returns null for unknown type', () => {
    const cls = createLiteGraphNodeClass('nonexistent', []);
    expect(cls).toBeNull();
  });

  it('creates class with correct port count', () => {
    const nodeTypes = [
      { id: 'relief', label: 'Relief', category: 'process',
        inputs: [{ name: 'image', type: 'image' }],
        outputs: [{ name: 'stl', type: 'stl' }],
        params: {} }
    ];
    const cls = createLiteGraphNodeClass('relief', nodeTypes);
    expect(cls).not.toBeNull();
  });
});

describe('_findSlot', () => {
  it('finds slot by name', () => {
    const node = { outputs: [{ name: 'stl', type: 'stl' }] };
    expect(_findSlot(node, 'stl', false)).toBe(0);
  });

  it('returns -1 for non-existent', () => {
    const node = { outputs: [] };
    expect(_findSlot(node, 'nonexistent', false)).toBe(-1);
  });
});
```

**模板 schema 验证测试** — 运行期检查模板定义一致性：

```javascript
// tests/frontend/template-validation.test.js
describe('Template type validation', () => {
  it('all template node types exist in node registry', async () => {
    const nodeTypes = await fetch('/api/node-types').then(r => r.json());
    const typeIds = new Set(nodeTypes.types.map(t => t.id));

    const templates = { basic: ..., text2img: ..., advanced: ..., ... };
    for (const [name, tpl] of Object.entries(templates)) {
      for (const node of tpl.nodes) {
        const cleanType = node.type.replace(/^wf_/, '');
        expect(typeIds.has(cleanType), `Template "${name}" references unknown type "${node.type}"`).toBe(true);
      }
    }
  });
});
```

#### B. API Schema 一致性测试

```python
# tests/test_schema_consistency.py — 新增
def test_template_types_match_node_types():
    """验证模板引用的所有节点类型在 node_types.py 中存在"""
    from web.node_types import NODE_TYPES

    templates = {
        "basic": ["file_input", "relief"],
        "text2img": ["text_input", "text_to_image", "relief"],
        "advanced": ["file_input", "layered_relief", "repair"],
        "print-ready": ["file_input", "triposr", "model_prep"],
        "full": ["file_input", "triposr", "model_prep", "views"],
    }

    for tpl_name, expected_types in templates.items():
        for t in expected_types:
            assert t in NODE_TYPES, f"Template '{tpl_name}' references '{t}' which is not a registered node type"

def test_template_port_names_match_node_ports():
    """验证模板边的端口名在节点类型输出端口中存在"""
    ...
```

#### C. 前端函数导入测试（验证 JS 模块解析）

在 CI 中执行简单的 `node -e "require('./web/static/js/pages/wf-editor.js')"` 或使用 Node.js 的 ES 模块加载验证语法和导入路径正确性。

### 5.2 中期（1-2 周内）

#### D. Playwright E2E 浏览器测试

```bash
npm install --save-dev @playwright/test
npx playwright install chromium
```

关键 E2E 测试场景：

```javascript
// e2e/workflow-editor.spec.js
const { test, expect } = require('@playwright/test');

test.describe('Workflow Editor', () => {

  test('Template "basic" creates 2 nodes on canvas', async ({ page }) => {
    await page.goto('http://127.0.0.1:8080/#/workflow/new');
    await page.waitForSelector('#wf-canvas-wrap canvas');

    // 点击"Basic"模板按钮
    await page.click('text=Basic');

    // 等待节点出现在画板上
    await page.waitForTimeout(500);

    // 验证 LiteGraph 内部状态
    const nodeCount = await page.evaluate(() => {
      return window.wfGraph?._nodes?.length || 0;
    });
    expect(nodeCount).toBe(2);
  });

  test('template "text2img" creates 3 nodes with correct connections', async ({ page }) => {
    await page.goto('http://127.0.0.1:8080/#/workflow/new');
    await page.click('text=Text → Image');

    const linkCount = await page.evaluate(() => {
      return (window.wfGraph?._links || []).length;
    });
    expect(linkCount).toBe(2);
  });

  test('drag palette item to canvas creates node', async ({ page }) => {
    await page.goto('http://127.0.0.1:8080/#/workflow/new');

    const paletteItem = page.locator('.node-item[draggable]').first();
    const canvas = page.locator('#wf-canvas-wrap');

    await paletteItem.dragTo(canvas, { targetPosition: { x: 300, y: 200 } });

    const hasNode = await page.evaluate(() => {
      return window.wfGraph?._nodes?.length > 0;
    });
    expect(hasNode).toBe(true);
  });

  test('click node shows inspector with correct inputs/outputs', async ({ page }) => {
    // ...
  });

  test('canvas fit button adjusts view', async ({ page }) => {
    // ...
  });

  test('no console errors after template load', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err));

    await page.goto('http://127.0.0.1:8080/#/workflow/new');
    await page.click('text=Basic');
    await page.waitForTimeout(500);

    expect(errors).toHaveLength(0);
  });
});
```

#### E. CI 集成

```yaml
# .github/workflows/test.yml (或项目级 CI 脚本)
steps:
  - name: Python lint & unit tests
    run: |
      python tests/test_scripts.py
      python tests/test_workflow_engine.py

  - name: Schema consistency test
    run: python tests/test_schema_consistency.py

  - name: Start server & API integration test
    run: python tests/test_api.py --start-server

  - name: Frontend unit tests (vitest)
    run: npx vitest run tests/frontend/

  - name: E2E browser tests (Playwright)
    run: |
      python start-server.py --no-browser &
      npx playwright test e2e/
      kill %1
```

#### F. 前端集成测试 — 验证 LiteGraph 兼容性

专门测试我们的 `WFNode` 类、`createLiteGraphNodeClass`、`_findSlot` 等与 LiteGraph 0.7.14 版本的兼容性：

```javascript
// tests/frontend/litegraph-integration.test.js
import { describe, it, expect, beforeAll } from 'vitest';

// 模拟 LiteGraph 环境
import 'litegraph.js';  // 从 node_modules 或 mock

describe('WFNode integration with LiteGraph', () => {
  it('adds correct number of inputs/outputs', () => { ... });
  it('connects between nodes with matching port types', () => { ... });
  it('rejects connection with incompatible port types', () => { ... });
  it('serializes and deserializes correctly', () => { ... });
});
```

### 5.3 长期（架构级改进）

#### G. 前端类型安全

虽然项目使用 Vanilla JS（零构建），但可以引入 **JSDoc 类型注解 + TypeScript 检查**（不改变运行时）：

```javascript
// wf-editor.js
/**
 * @typedef {{ id: number|string, type: string, title?: string, pos: [number, number] }} WFNodeDef
 * @typedef {{ source: number|string, target: number|string, sourcePort: string|number, targetPort: string|number }} WFEdgeDef
 * @typedef {{ nodes: WFNodeDef[], edges: WFEdgeDef[] }} WFTemplate
 */

/** @type {Record<string, WFTemplate>} */
const templates = { ... };
```

然后用 `tsc --checkJs` 在 CI 中验证。

#### H. 模板定义从后端加载

不再在前端硬编码模板，改为从后端 API 加载：

```
GET /api/workflow-templates

→ {
    "templates": [
      {
        "id": "basic",
        "label": "Basic",
        "label_zh": "基础",
        "nodes": [
          {"id": 1, "type": "file_input", "title": "File", "pos": [100, 100]},
          {"id": 2, "type": "relief", "title": "Relief", "pos": [400, 100]}
        ],
        "edges": [
          {"source": 1, "target": 2, "sourcePort": "file", "targetPort": "image"}
        ]
      },
      ...
    ]
  }
```

后端在生成模板定义时可自动校验所有类型名和端口名，杜绝不一致。

#### I. LiteGraph 版本锁定与 API 适配层

```javascript
// lib/litegraph-adapter.js — LiteGraph 版本适配层
export function zoomCanvasToFit(canvas) {
  if (typeof canvas.zoomToFit === 'function') return canvas.zoomToFit();
  if (typeof canvas.fitToContent === 'function') return canvas.fitToContent();
  if (canvas.ds) {
    // 手动实现 fit
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    // ... calculate bounds
    canvas.ds.scale = Math.min(/* ... */);
  }
}

export function getGraphLinks(graph) {
  return graph._links || [];
}

export function connectNodes(srcNode, srcSlot, tgtNode, tgtSlot) {
  return srcNode.connect(srcSlot, tgtNode, tgtSlot);
}

export function findSlot(node, name, isInput) {
  // 统一的 slot 查找，兼容不同 LiteGraph 版本
  if (isInput && node.findInputSlot) {
    const r = node.findInputSlot(name);
    return typeof r === 'number' ? r : (r?.slot ?? -1);
  }
  if (!isInput && node.findOutputSlot) {
    const r = node.findOutputSlot(name);
    return typeof r === 'number' ? r : (r?.slot ?? -1);
  }
  const slots = isInput ? node.inputs : node.outputs;
  return slots?.findIndex(s => s.name === name) ?? -1;
}
```

---

## 六、优先级排序

| 优先级 | 方案 | 工作量 | 影响 | 阻止何种 Bug 复发 |
|-------|------|-------|------|-----------------|
| **P0** | B. Schema 一致性测试 | 1h | 立即发现模板类型名不匹配 | Bug 1 |
| **P0** | A. 前端单元测试 (vitest) | 2h | 测试独立函数逻辑 | Bug 1, 2, 6 |
| **P0** | F. LiteGraph 集成测试 | 2h | 验证与 LiteGraph 0.7.14 兼容 | Bug 2, 3, 4 |
| **P1** | D. Playwright E2E 测试 | 4h | 验证完整用户交互流程 | 全部 Bug |
| **P1** | E. CI 集成 | 2h | 自动化执行所有测试 | 防止回归 |
| **P1** | J. 适配层 (lib/litegraph-adapter.js) | 2h | 隔离 LiteGraph 版本差异 | Bug 2, 3, 4, 6 |
| **P2** | H. 模板从后端加载 | 4h | 模板与节点定义单一数据源 | Bug 1 |
| **P3** | G. TypeScript JSDoc 检查 | 3h | 编译时发现类型错误 | Bug 1, 4 |
| **P3** | I. 快照/视觉回归测试 | 3h | 检测 UI 布局意外变化 | 渲染类 Bug |

---

## 七、教训总结

1. **外部库 API 假设必须有测试验证**: 前端依赖了 LiteGraph CDN 版本，但没有针对该特定版本编写兼容性测试。修复：为每个外部依赖的集成点编写测试。

2. **字符串常量是 Bug 的温床**: 模板类型名、端口名、参数名等字符串常量在前端和后端之间重复定义。修复：单一数据源（后端生成模板定义）或共享 schema。

3. **前端测试空白是不可接受的**: 项目的 STANDARDS.md 中已经规划了测试金字塔（Python 3 层），但前端的 JavaScript 层完全无测试。修复：补充前端的 vitest 单元测试 + Playwright E2E 测试。

4. **"静默失败"的反模式**: `createLiteGraphNodeClass` 在找不到类型时返回 `null`，调用方默默跳过。这是正确行为但缺少日志。修复：添加 `console.warn` 提示（已在本次修复中加入）。

5. **迭代记录可以更好**: 当前迭代记录是自动生成的结构化报告，但缺少"已知技术债"清单。建议在每次迭代结束时更新一个 `TECHDEBT.md`，列出待修复的假设和快捷方式。

---

*分析编写: Claude Code | 2026-05-15*
