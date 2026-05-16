# 前端测试基础设施 — 实施方案

**日期**: 2026-05-15  
**状态**: ✅ 已完成  
**关联**: [工作流编辑器 Bug 复盘](./workflow-editor-bug-retrospective.md)

---

## 一、目标

建立覆盖前端 JavaScript 层的自动化测试体系，补上当前 0% 覆盖的空白。完成后，所有新引入的前端代码必须通过对应测试才能合并。

## 二、改造清单 (Checklist)

### P0 — 立即实施（阻止同类 Bug 复发）

- [x] **P0-1** `tests/test_schema_consistency.py` — Python Schema 一致性测试
  - 验证模板类型名在 `node_types.py` 中存在
  - 验证模板端口名在节点类型定义中存在
  - 验证 `/api/node-types` 返回所有注册节点
  - 工作量: ~1h | 依赖: 无

- [x] **P0-2** 前端测试环境搭建 — npm init + vitest 配置
  - 项目根目录 `package.json`
  - `vitest.config.js` (jsdom 环境)
  - `tests/frontend/` 目录
  - 工作量: ~0.5h | 依赖: Node.js

- [x] **P0-3** `tests/frontend/wf-core.test.js` — 前端核心函数单元测试
  - `createLiteGraphNodeClass` 正确创建/拒绝
  - `_findSlot` 按名查找
  - `_isTypeCompatible` 类型兼容规则
  - Mock LiteGraph API
  - 工作量: ~2h | 依赖: P0-2

- [x] **P0-4** `tests/frontend/litegraph-adapter.test.js` — LiteGraph 适配层测试
  - `connectNodes` 正确调用 LiteGraph
  - `zoomCanvasToFit` 多版本兼容
  - `getGraphLinks` 空值安全
  - `registerNodeType` 幂等
  - 工作量: ~1h | 依赖: P0-2, P1-3

- [x] **P0-5** `web/static/js/lib/litegraph-adapter.js` — LiteGraph 适配层
  - 封装所有 LiteGraph 版本差异
  - 提供统一的断言/降级 API
  - 工作量: ~1.5h | 依赖: 无

### P1 — 短期实施（建立回归防线）

- [x] **P1-1** `e2e/workflow-editor.spec.js` — Playwright E2E 测试
  - 模板点击→节点出现在画板
  - 拖拽组件到画板→节点创建
  - 节点点击→inspector 面板展示
  - Fit 按钮→画板缩放
  - 无控制台报错
  - 工作量: ~4h | 依赖: Playwright, Server

- [x] **P1-2** `e2e/playwright.config.js` — Playwright 配置
  - Chromium 浏览器
  - 自动启动/停止开发服务器
  - 截图/录像 on failure
  - 工作量: ~0.5h | 依赖: P1-1

- [x] **P1-3** `run-tests.sh` / `run-tests.bat` — CI 测试脚本
  - 按顺序执行: Python → vitest → Playwright
  - 失败时退出非零码
  - 打印汇总结果
  - 工作量: ~0.5h | 依赖: P0-2, P1-1

- [x] **P1-4** 更新 `STANDARDS.md` — 补充前端测试规范
  - 新增 "前端测试规范" 章节
  - 明确新增组件必须补充测试
  - 工作量: ~0.3h | 依赖: 无

---

## 三、架构设计

### 3.1 测试金字塔

```
           ┌──────────┐
           │ E2E      │  Playwright 浏览器测试 (P1-1)
           │ ~6 tests │  验证完整用户交互流程
           ├──────────┤
           │ 集成     │  vitest + LiteGraph mock (P0-4)
           │ ~8 tests │  验证 WFNode ↔ LiteGraph API 兼容
           ├──────────┤
           │ 单元     │  vitest 纯函数测试 (P0-3)
           │ ~15 tests│  验证独立 JS 函数逻辑
           ├──────────┤
           │ Schema   │  Python 一致性检查 (P0-1)
           │ ~8 tests │  验证前后端数据结构一致
           └──────────┘
```

### 3.2 LiteGraph 适配层设计

```
wf-editor.js
┌─────────────────────────────────────┐
│  import { connectNodes,              │
│           zoomCanvasToFit,           │
│           getGraphLinks,             │
│           findSlot,                  │
│           registerNodeTypeSafe }     │
│         from '../lib/litegraph-adapter.js' │
└──────────────┬──────────────────────┘
               │
litegraph-adapter.js
┌──────────────────────────────────────┐
│  // 统一封装所有 LiteGraph API 差异    │
│  // 版本: 0.7.14 (CDN)               │
│  // 降级: 无方法时 graceful fallback  │
│  // 断言: 开发模式下检查前置条件       │
└──────────────┬──────────────────────┘
               │
       LiteGraph CDN (global)
```

### 3.3 文件结构

```
3dprint/
├── package.json                    # 新增: npm 项目配置
├── vitest.config.js                # 新增: vitest 配置
├── run-tests.sh / run-tests.bat    # 新增: CI 入口脚本
├── tests/
│   ├── test_scripts.py             # 已有
│   ├── test_api.py                 # 已有
│   ├── test_workflow_engine.py     # 已有
│   ├── test_schema_consistency.py  # 新增 P0-1
│   └── frontend/                   # 新增 P0-3, P0-4
│       ├── setup.js                #   vitest setup: mock LiteGraph
│       ├── wf-core.test.js         #   核心函数测试
│       └── litegraph-adapter.test.js # 适配层测试
├── e2e/                            # 新增 P1-1, P1-2
│   ├── playwright.config.js
│   └── workflow-editor.spec.js
└── web/static/js/lib/
    └── litegraph-adapter.js        # 新增 P0-5
```

---

## 四、各方案详细设计

### P0-1: Schema 一致性测试

**文件**: `tests/test_schema_consistency.py`

测试用例：
1. `test_all_template_types_exist` — 遍历所有模板，确认每个 `type` 在 `NODE_TYPES` 中
2. `test_template_port_names_match` — 确认模板边的 `sourcePort`/`targetPort` 是真实端口名
3. `test_node_type_ids_consistent` — 确认 `node_types.py` 中 `NODE_TYPES` key == NodeType.id
4. `test_api_returns_all_node_types` — HTTP GET `/api/node-types` 覆盖所有注册节点
5. `test_template_labels_in_i18n` — 确认模板名在各语言 locale 中有翻译

### P0-2: vitest 环境搭建

**文件**: `package.json`, `vitest.config.js`

```json
{
  "name": "3dprint",
  "private": true,
  "type": "module",
  "scripts": {
    "test:frontend": "vitest run tests/frontend/",
    "test:frontend:watch": "vitest tests/frontend/",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
  },
  "devDependencies": {
    "vitest": "^2.0.0",
    "@playwright/test": "^1.50.0"
  }
}
```

### P0-3: 前端核心函数单元测试

**文件**: `tests/frontend/wf-core.test.js`

Mock LiteGraph 全局对象，测试：
- `createLiteGraphNodeClass` 对正确/错误/边界输入的行为
- `_findSlot` 按名查找 input/output slot
- `_isTypeCompatible` 全部兼容规则
- WFNode 构造后 inputs/outputs 数量正确
- WFNode.connect 的 lenient 类型检查

### P0-4: LiteGraph 适配层测试

**文件**: `tests/frontend/litegraph-adapter.test.js`

测试适配层函数的降级逻辑，包括模拟 LiteGraph 不存在的场景。

### P0-5: LiteGraph 适配层

**文件**: `web/static/js/lib/litegraph-adapter.js`

从 `wf-editor.js` 中抽取所有直接接触 LiteGraph 内部 API 的代码，统一封装。

### P1-1: Playwright E2E 测试

**文件**: `e2e/workflow-editor.spec.js`

关键场景：
1. 打开编辑器 → 点击 "Basic" 模板 → 2 个节点出现在画板
2. 拖拽 palette 项到画板 → 新节点创建
3. 点击节点 → inspector 展示输入/输出/参数
4. 点击 Fit 按钮 → 无报错
5. 控制台无 error 级别日志

### P1-3: CI 脚本

**文件**: `run-tests.bat` (Windows) / `run-tests.sh` (Unix)

```
1. Python lint (可选)
2. test_scripts.py
3. test_workflow_engine.py
4. test_schema_consistency.py
5. 启动 server → test_api.py → 关闭 server
6. vitest run tests/frontend/
7. 启动 server → playwright test → 关闭 server
8. 打印汇总
```

---

## 五、实施顺序

```
Step 1: P0-5  适配层 (隔离依赖)
Step 2: P0-2  vitest 环境
Step 3: P0-3  核心函数测试 (依赖 Step 1, 2)
Step 4: P0-4  适配层测试 (依赖 Step 1, 2)
Step 5: P0-1  Schema 测试 (独立，可并行)
Step 6: P1-4  STANDARDS.md 更新
Step 7: P1-1, P1-2  Playwright E2E
Step 8: P1-3  CI 脚本
```

---

*计划编写: Claude Code | 2026-05-15*
