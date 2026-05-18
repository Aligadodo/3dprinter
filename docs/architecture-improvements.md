# 架构优化方案 — 2026-05-18

基于代码审查中保留的架构级问题，列出优化方向、收益和成本评估。

---

## 1. GPU 锁粒度细化

### 现状

`web/scheduler.py` 使用单一 `asyncio.Lock` 控制所有任务并发。relief/lithophane 等纯 CPU 任务也被锁阻塞，用户提交的 relief 任务需要排队等待 GPU 任务（如 TripoSR）完成。

```python
# scheduler.py:22
self.gpu_lock = asyncio.Lock()

# 所有类型任务执行前都 acquire
async with self.gpu_lock:
    await self._run_task(...)
```

### 方案

将锁分为两类：`gpu_lock`（仅 GPU 任务：TripoSR/Hunyuan/views）和 `cpu_semaphore`（限制 CPU 并发数，如 2-3 个 relief 可并行）。

```python
GPU_TASKS = {"triposr", "hunyuan", "views"}
CPU_MAX = 3

async def _acquire(self, pipeline_type):
    if pipeline_type in GPU_TASKS:
        await self.gpu_lock.acquire()
    else:
        await self.cpu_semaphore.acquire()

async def _release(self, pipeline_type):
    if pipeline_type in GPU_TASKS:
        self.gpu_lock.release()
    else:
        self.cpu_semaphore.release()
```

### 收益

| 维度 | 改善 |
|------|------|
| 吞吐量 | CPU 任务不再排 GPU 队，relief 等待时间从分钟级降到秒级 |
| 资源利用率 | GPU 任务独占时，CPU 可并行跑 2-3 个 relief |
| 用户体验 | 提交 relief 后立即开始，不用等 TripoSR 跑完 |

### 成本/风险

- 改动量：~30 行，`scheduler.py` 内改动
- 风险：低。GPU 任务仍串行，仅解除 CPU 任务对 GPU 锁的依赖
- 需要验证：relief/lithophane 的内存峰值，避免 CPU 并发过多导致 OOM

---

## 2. 子进程 stderr 持久化

### 现状

所有脚本通过 `subprocess.run(capture_output=True)` 调用，stderr 仅保存在内存中。`pipeline.py:25` 只截取前 500 字符：

```python
stderr = r.stderr[:500] if r.stderr else "unknown error"
```

对于 Hunyuan3D（日志可达数万行），关键错误常被截断，事后无法排查。

### 方案

将 stderr 写入任务工作目录下的文件（如 `task_dir/stderr.log`），摘要（最后 500 字符）仍写入 JSON result。

```python
stderr_log = os.path.join(task_dir, "stderr.log")
with open(stderr_log, "w", encoding="utf-8") as f:
    f.write(r.stderr)
result["stderr_log"] = stderr_log
result["stderr_tail"] = r.stderr[-500:] if r.stderr else ""
```

### 收益

| 维度 | 改善 |
|------|------|
| 可调试性 | Hunyuan3D 失败后可查看完整日志，不再盲调 |
| 磁盘成本 | 单任务日志通常 < 1MB，可接受 |
| 用户可见 | 任务详情页可增加"下载日志"链接 |

### 成本/风险

- 改动量：~40 行，涉及 `scheduler.py` + `pipeline.py` 的 `run_stage()`
- 风险：极低。纯增量行为，不改现有逻辑
- 需考虑：日志清理策略（与任务目录一同清理即可）

---

## 3. 数据库连接管理规范化

### 现状

`workflow_models.py` 中大量 `conn = get_db(); ...; conn.close()` 模式。若中间抛异常，`conn.close()` 不执行，SQLite 连接泄漏。

```python
def create_workflow_definition(name, graph_json, description=""):
    conn = get_db()
    conn.execute(...)
    conn.commit()
    conn.close()  # 异常时不执行
```

涉及文件：`models.py`（~15 处）、`workflow_models.py`（~20 处）。

### 方案

使用 context manager 封装，确保连接自动关闭：

```python
from contextlib import contextmanager

@contextmanager
def db():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

# 使用
def create_workflow_definition(name, graph_json, description=""):
    with db() as conn:
        conn.execute(...)
```

### 收益

| 维度 | 改善 |
|------|------|
| 可靠性 | 连接泄漏彻底消除 |
| 可维护性 | 去掉 35+ 处手动 `close()`，代码量减少 |
| 事务安全 | 异常时自动 rollback，避免脏数据 |

### 成本/风险

- 改动量：~100 行，涉及两个文件 35+ 处调用点
- 风险：中。改动面广，需要逐函数验证 commit/rollback 行为
- **建议分批进行**：先改 `workflow_models.py`，再改 `models.py`

---

## 4. Hunyuan3D 路径配置化

### 现状

`scripts/hunyuan-to-3d.py:88` 硬编码中文路径：

```python
base_dir = os.path.join(base_dir, "混元3D2.1+comfyui便携版+工作流+模型+环境")
```

在非中文 Windows 系统上可能损坏，用户必须通过 `--base-dir` 手动覆盖。

### 方案

优先级链：`--base-dir` CLI 参数 > `HUNYUAN3D_HOME` 环境变量 > 默认路径。

```python
default_base = os.environ.get("HUNYUAN3D_HOME") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "混元3D2.1+comfyui便携版+工作流+模型+环境"
)
base_dir = args.base_dir or default_base
```

同时在 `CLAUDE.md` 和 `.env.example` 中记录该环境变量。

### 收益

| 维度 | 改善 |
|------|------|
| 可移植性 | 非中文系统、CI/CD 环境可直接使用 |
| 可配置性 | 无需每次传 `--base-dir` |
| 多版本共存 | 切换 `HUNYUAN3D_HOME` 即可切换 ComfyUI 版本 |

### 成本/风险

- 改动量：~10 行
- 风险：极低。向后兼容，现有用户行为不变

---

## 5. workflow_models.py 动态 SQL 加固

### 现状

三处 `UPDATE` 使用 f-string 拼接列名：

```python
conn.execute(f"UPDATE workflow_definitions SET {', '.join(updates)} WHERE id = ?", params)
```

列名来自函数内硬编码列表，当前没有用户输入路径可到达。但如果将来增加从请求体动态构造列名的功能，存在 SQL 注入风险。

### 方案

方案 A（最小改动）：添加运行时断言，确保所有列名在预定义白名单内：

```python
ALLOWED_COLS = {"name", "description", "graph_json", "updated_at", ...}
assert all(col in ALLOWED_COLS for col in update_cols), f"illegal cols: {update_cols}"
```

方案 B（彻底）：使用 CASE WHEN 展开，每个参数显式写出：

```python
conn.execute("""
    UPDATE workflow_definitions SET
        name = COALESCE(?, name),
        description = COALESCE(?, description),
        ...
    WHERE id = ?
""", [params.get("name"), params.get("description"), ..., wf_id])
```

### 收益

| 维度 | 改善 |
|------|------|
| 安全性 | 方案 A 零成本防御，方案 B 彻底消除注入面 |
| 可审计性 | 显式列名便于代码审查和安全扫描 |

### 成本/风险

- 方案 A：~5 行，零风险
- 方案 B：~60 行，需要逐函数确认所有调用参数
- **建议先实施方案 A**，数据库重构时再考虑方案 B

---

## 优先级排序

| 优先级 | 项目 | 收益 | 成本 | 状态 |
|--------|------|------|------|------|
| 1 | GPU 锁粒度 | 高：并行度提升 2-3x | 低 | ✅ 已完成 (2026-05-18) |
| 2 | stderr 持久化 | 中：调试效率 | 低 | ✅ 已完成 (2026-05-18) |
| 3 | 动态 SQL 加固（方案 A） | 中：消除隐患 | 极低 | ✅ 已完成 (2026-05-18) |
| 4 | Hunyuan3D 路径配置化 | 低：中文本地系统无影响 | 极低 | ✅ 已存在（代码中已有 `HUNYUAN3D_HOME` 环境变量支持） |
| 5 | DB 连接 context manager | 中：可靠性 | 中 | 待分批做 |
