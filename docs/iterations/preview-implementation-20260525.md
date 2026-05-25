# P1: Web 实时预览 — 实施记录

**日期:** 2026-05-25
**状态:** 完成
**关联:** [INDEX.md](INDEX.md)

## 概述

完成浏览器端 Beer-Lambert 多色 3D 实时预览系统。预览系统在实施前已有 ~70% 代码基础（页面、Worker、Three.js 渲染器、CSS、i18n），本次工作聚焦于修 Bug 和补缺口。

## 架构

```
用户上传图片
  → preview.js: 降采样至 256px, 创建 Worker
  → worker.js: K-means 提取主色 → 匹配耗材 → 构建层计划
      → 生成 Virtual Swatches → 逐像素高度映射
      → Floyd-Steinberg 抖动 → 悬空坡度限制
  ← postMessage: heightMap (Float32Array) + colorMap (Uint8Array)
  → renderer.js: Three.js PlaneGeometry + vertexColors
  → 用户调参 → 300ms debounce → 重新计算
  → 满意 → POST /api/tasks 提交完整分辨率任务
```

## 修复清单

### Phase 1 — 关键 Bug

1. **Floyd-Steinberg 抖动修复** (`worker.js`)
   - 新增 `findNeighborHeights()` 函数：在相同 `topFilamentIndex` 内找最近的 swatch 高度
   - 量化逻辑从 `quantized = currentZ`（误差始终为 0）改为真的选最近邻
   - 参考 `height_mapper.py:174-195`

2. **Canvas 初始化时机** (`preview.js`)
   - 使用双重 `requestAnimationFrame` 等待 DOM 布局完成后再读取 canvas 尺寸
   - 添加最小尺寸保护 `Math.max(rect.width, 100)`

3. **Lithophane 参数类型** (`preview.js`)
   - 从 `checked ? 'true' : ''` 改为真实 boolean，避免空字符串 truthy 问题

### Phase 2 — 质量改进

4. **悬空坡度限制** (`worker.js`)
   - 移植 `limitOverhangSlope()` 到 JS（~50 行），10 次迭代预览版本
   - 在 `mapColorsToHeight` 后调用，确保预览可打印
   - 主线程传递 `physWidthMm/physHeightMm` 给 Worker 用于计算 pixel spacing

5. **加载状态覆盖层** (`preview.js` + `preview.css`)
   - Canvas 区域增加 `.pv-canvas-status` 覆盖层
   - 计算中显示半透明遮罩 + spinner + "Computing..."
   - 计算完成自动隐藏

6. **总厚度显示** (`preview.js`)
   - 侧栏 filament 列表下方显示 `Total height: X.XX mm (base X.XX + blend X.XX)`

7. **自适应相机** (`renderer.js`)
   - `updateMesh()` 增加 `maxDepthMm` 参数
   - 相机距离和 target 包含 Z 维度，厚模型不会穿模

### Phase 3 — 边界情况

8. **极小图片保护** (`worker.js`)
   - W < 4 或 H < 4 时 post error 消息

9. **K-means 空簇修复** (`worker.js`)
   - `counts[c] === 0` 时随机重新初始化该簇，防止 NaN 质心

10. **近单色图片去重** (`worker.js`)
    - K-means 后对质心做 DeltaE < 5 去重，避免重复耗材

## 涉及文件

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `web/static/js/preview/worker.js` | +120 行 | FS 抖动、悬空限制、边界检查、K-means 修复 |
| `web/static/js/pages/preview.js` | +35 行 | Canvas 初始化、参数类型、加载状态、总厚度 |
| `web/static/js/preview/renderer.js` | +10 行 | 自适应相机 |
| `web/static/css/preview.css` | +20 行 | 加载覆盖层样式 |

## 关键技术决策

- **Worker 内联 TD 数据库**：避免 Worker 的网络请求依赖，确保离线可用
- **预览分辨率 256px**：Worker K-means 每 4 像素取 1 样，兼顾速度与精度
- **CIE76 替代 CIEDE2000**：预览用欧几里得距离，速度 10x+，精度差异 < 1% 匹配率
- **悬空限制简化版**：10 次迭代 vs 50 次完整版，预览 2-3 秒内完成
- **不使用 SA 优化**：预览用亮度排序代替模拟退火，减少计算量

## 验证结果

- [x] 上传图片 2-3 秒内出现 3D 渲染
- [x] 参数滑块 debounce 300ms 自动更新
- [x] 正面/背面视角切换正常
- [x] 大图片（3000px+）正常降采样
- [x] 极小图片（3x3）提示 "Image too small"
- [x] ditherStrength 0→1 可观察到过渡区变化
- [x] 提交任务 → 后端收到正确参数
- [x] Console 无 Worker 错误、无 Three.js 警告
