# Multi-Color UX 简化：自动颜色提取替代手动 JSON 输入

> 2026-05-22 | 迭代目标：让用户只需选择"保留几种颜色"，无需手写 filament JSON

---

## 一、问题背景

多色打印管线在 Web UI 上线后，`multi_color_relief` 节点要求用户手动输入 JSON 格式的 filament 规格：

```json
[{"color":"#000000","name":"Black PLA","td":0.6}, {"color":"#FF0000","name":"Red PLA","td":3.5}]
```

这对非技术用户极其不友好 — 需要知道 TD 值、十六进制颜色码、JSON 语法。实际使用中，第一个测试任务就因 HTML 属性内双引号转义问题导致 JSON 被截断而直接失败（exit code 1）。

## 二、解决方案

**让用户只需选择一个整数 "Number of Colors"（2-8），系统自动完成：**

```
用户上传图片 → 选 N 种颜色 → K-means 提取主色 → DeltaE 匹配已知 filament → Beer-Lambert 叠色 → 输出 STL + 3MF
```

保留 `filaments` 参数作为高级选项（CLI 用户和测试脚本可用），但 Web UI 中不再暴露。

---

## 三、技术方案

### 3.1 颜色自动提取流水线

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ 输入图片      │ →   │ K-means 聚类     │ →   │ DeltaE 2000 匹配  │
│ (PIL Image)  │     │ sklearn KMeans   │     │ 已知 filament 库  │
└──────────────┘     └─────────────────┘     └──────────────────┘
                            │                        │
                    N 个 (R,G,B) 主色          N 个 filament dict
                            │                        │
                    按亮度排序（暗→亮）          {color, name, td}
                            └──────────┬─────────────┘
                                       ▼
                              ┌─────────────────┐
                              │ Beer-Lambert 叠色 │
                              │ optimize + blend  │
                              └─────────────────┘
```

### 3.2 关键模块改动

#### `scripts/multi_color/td_database.py`

新增两个组件支撑自动匹配：

**A) `_COLOR_RGB` — 颜色名 → sRGB 近似值映射表（33 种颜色）**

```python
_COLOR_RGB = {
    "black": (15, 15, 15), "white": (245, 245, 245),
    "red": (210, 40, 40), "blue": (30, 80, 200),
    "green": (30, 150, 60), "yellow": (245, 220, 30),
    # ... 33 种颜色
}
```

**B) `find_closest_filaments(rgb_list, preferred_brand=None)`**

- 输入：K-means 提取的 RGB 元组列表
- 对每个 RGB，用 `rgb_to_lab()` 转换到 Lab 空间
- 遍历 `KNOWN_TD` 中所有有 RGB 参考值的 filament，计算 `delta_e_2000()` 色差
- 选择色差最小的 filament，去重后按亮度排序（暗→亮，即底部→顶部）
- 支持 `preferred_brand` 品牌优先匹配

#### `scripts/multi_color/__init__.py`

`compute_color_layers()` 新增 `num_colors` 参数 + 自动提取逻辑：

```python
def compute_color_layers(image_path, filaments=None, num_colors=None, ...):
    # ...
    if filaments is None:
        if num_colors and num_colors >= 2:
            dominant_rgbs = _extract_dominant_colors(img, num_colors)
            filaments = find_closest_filaments(dominant_rgbs)
        else:
            filaments = [
                {"color": "#000000", "name": "Black PLA", "td": 0.6},
                {"color": "#FFFFFF", "name": "White PLA", "td": 4.4},
            ]
```

新增 `_extract_dominant_colors(img, num_colors)` — 使用 sklearn KMeans 对图像像素做聚类，取每 4 个像素采样以加速，返回按亮度排序的 RGB 元组列表。

#### `scripts/image-to-relief.py`

新增 `--num-colors` CLI 参数（int, 2-8），传递给 `compute_color_layers()`。`--filaments` 改为可选（仅在有值时 `json.loads`）。

### 3.3 Web UI 改动

| 文件 | 改动 |
|------|------|
| `web/node_types.py` | `multi_color_relief` / `multi_color_lithophane` 的 params 从 `filaments`(string) 改为 `num_colors`(int, 2-8, default 4) |
| `web/schemas.py` | 对应 pipeline type 的 params 同步更新 |
| `web/scheduler.py` | param_map: `num_colors → --num-colors`，新增 `--multi-color` / `--lithophane` 标志 |
| `web/workflow_engine.py` | 新增 `swaps` / `color_preview` 结果路径映射 |

### 3.4 HTML 转义 Bug 修复

发现并修复了一个关键前端 bug：`<input value="...">` 属性中嵌入含双引号的 JSON 字符串时，`"` 会提前截断 value 属性。

**修复：** 在 `new-task.js` 和 `wf-editor.js` 三处对 string 类型参数默认值使用 `escHtml()` 转义：

```javascript
// 修复前：JSON 被截断
`<input value="${p.default||''}">`

// 修复后：安全转义
`<input value="${escHtml(String(p.default||''))}">`
```

---

## 四、文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/multi_color/td_database.py` | 修改 | 新增 `_COLOR_RGB` + `find_closest_filaments()` |
| `scripts/multi_color/__init__.py` | 修改 | 新增 `num_colors` 参数 + `_extract_dominant_colors()` |
| `scripts/image-to-relief.py` | 修改 | 新增 `--num-colors` CLI 参数 |
| `web/node_types.py` | 修改 | params 从 `filaments` 改为 `num_colors` |
| `web/schemas.py` | 修改 | pipeline type params 同步 |
| `web/scheduler.py` | 修改 | param_map + 标志位更新 |
| `web/workflow_engine.py` | 修改 | 新增结果路径映射 |
| `web/static/js/pages/new-task.js` | 修改 | `escHtml()` 修复 |
| `web/static/js/pages/wf-editor.js` | 修改 | `escHtml()` 修复（2 处） |
| `web/static/locales/en.json` | 修改 | 新增双语标签 |
| `web/static/locales/zh.json` | 修改 | 新增双语标签 |

---

## 五、验证结果

- **测试套件：** 46/46 PASSED
- **端到端验证：** `compute_color_layers('bars_3color.png', num_colors=3)` 正确提取 Black/Red/White 并映射到 Bambu 对应 filament（TD 0.6/3.5/4.4）
- **向后兼容：** `--filaments` JSON 参数在 CLI 模式下仍然可用

---

## 六、相关文档

- [多色3D打印技术调研 & 实施方案](multi-color-research-20260522.md)
- [Multi-Color Pipeline — Functional Test Report](multi-color-test-report-20260522.md)
