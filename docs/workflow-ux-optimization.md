# Workflow UX 优化方案

> 实施日期: 2026-05-16 | 版本: 1.0

## 优化概览

针对工作流编辑器和运行页面的 5 项交互优化，提升可读性和易用性。

---

## 优化 1: 统一中英文双语显示

### 问题
工作流节点在画板、面板、运行页面上中英文显示不一致，有的只显示中文，有的只显示英文，尤其在任务运行页几乎全是英文。

### 方案
创建 `getBilingualLabel(nt)` 函数，统一返回 `"中文 English"` 格式，不再根据当前语言环境切换。

```javascript
function getBilingualLabel(nt) {
  const zh = nt.label_zh || nt.label;
  const en = nt.label;
  if (!zh || zh === en) return en || '';
  return zh + ' ' + en;
}
```

### 影响范围
| 文件 | 修改内容 |
|------|---------|
| `web/static/js/pages/wf-editor.js` | 画板节点标题、面板列表、工具提示、属性面板标题、运行参数弹窗 |
| `web/static/js/pages/wf-runner.js` | DAG 节点标题、Tab 标签、概览卡片 |
| `web/static/js/pages/task-detail.js` | 工作流上下文节点标签 |
| `web/static/js/components/node-detail.js` | 节点详情面板标题 |
| `web/static/js/pages/new-task.js` | 新建任务工作流表单 |


## 优化 2: 节点命名优化

### 问题
节点命名使用 LiteGraph 内部自动递增的 ID（如 1、5、6、7），在运行页面 Tab 上完全看不出是哪个节点。

### 方案
自动生成带类型计数器的标题：`"文件输入 File Input #1"`、`"浮雕 Relief #2"`。

- 编辑器拖放节点时自动分配标题
- 运行页面使用相同命名规则显示

```javascript
function generateNodeTitle(typeId, nodeTypes, graph) {
  const nt = nodeTypes.find(n => n.id === typeId);
  const base = getBilingualLabel(nt);
  let count = 0;
  graph._nodes.forEach(n => {
    if ((n._wfTypeId || (n.type || '').replace(/^wf_/, '')) === typeId) count++;
  });
  return base + ' #' + (count + 1);
}
```

### 影响范围
| 文件 | 修改内容 |
|------|---------|
| `web/static/js/pages/wf-editor.js` | 拖放自动命名、模板预设标题 |
| `web/static/js/pages/wf-runner.js` | Tab 标签、概览卡片、DAG 节点 |
| `web/static/js/pages/task-detail.js` | 工作流上下文节点 |


## 优化 3: 显示上游连线信息

### 问题
任务运行时，节点入参已通过连线连好，但详情面板仍显示"无输入 (根节点)"，用户看不到从哪个上游节点获取数据。

### 方案
在 `renderNodeDetailPanel` 中新增 `upstreamEdges` 参数。对于已连线但上游尚未产生输出的端口，显示虚线卡片标明上游来源：

```
┌──────────────────┐
│ 📥 image         │
│ ← 文件输入 File Input #1.file  │
│ (等待上游输出)    │
└──────────────────┘
```

### 影响范围
| 文件 | 修改内容 |
|------|---------|
| `web/static/js/components/node-detail.js` | 新增 `upstreamEdges` 参数，渲染待定上游卡片 |
| `web/static/js/pages/wf-runner.js` | 构建 `upstreamInfo` 传入详情面板 |
| `web/static/js/pages/task-detail.js` | 同上 |
| `web/static/locales/zh.json` | 新增 `node.upstreamPending` 键 |
| `web/static/locales/en.json` | 新增 `node.upstreamPending` 键 |


## 优化 4: 前端保存校验

### 问题
前端保存工作流时无校验，可以保存孤立节点、无下游的输入节点等不合理配置。

### 方案
创建 `workflow-validator.js` 校验模块，保存前弹窗提示。

### 校验规则
| 级别 | 规则 |
|------|------|
| ERROR | 工作流无节点 |
| ERROR | 节点 ID 重复 |
| WARNING | 输入节点无下游消费者 |
| WARNING | 处理节点必填端口未连接 |
| WARNING | 输出节点无输入 |
| WARNING | 节点孤立（无任何连接） |

- **ERROR**: 阻止保存，必须修复
- **WARNING**: 弹窗确认后仍可保存

### 新文件
- `web/static/js/lib/workflow-validator.js`

### 新 i18n 键
`wf.validation.*` 系列（title, errors, warnings, saveAnyway, cancel + 各规则消息）


## 优化 5: 自动格式化布局

### 问题
工作流节点位置完全手动拖放，在单一流水线、多输入、多输出、多分支等场景下显示混乱。

### 方案
创建 `workflow-layout.js` 布局模块，实现分层层次化布局算法（简化 Sugiyama）。

### 算法
1. **构建邻接表**: 从边列表建立上下游关系
2. **分层分配**: 根节点（入度=0）→ 第 0 层，其余 → max(上游层)+1
3. **层内排序**: 按类别（输入→生成→处理→输出）→ 节点 ID
4. **位置计算**: X = 层号 × 280px, Y = 层内居中
5. **应用**: 设置 `node.pos`，重绘画布

### 工具栏按钮
在保存按钮旁增加 🔧 格式化按钮，点击即自动排列。

### 新文件
- `web/static/js/lib/workflow-layout.js`


## 文件清单

### 新建文件
| 文件 | 用途 |
|------|------|
| `web/static/js/lib/workflow-validator.js` | 前端校验规则引擎 |
| `web/static/js/lib/workflow-layout.js` | 层次化自动布局算法 |
| `docs/workflow-ux-optimization.md` | 本文档 |

### 修改文件
| 文件 | 修改要点 |
|------|---------|
| `web/static/js/pages/wf-editor.js` | 双语标签、自动命名、校验弹窗、格式化按钮 |
| `web/static/js/pages/wf-runner.js` | 双语标签、带计数器标签、上游连线信息 |
| `web/static/js/pages/task-detail.js` | 双语标签、上游连线信息 |
| `web/static/js/components/node-detail.js` | 双语标题、上游待定卡片渲染 |
| `web/static/js/pages/new-task.js` | 双语标签 |
| `web/static/locales/zh.json` | 新增校验/格式化/上游连线 i18n 键 |
| `web/static/locales/en.json` | 同上 |
| `web/static/css/workflow.css` | 校验弹窗样式、待定上游卡片样式 |

## 验证方法

1. 打开工作流编辑器，从面板拖放节点 → 验证双语标签+自动编号
2. 多次拖放同一类型节点 → 验证计数器递增
3. 连线后保存并运行 → 查看运行页 Tab 标签和节点详情
4. 创建孤立节点尝试保存 → 验证校验弹窗
5. 点击格式化按钮 → 验证节点自动排列
6. 切换中英文 → 验证标签始终显示双语
