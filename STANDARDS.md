# 3D Print Pipeline — 项目标准与规范清单

> 本文档是项目协作的核心规范参考，供 Claude Code 和开发者共同遵守。
> 每次重大迭代后更新，变更记录见文件历史。

---

## 一、业务设计目标

### 1.1 核心使命

将一张图片（照片、渲染图、插画）转换为 **Bambu Lab 打印机可直接打印的 STL 文件**，中间可能经过 AI 3D 生成、网格修复、浮雕生成等阶段。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **硬件约束优先** | 6GB 显存 RTX 3060 Laptop 为硬约束，所有优化不得突破此边界 |
| **零依赖 CLI** | CLI 脚本独立运行，不依赖 Web 层，可直接通过命令行调用 |
| **JSON 作为协议** | 所有脚本通过 stdout 输出结构化 JSON，实现与上层解耦 |
| **渐进增强** | 快速预览（TripoSR 2s）→ 高质量（Hunyuan3D 30min）分层提供 |
| **打印就绪** | 输出文件直接可用于 Bambu Studio，不需额外转换 |

### 1.3 功能边界

- ✅ 支持：图片 → 3D网格 / 浮雕 / 夜灯 / 六视图
- ✅ 支持：网格修复、减面、平滑、缩放
- ❌ 不支持：多视角图片输入（代码存在但未启用）
- ❌ 不支持：PBR 纹理生成（WIP，VRAM 不足）
- ❌ 不支持：自动排版、层高规划（未来路线图）

---

## 二、技术规范

### 2.1 硬件与运行时

```
GPU:     RTX 3060 Laptop 6GB
RAM:     64GB
OS:      Windows 11 (也支持 Linux/macOS)
Python:  3.12 (system)
CUDA:    12.1+
```

| 引擎 | 显存 | RAM | 磁盘 | 推理速度 |
|------|------|-----|------|---------|
| TripoSR | 3.5GB | 8GB+ | ~3GB | ~2s |
| Hunyuan3D-2.1 | 6.86GB | 32GB+ | ~50GB | 67-287s/step |
| Relief/Lithophane | <1GB | 任意 | — | <5s |

### 2.2 目录结构规范

```
3dprint/
├── scripts/          # 所有CLI脚本（不可被上层直接import，仅通过subprocess调用）
├── web/              # Web服务（不修改CLI脚本行为）
├── models/           # TripoSR 权重（model.ckpt + config.yaml）
├── config/           # providers.yaml + .env
├── output/           # 生成文件（lithophane/ relief/ views/ tasks/）
├── docs/             # 文档（index.html + 迭代记录）
├── triposr/src/      # TripoSR 推理代码（tsr/ 包）
├── hunyuan3d/        # Hunyuan3D 分析文档
└── 混元3D2.1+.../     # ComfyUI 便携包（含中文路径）
```

> 注意：`output/` 是唯一允许脚本直接写入的输出目录。

### 2.3 脚本输出规范

所有 `scripts/` 下的脚本必须：

1. **stdout 输出 JSON**（不含日志污染）
2. **错误时输出** `{"error": "...", "code": "...", "details": {...}}`
3. **成功时输出** 包含 `output`（文件路径）字段
4. **禁止** 在 stdout 输出非 JSON 内容（调试信息用 stderr 或日志文件）

```python
# 正确示例
if __name__ == "__main__":
    result = some_function(...)
    if "error" in result:
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

### 2.4 路径规范

- 写入 `output/` 时，避免 `output/output/` 嵌套
- 输入文件在 `output/` 时，输出保持同级（不新建子目录）
- 中文路径：`混元3D2.1+...` 使用嵌入式 Python 处理

### 2.5 VRAM 管理

```
# Hunyuan3D on 6GB — 必须使用 shared memory
torch.float16  # 强制半精度
--steps 10      # 预览模式
mm.unload_all_models()  # 任务结束时释放
```

### 2.6 错误处理分级

| 级别 | 行为 | 示例 |
|------|------|------|
| 可恢复 | 返回 JSON + 退出码 0 | 缺少可选依赖 |
| 用户错误 | 返回 JSON + 退出码 1 | 文件不存在、参数越界 |
| 系统错误 | stderr + 退出码 1 | CUDA 不可用、内存不足 |

---

## 三、Web 服务规范

### 3.1 API 设计原则

- **REST + SSE**：任务管理用 REST，进度推送用 SSE
- **无认证**：单用户 LAN 工具，信任本地网络
- **路径安全**：所有文件访问必须限制在 `PROJECT_ROOT` 内

### 3.2 数据库规范

- 使用 SQLite WAL 模式（`tasks.db`）
- `tasks` 表：任务记录
- `output_files` 表：输出文件追踪（ON DELETE CASCADE）
- `workflow_definitions`：工作流定义
- `workflow_instances`：工作流实例
- `workflow_node_runs`：节点执行记录

### 3.3 GPU 调度

```python
gpu_lock = asyncio.Lock()  # 全局单一锁
# GPU任务（TripoSR/Hunyuan3D）必须获取锁后执行
# CPU任务（relief/views/repair）绕过锁并发执行
```

### 3.4 工作流引擎

- 使用 Kahn's 算法做拓扑排序
- 支持 replay（从指定节点重新执行）
- 节点间通过文件路径传递数据（非二进制）
- 取消标志在 0.5s 超时循环中每轮检查

### 3.5 前端架构

- Vanilla JS ES Modules（零构建工具）
- 懒加载页面模块
- Hash 路由（`#/dashboard`、`#/workflows/editor/<id>`）
- i18n：dot-path lookup + localStorage 持久化

---

## 四、代码质量规范

### 4.1 脚本命名

- 主入口：`image-to-3d.py`、`mesh-repair.py` 等
- 每个脚本对应一种功能，文件名即功能描述
- 禁止在一个脚本里混合多种功能

### 4.2 函数设计

- `generate_xxx()` — 核心生成函数，可被 import 调用
- `_helper_func()` — 内部私有函数（以下划线前缀）
- 返回值：字典（包含 `output`、`format`、`engine`、`log` 等标准键）

### 4.3 测试覆盖

**测试金字塔：**

```
           ┌──────────┐
           │ E2E      │  Playwright 浏览器测试
           │ ~6 tests │  验证完整用户交互流程
           ├──────────┤
           │ 集成     │  vitest + LiteGraph mock
           │ ~64 tests│  验证 WFNode ↔ LiteGraph API 兼容
           ├──────────┤
           │ 单元     │  vitest 纯函数测试
           │ ~44 tests│  验证独立 JS 函数逻辑
           ├──────────┤
           │ Schema   │  Python 一致性检查
           │ ~232 tests│  验证前后端数据结构一致
           ├──────────┤
           │ 后端     │  Python 脚本/API/引擎测试
           │ ~X tests │  已有: test_scripts/api/workflow_engine
           └──────────┘
```

**后端测试：**

| 测试类型 | 覆盖目标 | 测试文件 |
|----------|---------|---------|
| 输出格式测试 | 验证 JSON 结构完整性 | `tests/test_scripts.py` |
| 路径嵌套测试 | 确保无 `output/output/` 问题 | `tests/test_scripts.py` |
| 错误恢复测试 | 缺模型、缺依赖时的错误处理 | `tests/test_scripts.py` |
| API 集成测试 | REST + SSE + 工作流 CRUD/执行 | `tests/test_api.py` |
| 工作流引擎测试 | 拓扑排序、边标准化、端口映射 | `tests/test_workflow_engine.py` |
| 错误处理测试 | 404/400 边界、参数验证 | `tests/test_api.py` |
| Schema 一致性测试 | 前后端节点类型/端口名一致 | `tests/test_schema_consistency.py` |

**前端测试：**

| 测试类型 | 覆盖目标 | 测试文件 |
|----------|---------|---------|
| LiteGraph mock 测试 | 验证测试环境正常 | `tests/frontend/smoke.test.js` |
| 核心函数测试 | `_findSlot`、`_isTypeCompatible`、`createLiteGraphNodeClass`、`WFNode.connect` | `tests/frontend/wf-core.test.js` |
| 适配层测试 | 所有 litegraph-adapter.js 导出函数的正确性和降级行为 | `tests/frontend/litegraph-adapter.test.js` |
| E2E 测试 | 工作流编辑器模板加载、拖拽、inspector、fit 按钮 | `e2e/workflow-editor.spec.js` |

**运行方式：**
```bash
# 后端单元测试（无需启动服务器）
python tests/test_scripts.py
python tests/test_workflow_engine.py
python tests/test_schema_consistency.py

# 后端集成测试（需要服务器运行）
python tests/test_api.py --start-server

# 前端单元测试（无需启动服务器）
npm test                    # vitest run tests/frontend/
npm run test:frontend:watch # vitest (watch mode)

# E2E 测试（需要服务器运行）
npm run test:e2e            # playwright test
npm run test:e2e:ui         # playwright test --ui

# 一键运行全部测试
run-tests.bat               # Windows
./run-tests.sh              # Unix
```

**新增脚本时必须补充的测试用例（后端）：**
1. 基本 JSON 输出格式（含必要字段：`output`、`log`）
2. 错误输入时的 error JSON 契约
3. 路径嵌套检测（输入在 `output/` 时输出不新建 `output/output/`）
4. 参数边界值测试（如 max_depth=0、colors 超限）
5. 可选：进度事件流（`{"event":"progress",...}` 行）

**新增前端组件/函数时必须补充的测试用例：**
1. 纯函数的输入-输出正确性（正确/边界/错误三类输入）
2. 涉及 LiteGraph API 的代码必须通过适配层调用，适配层函数必须有测试
3. 新工作流模板的类型名和端口名必须在 `test_schema_consistency.py` 的 TEMPLATES 字典中有对应条目
4. E2E：新增关键用户交互路径必须补充 Playwright 测试场景

### 4.4 文档更新触发

以下情况必须更新文档：
- 新增脚本/参数
- 改变输出格式
- 新增工作流节点
- 修改硬件约束

---

## 五、文件格式规范

### 5.1 输出格式优先级

```
STL  > OBJ  > 3MF  > GLB
通用打印  保留颜色  支持Bambu  实验性
```

### 5.2 浮雕/夜灯格式

- Relief/Lithophane：高度场三角网格，base_thickness + max_depth 结构
- Layered Relief：单 mesh + Z-band 颜色分层，配套 color_map.json
- 3MF：Bambu Studio 兼容格式，颜色信息嵌入 metadata

### 5.3 OBJ 导出（含颜色）

使用 `vc` 扩展格式：
```
v x y z
vc r g b
v x y z
vc r g b
...
```
禁止将颜色行写为独立的 `v` 行（会导致几何被破坏）。

---

## 六、安全规范

### 6.1 文件访问

```python
# ✅ 正确：规范路径后检查前缀
full_path = os.path.normpath(os.path.join(PROJECT_ROOT, file_path))
if not full_path.startswith(os.path.normpath(PROJECT_ROOT)):
    raise HTTPException(403)

# ❌ 错误：直接用 realpath（可能追随符号链接导致绕过）
```

### 6.2 用户输入

- 所有 CLI 参数必须验证类型和范围
- 文件路径检查存在性和可读性
- 禁止将用户输入直接拼接入 subprocess 命令（用 list + shlex 分离）

### 6.3 敏感信息

- API 密钥通过 `config/.env` 管理，不进入代码
- 使用 `providers.is_key_configured()` 检查密钥是否配置

---

## 七、项目迭代规范

### 7.1 迭代记录

每次设计决策变更，自动保存到 `docs/iterations/YYYY-MM-DD-HHMMSS-name.md`。
INDEX.md 由系统自动更新。

### 7.2 CLAUDE.md 更新

当发生以下变化时，更新 `CLAUDE.md`：
- 新增脚本或参数
- 目录结构变化
- 硬件约束变化

### 7.3 Bug 修复规范

```
严重程度：
🔴 高 — 崩溃、数据丢失、安全问题
🟡 中 — 功能异常、边界条件错误
🟢 低 — 代码风格、可接受的风险

修复状态：
✅ 已修复 — 有代码变更
⚠️ 需验证 — 需要人工测试确认
🛡️ 设计正确 — 误报或已知可接受风险
```

### 7.4 Git 提交规范

**禁止 `git push --force`**：force push 会覆盖远程历史，可能造成协作者丢失提交。应使用 `git pull --rebase` 合并远程更新，或与协作者协调后 merge。

```
# 正确：先拉取再推送
git pull --rebase
git push

# 错误：强制覆盖远程
git push --force
```

**提交信息规范：**
- 首行：不超 72 字，简述本次变更内容
- 使用中文描述，动词用现在时
- 结尾需附 Co-Authored-By

**Commit message 格式：**
```
<类型>: <简短描述>

<详细说明（可选）>

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

类型：`feat` / `fix` / `docs` / `refactor` / `test` / `chore`

---

## 八、快捷参考

### 常用命令

```bash
# CLI
python scripts/pipeline.py photo.jpg --engine triposr --views
python scripts/image-to-relief.py photo.jpg --lithophane --colors 4
python scripts/mesh-repair.py model.glb --output stl --scale 0.5

# Web
python start-server.py
curl http://127.0.0.1:8080/api/tasks

# 测试
python -c "import sys; sys.path.insert(0,'scripts'); from image_to_3d import generate_3d; print(generate_3d('photo.jpg'))"
```

### VRAM 估算公式

```
TripoSR:     3.5GB 固定
Hunyuan3D:   7.4GB (fp16) = DiT(3B) + VAE(328M) + conditioner(304M)
             6GB 卡会溢出到共享内存，推理速度降至 1/4
```

### 端口映射参考

| 节点类型 | 输入端口 | 输出端口 |
|----------|----------|---------|
| relief | image | stl, color_preview |
| triposr | image | mesh, preview |
| hunyuan | image | mesh, preview |
| views | mesh | grid, views_dir |
| repair | mesh | repaired_mesh |
| layered_relief | image | stl, 3mf, color_map, color_preview |