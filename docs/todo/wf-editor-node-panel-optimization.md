# 工作流编辑器节点分类优化方案

## 背景问题

1. **节点平铺展示**：所有 28 个节点类型无差别展示，新用户难以发现核心功能
2. **不常用节点干扰**：mesh_align、mesh_cut、mesh_stitch、mesh_decorate 等参数复杂、难理解、功能受众窄，与常用节点混在一起造成干扰
3. **缺乏搜索/过滤**：无法快速定位节点
4. **无树形展开**：所有分类平铺，视觉噪音大

## 方案设计

### 1. 节点分类重组

| 分类 | ID | 说明 | 可见性 |
|------|-----|------|--------|
| 输入 | `input` | 文件/文本输入 | 默认展示 |
| 生成 | `generate` | TripoSR、Hunyuan、text2img | 默认展示 |
| 处理 | `process` | 浮雕、简化、修复、views | 默认展示 |
| 输出 | `output` | 文件输出 | 默认展示 |
| **高级Mesh** | `mesh_ops` | mesh_boolean/stitch/cut/align/decorate | **折叠** |
| **其他** | `other` | 杂项 | **折叠** |

### 2. 侧边栏交互优化

```
[搜索框 ________________________]
[模板按钮 x4]

▼ 输入 (2)
  ○ 文件输入
  ○ 文本输入

▶ 生成 (3)
    TripoSR
    Hunyuan3D
    文生图

▼ 处理 (5)
    浮雕 / Lithophane
    分层彩色浮雕
    网格修复
    ...

▶ 高级Mesh (5)  ← 默认折叠
    Mesh Boolean
    Mesh 缝合
    ...

[其他] (1)      ← 默认折叠
```

- 分类标题可点击展开/折叠
- 高级分类默认收起，用户主动展开
- 搜索时：全局展开，所有匹配项高亮

### 3. 实现计划

**Phase 1：数据层**
- [ ] `web/node_types.py`：为 mesh 节点设置 `category="mesh_ops"`
- [ ] `CATEGORIES` 新增 `mesh_ops` 和 `other` 条目
- [ ] 确认 inline 节点（mesh_transform、mesh_select）的 category

**Phase 2：前端 UI**
- [ ] `wf-editor.js` 侧边栏改造为可折叠树形
- [ ] 添加搜索框（按名称过滤，搜索时展开所有匹配分类）
- [ ] 分类默认状态：mesh_ops 和 other 折叠，其他展开
- [ ] 3D 相关建议方案文档

**Phase 3：其他优化**
- [ ] docs/todo/3d-model-editing.md（3D 可视化交互方案）

## 实现细节

### 侧边栏 HTML 结构
```html
<div id="wf-palette">
  <input id="node-search" placeholder="搜索节点..." />
  <div class="template-buttons">...</div>
  <div id="node-tree">
    <div class="cat-section" data-cat="input">
      <div class="cat-header">输入</div>
      <div class="cat-nodes">...</div>
    </div>
    ...
  </div>
</div>
```

### CSS 需求
- `.cat-section.collapsed .cat-nodes { display: none }`
- `.cat-header` 带展开/折叠箭头
- `.search-match` 高亮
- `.cat-section.collapsed` 箭头旋转

### 分类折叠逻辑
```javascript
const DEFAULT_COLLAPSED = ['mesh_ops', 'other'];

// 初始化时
catSections.forEach(el => {
  const cat = el.dataset.cat;
  if (DEFAULT_COLLAPSED.includes(cat)) {
    el.classList.add('collapsed');
  }
});

// 搜索时：全部展开
// 搜索清空时：恢复默认折叠状态
```