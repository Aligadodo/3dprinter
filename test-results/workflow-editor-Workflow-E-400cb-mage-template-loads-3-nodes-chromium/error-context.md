# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: workflow-editor.spec.js >> Workflow Editor >> clicking "Text→Image" template loads 3 nodes
- Location: e2e\workflow-editor.spec.js:39:3

# Error details

```
TimeoutError: page.waitForSelector: Timeout 10000ms exceeded.
Call log:
  - waiting for locator('#wf-canvas') to be visible

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - navigation "主导航" [ref=e2]:
    - generic [ref=e3]:
      - generic [ref=e4]: 3D 打印流水线
      - generic [ref=e5]:
        - button "中" [ref=e6] [cursor=pointer]
        - button "EN" [ref=e7] [cursor=pointer]
    - generic [ref=e8]: 任务管理
    - link "工作台" [ref=e9] [cursor=pointer]:
      - /url: "#/dashboard"
    - link "新建任务" [ref=e10] [cursor=pointer]:
      - /url: "#/new"
    - separator [ref=e11]
    - generic [ref=e12]: 文件管理
    - link "文件浏览" [ref=e13] [cursor=pointer]:
      - /url: "#/browse"
    - separator [ref=e14]
    - generic [ref=e15]: 工作流
    - link "工作流管理" [ref=e16] [cursor=pointer]:
      - /url: "#/workflows"
    - link "工作流编辑器" [ref=e17] [cursor=pointer]:
      - /url: "#/workflow/new"
    - separator [ref=e18]
    - generic [ref=e19]: 文档中心
    - link "设计文档" [ref=e20] [cursor=pointer]:
      - /url: "#/docs"
    - link "API 文档" [ref=e21] [cursor=pointer]:
      - /url: /docs
    - separator [ref=e22]
    - generic [ref=e23]: 开发工具
    - button "切换深浅色主题" [ref=e25] [cursor=pointer]: ☀
  - main [ref=e26]:
    - heading "工作台" [level=2] [ref=e27]
    - generic [ref=e28]:
      - generic [ref=e29]:
        - generic [ref=e30]:
          - generic [ref=e31]: "0"
          - generic [ref=e32]: 排队中
        - generic [ref=e33]:
          - generic [ref=e34]: "0"
          - generic [ref=e35]: 运行中
        - generic [ref=e36]:
          - generic [ref=e37]: "29"
          - generic [ref=e38]: 已完成
        - generic [ref=e39]:
          - generic [ref=e40]: "1"
          - generic [ref=e41]: 失败
      - generic [ref=e42]:
        - heading "最近任务" [level=3] [ref=e43]
        - generic [ref=e44]:
          - combobox [ref=e45]:
            - option "状态筛选" [selected]
            - option "排队"
            - option "运行"
            - option "完成"
            - option "失败"
            - option "取消"
          - combobox [ref=e46]:
            - option "类型筛选" [selected]
            - option "多层套色浮雕"
            - option "夜灯 (Lithophane)"
            - option "网格简化 (Simplify)"
            - option "网格平滑 (Smooth)"
            - option "打印准备 (Model Prep)"
            - option "浮雕 (Relief)"
            - option "TripoSR（快速 3D）"
          - button "刷新" [ref=e47] [cursor=pointer]
      - generic [ref=e48]:
        - 'link "✓ 完成 多层套色浮雕 套色浮雕 2026-05-16 07:56:59 input.jpg (4色层 层高0.4mm) ID: c9670701c5d5 →" [ref=e49] [cursor=pointer]':
          - /url: "#/task/c9670701c5d5"
          - generic [ref=e50]: ✓ 完成
          - generic [ref=e51]: 多层套色浮雕
          - generic [ref=e52]:
            - generic [ref=e53]: 套色浮雕 2026-05-16 07:56:59 input.jpg (4色层 层高0.4mm)
            - generic [ref=e54]: "ID: c9670701c5d5"
          - generic [ref=e55]: →
        - 'link "✓ 完成 浮雕 (Relief) 浮雕 2026-05-15 23:03:07 input.jpg (230×135mm 深3mm) ID: 3079b7be7f07 →" [ref=e56] [cursor=pointer]':
          - /url: "#/task/3079b7be7f07"
          - generic [ref=e57]: ✓ 完成
          - generic [ref=e58]: 浮雕 (Relief)
          - generic [ref=e59]:
            - generic [ref=e60]: 浮雕 2026-05-15 23:03:07 input.jpg (230×135mm 深3mm)
            - generic [ref=e61]: "ID: 3079b7be7f07"
          - generic [ref=e62]: →
        - 'link "✓ 完成 多层套色浮雕 套色浮雕 2026-05-15 22:45:26 input.jpg (4色层 层高0.4mm 3MF) ID: adcd8bb005b9 →" [ref=e63] [cursor=pointer]':
          - /url: "#/task/adcd8bb005b9"
          - generic [ref=e64]: ✓ 完成
          - generic [ref=e65]: 多层套色浮雕
          - generic [ref=e66]:
            - generic [ref=e67]: 套色浮雕 2026-05-15 22:45:26 input.jpg (4色层 层高0.4mm 3MF)
            - generic [ref=e68]: "ID: adcd8bb005b9"
          - generic [ref=e69]: →
        - 'link "✗ 失败 🔄 工作流 打印准备 (Model Prep) model_prep 2026-05-15 22:10:33 input.jpg ID: a26249b094da →" [ref=e70] [cursor=pointer]':
          - /url: "#/task/a26249b094da"
          - generic [ref=e71]: ✗ 失败
          - generic "此任务属于工作流运行" [ref=e72]: 🔄 工作流
          - generic [ref=e73]: 打印准备 (Model Prep)
          - generic [ref=e74]:
            - generic [ref=e75]: model_prep 2026-05-15 22:10:33 input.jpg
            - generic [ref=e76]: "ID: a26249b094da"
          - generic [ref=e77]: →
        - 'link "✓ 完成 🔄 工作流 多层套色浮雕 套色浮雕 2026-05-15 22:09:58 input.jpg (4色层 层高0.4mm) ID: f539d5bda074 →" [ref=e78] [cursor=pointer]':
          - /url: "#/task/f539d5bda074"
          - generic [ref=e79]: ✓ 完成
          - generic "此任务属于工作流运行" [ref=e80]: 🔄 工作流
          - generic [ref=e81]: 多层套色浮雕
          - generic [ref=e82]:
            - generic [ref=e83]: 套色浮雕 2026-05-15 22:09:58 input.jpg (4色层 层高0.4mm)
            - generic [ref=e84]: "ID: f539d5bda074"
          - generic [ref=e85]: →
        - 'link "✓ 完成 多层套色浮雕 套色浮雕 2026-05-15 20:54:37 input.jpg (4色层 层高0.4mm 3MF) ID: e4a822dfd342 →" [ref=e86] [cursor=pointer]':
          - /url: "#/task/e4a822dfd342"
          - generic [ref=e87]: ✓ 完成
          - generic [ref=e88]: 多层套色浮雕
          - generic [ref=e89]:
            - generic [ref=e90]: 套色浮雕 2026-05-15 20:54:37 input.jpg (4色层 层高0.4mm 3MF)
            - generic [ref=e91]: "ID: e4a822dfd342"
          - generic [ref=e92]: →
        - 'link "✓ 完成 多层套色浮雕 套色浮雕 2026-05-15 20:20:39 input.jpg (4色层 层高0.4mm 3MF) ID: 7814f61a03ac →" [ref=e93] [cursor=pointer]':
          - /url: "#/task/7814f61a03ac"
          - generic [ref=e94]: ✓ 完成
          - generic [ref=e95]: 多层套色浮雕
          - generic [ref=e96]:
            - generic [ref=e97]: 套色浮雕 2026-05-15 20:20:39 input.jpg (4色层 层高0.4mm 3MF)
            - generic [ref=e98]: "ID: 7814f61a03ac"
          - generic [ref=e99]: →
        - 'link "✓ 完成 🔄 工作流 多层套色浮雕 套色浮雕 2026-05-15 18:30:31 input.jpg (4色层 层高0.4mm) ID: e059c3a8ab19 →" [ref=e100] [cursor=pointer]':
          - /url: "#/task/e059c3a8ab19"
          - generic [ref=e101]: ✓ 完成
          - generic "此任务属于工作流运行" [ref=e102]: 🔄 工作流
          - generic [ref=e103]: 多层套色浮雕
          - generic [ref=e104]:
            - generic [ref=e105]: 套色浮雕 2026-05-15 18:30:31 input.jpg (4色层 层高0.4mm)
            - generic [ref=e106]: "ID: e059c3a8ab19"
          - generic [ref=e107]: →
        - 'link "✓ 完成 浮雕 (Relief) 浮雕 2026-05-15 18:12:45 input.jpg (160×120mm 深3mm) ID: 29930f5ca730 →" [ref=e108] [cursor=pointer]':
          - /url: "#/task/29930f5ca730"
          - generic [ref=e109]: ✓ 完成
          - generic [ref=e110]: 浮雕 (Relief)
          - generic [ref=e111]:
            - generic [ref=e112]: 浮雕 2026-05-15 18:12:45 input.jpg (160×120mm 深3mm)
            - generic [ref=e113]: "ID: 29930f5ca730"
          - generic [ref=e114]: →
        - 'link "✓ 完成 多层套色浮雕 套色浮雕 2026-05-15 13:52:21 input.jpg (4色层 层高0.4mm 3MF) ID: b099b6a0a592 →" [ref=e115] [cursor=pointer]':
          - /url: "#/task/b099b6a0a592"
          - generic [ref=e116]: ✓ 完成
          - generic [ref=e117]: 多层套色浮雕
          - generic [ref=e118]:
            - generic [ref=e119]: 套色浮雕 2026-05-15 13:52:21 input.jpg (4色层 层高0.4mm 3MF)
            - generic [ref=e120]: "ID: b099b6a0a592"
          - generic [ref=e121]: →
        - 'link "✓ 完成 🔄 工作流 多层套色浮雕 套色浮雕 2026-05-14 17:33:48 input.JPG (4色层 层高0.4mm) ID: a7e8544f3c47 →" [ref=e122] [cursor=pointer]':
          - /url: "#/task/a7e8544f3c47"
          - generic [ref=e123]: ✓ 完成
          - generic "此任务属于工作流运行" [ref=e124]: 🔄 工作流
          - generic [ref=e125]: 多层套色浮雕
          - generic [ref=e126]:
            - generic [ref=e127]: 套色浮雕 2026-05-14 17:33:48 input.JPG (4色层 层高0.4mm)
            - generic [ref=e128]: "ID: a7e8544f3c47"
          - generic [ref=e129]: →
        - 'link "✓ 完成 🔄 工作流 多层套色浮雕 套色浮雕 2026-05-14 16:10:52 input.JPG (4色层 层高0.4mm) ID: 1d45d1b54812 →" [ref=e130] [cursor=pointer]':
          - /url: "#/task/1d45d1b54812"
          - generic [ref=e131]: ✓ 完成
          - generic "此任务属于工作流运行" [ref=e132]: 🔄 工作流
          - generic [ref=e133]: 多层套色浮雕
          - generic [ref=e134]:
            - generic [ref=e135]: 套色浮雕 2026-05-14 16:10:52 input.JPG (4色层 层高0.4mm)
            - generic [ref=e136]: "ID: 1d45d1b54812"
          - generic [ref=e137]: →
        - 'link "✓ 完成 TripoSR（快速 3D） TripoSR 2026-05-14 11:20:46 input.jpg (GLB 256px) ID: dd637861d4a7 →" [ref=e138] [cursor=pointer]':
          - /url: "#/task/dd637861d4a7"
          - generic [ref=e139]: ✓ 完成
          - generic [ref=e140]: TripoSR（快速 3D）
          - generic [ref=e141]:
            - generic [ref=e142]: TripoSR 2026-05-14 11:20:46 input.jpg (GLB 256px)
            - generic [ref=e143]: "ID: dd637861d4a7"
          - generic [ref=e144]: →
        - 'link "✓ 完成 TripoSR（快速 3D） TripoSR 2026-05-14 00:50:21 input.jpg (GLB 256px) ID: 4ee4873b8313 →" [ref=e145] [cursor=pointer]':
          - /url: "#/task/4ee4873b8313"
          - generic [ref=e146]: ✓ 完成
          - generic [ref=e147]: TripoSR（快速 3D）
          - generic [ref=e148]:
            - generic [ref=e149]: TripoSR 2026-05-14 00:50:21 input.jpg (GLB 256px)
            - generic [ref=e150]: "ID: 4ee4873b8313"
          - generic [ref=e151]: →
        - 'link "✓ 完成 夜灯 (Lithophane) 夜灯 2026-05-13 21:54:46 input.jpg (160×120mm 深2mm) ID: 69b6cf9f9180 →" [ref=e152] [cursor=pointer]':
          - /url: "#/task/69b6cf9f9180"
          - generic [ref=e153]: ✓ 完成
          - generic [ref=e154]: 夜灯 (Lithophane)
          - generic [ref=e155]:
            - generic [ref=e156]: 夜灯 2026-05-13 21:54:46 input.jpg (160×120mm 深2mm)
            - generic [ref=e157]: "ID: 69b6cf9f9180"
          - generic [ref=e158]: →
        - 'link "✓ 完成 🔄 工作流 浮雕 (Relief) 浮雕 2026-05-13 01:33:59 input.png (160×120mm 深3mm) ID: 69cff040fb3d →" [ref=e159] [cursor=pointer]':
          - /url: "#/task/69cff040fb3d"
          - generic [ref=e160]: ✓ 完成
          - generic "此任务属于工作流运行" [ref=e161]: 🔄 工作流
          - generic [ref=e162]: 浮雕 (Relief)
          - generic [ref=e163]:
            - generic [ref=e164]: 浮雕 2026-05-13 01:33:59 input.png (160×120mm 深3mm)
            - generic [ref=e165]: "ID: 69cff040fb3d"
          - generic [ref=e166]: →
        - 'link "✓ 完成 🔄 工作流 浮雕 (Relief) 浮雕 2026-05-13 01:04:53 input.png (160×120mm 深3mm) ID: f366a5dec38c →" [ref=e167] [cursor=pointer]':
          - /url: "#/task/f366a5dec38c"
          - generic [ref=e168]: ✓ 完成
          - generic "此任务属于工作流运行" [ref=e169]: 🔄 工作流
          - generic [ref=e170]: 浮雕 (Relief)
          - generic [ref=e171]:
            - generic [ref=e172]: 浮雕 2026-05-13 01:04:53 input.png (160×120mm 深3mm)
            - generic [ref=e173]: "ID: f366a5dec38c"
          - generic [ref=e174]: →
        - 'link "✓ 完成 🔄 工作流 浮雕 (Relief) 浮雕 2026-05-12 10:13:05 input.png (160×120mm 深3mm) ID: 5fdbb5947ada →" [ref=e175] [cursor=pointer]':
          - /url: "#/task/5fdbb5947ada"
          - generic [ref=e176]: ✓ 完成
          - generic "此任务属于工作流运行" [ref=e177]: 🔄 工作流
          - generic [ref=e178]: 浮雕 (Relief)
          - generic [ref=e179]:
            - generic [ref=e180]: 浮雕 2026-05-12 10:13:05 input.png (160×120mm 深3mm)
            - generic [ref=e181]: "ID: 5fdbb5947ada"
          - generic [ref=e182]: →
        - 'link "✓ 完成 网格平滑 (Smooth) mesh_smooth 2026-05-12 00:46:40 input.stl ID: c85025c4d78c →" [ref=e183] [cursor=pointer]':
          - /url: "#/task/c85025c4d78c"
          - generic [ref=e184]: ✓ 完成
          - generic [ref=e185]: 网格平滑 (Smooth)
          - generic [ref=e186]:
            - generic [ref=e187]: mesh_smooth 2026-05-12 00:46:40 input.stl
            - generic [ref=e188]: "ID: c85025c4d78c"
          - generic [ref=e189]: →
        - 'link "✓ 完成 网格简化 (Simplify) mesh_simplify 2026-05-12 00:46:37 input.stl ID: 50a3c55ce0d9 →" [ref=e190] [cursor=pointer]':
          - /url: "#/task/50a3c55ce0d9"
          - generic [ref=e191]: ✓ 完成
          - generic [ref=e192]: 网格简化 (Simplify)
          - generic [ref=e193]:
            - generic [ref=e194]: mesh_simplify 2026-05-12 00:46:37 input.stl
            - generic [ref=e195]: "ID: 50a3c55ce0d9"
          - generic [ref=e196]: →
      - button "加载更多 (20)" [ref=e198] [cursor=pointer]
```

# Test source

```ts
  1   | /* e2e/workflow-editor.spec.js — Playwright E2E tests for workflow editor */
  2   | 
  3   | import { test, expect } from '@playwright/test';
  4   | 
  5   | const EDITOR_URL = '/#/workflows/editor/new';
  6   | 
  7   | test.describe('Workflow Editor', () => {
  8   | 
  9   |   test.beforeEach(async ({ page }) => {
  10  |     // Go to editor page
  11  |     await page.goto(EDITOR_URL);
  12  | 
  13  |     // Wait for the editor canvas to appear
> 14  |     await page.waitForSelector('#wf-canvas', { timeout: 10000 });
      |                ^ TimeoutError: page.waitForSelector: Timeout 10000ms exceeded.
  15  |     // Wait for LiteGraph to load from CDN and templates to be ready
  16  |     await page.waitForFunction(() => {
  17  |       return typeof window.LiteGraph !== 'undefined'
  18  |         && window.LiteGraph.LGraph
  19  |         && document.querySelector('#wf-canvas');
  20  |     }, { timeout: 15000 });
  21  |   });
  22  | 
  23  |   // ── Template Loading ────────────────────────────────────────────────
  24  | 
  25  |   test('clicking "Basic" template loads 2 nodes into the canvas', async ({ page }) => {
  26  |     // Click the "Basic" template button
  27  |     await page.click('button:has-text("Basic")');
  28  | 
  29  |     // Check that canvas contains nodes
  30  |     // LiteGraph renders into a canvas element, nodes are in memory not DOM
  31  |     const nodeCount = await page.evaluate(() => {
  32  |       if (!window.wfGraph || !window.wfGraph._nodes) return 0;
  33  |       return window.wfGraph._nodes.length;
  34  |     });
  35  | 
  36  |     expect(nodeCount).toBeGreaterThanOrEqual(2);
  37  |   });
  38  | 
  39  |   test('clicking "Text→Image" template loads 3 nodes', async ({ page }) => {
  40  |     await page.click('button:has-text("Text→Image")');
  41  | 
  42  |     const nodeCount = await page.evaluate(() => {
  43  |       if (!window.wfGraph || !window.wfGraph._nodes) return 0;
  44  |       return window.wfGraph._nodes.length;
  45  |     });
  46  | 
  47  |     expect(nodeCount).toBeGreaterThanOrEqual(3);
  48  |   });
  49  | 
  50  |   test('clicking "Print Ready" template loads 3 nodes', async ({ page }) => {
  51  |     await page.click('button:has-text("Print Ready")');
  52  | 
  53  |     const nodeCount = await page.evaluate(() => {
  54  |       if (!window.wfGraph || !window.wfGraph._nodes) return 0;
  55  |       return window.wfGraph._nodes.length;
  56  |     });
  57  | 
  58  |     expect(nodeCount).toBeGreaterThanOrEqual(3);
  59  |   });
  60  | 
  61  |   test('clicking "Full Pipeline" template loads 4 nodes', async ({ page }) => {
  62  |     await page.click('button:has-text("Full Pipeline")');
  63  | 
  64  |     const nodeCount = await page.evaluate(() => {
  65  |       if (!window.wfGraph || !window.wfGraph._nodes) return 0;
  66  |       return window.wfGraph._nodes.length;
  67  |     });
  68  | 
  69  |     expect(nodeCount).toBeGreaterThanOrEqual(4);
  70  |   });
  71  | 
  72  |   // ── Drag & Drop from Palette ────────────────────────────────────────
  73  | 
  74  |   test('palette items are visible', async ({ page }) => {
  75  |     // Palette items should be in the sidebar
  76  |     const paletteItems = await page.$$('.wf-palette-item');
  77  |     expect(paletteItems.length).toBeGreaterThan(0);
  78  |   });
  79  | 
  80  |   // ── Inspector Panel ─────────────────────────────────────────────────
  81  | 
  82  |   test('inspector panel shows info when a node is selected', async ({ page }) => {
  83  |     // First load a template so we have nodes
  84  |     await page.click('button:has-text("Basic")');
  85  | 
  86  |     // Click a node on the canvas — LiteGraph handles this via canvas events
  87  |     // Use evaluate to simulate node selection
  88  |     await page.evaluate(() => {
  89  |       if (!window.wfGraph || !window.wfGraph._nodes || !window.wfGraph._nodes.length) return;
  90  |       var node = window.wfGraph._nodes[0];
  91  |       if (window.wfCanvas && window.wfCanvas.onNodeSelected) {
  92  |         window.wfCanvas.onNodeSelected(node);
  93  |       }
  94  |     });
  95  | 
  96  |     // Inspector should now be visible (not display:none)
  97  |     const inspectorVisible = await page.evaluate(() => {
  98  |       var panel = document.getElementById('wf-inspector');
  99  |       return panel && panel.style.display !== 'none';
  100 |     });
  101 |     expect(inspectorVisible).toBe(true);
  102 |   });
  103 | 
  104 |   // ── Fit Button ──────────────────────────────────────────────────────
  105 | 
  106 |   test('fit button does not throw errors', async ({ page }) => {
  107 |     // Load a template first
  108 |     await page.click('button:has-text("Full Pipeline")');
  109 | 
  110 |     // Collect any console errors after clicking Fit
  111 |     const errors = [];
  112 |     page.on('pageerror', err => errors.push(err));
  113 | 
  114 |     // Click the Fit button
```