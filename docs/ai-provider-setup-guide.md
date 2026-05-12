# 中国 AI 文生图供应商 — API Key 获取指南

本文档指导你获取火山引擎和智谱AI的 API Key，用于 3D Print Pipeline 的 text_to_image 节点。

---

## 一、火山引擎 Seedream（豆包图像创作）★ 推荐首选

**优势**: 4K 分辨率、原生 OpenAI 兼容、联网检索、CoT 推理

### 1. 注册账号

1. 打开 [火山引擎官网](https://www.volcengine.com/)
2. 点击右上角 **"免费注册"**，支持手机号/邮箱注册
3. 登录后进入 [火山方舟大模型服务平台](https://console.volcengine.com/ark)

### 2. 获取 API Key

1. 在火山方舟控制台左侧菜单，找到 **"API Key 管理"** 或访问：
   ```
   https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey
   ```
2. 点击 **"创建 API Key"**
3. 给 Key 起个名字（如 `3dprint-pipeline`），点击确定
4. **复制并保存**生成的 Access Key（只显示一次！）

### 3. 开通模型服务

火山引擎采用**模型广场 + 开通服务**模式：

1. 在控制台左侧进入 **"模型广场"**
2. 搜索 **"Seedream"**，找到最新版本（当前：`Seedream 5.0 Lite`）
3. 点击模型卡片 → **"开通服务"**
4. 同意协议，选择按量计费（有 200 张免费额度）

### 4. 配置到项目中

在本机设置环境变量（或直接替换 `${VOLCENGINE_API_KEY}`）:

```powershell
# Windows PowerShell - 临时设置
$env:VOLCENGINE_API_KEY = "your-api-key-here"

# Windows - 永久设置（推荐）
[System.Environment]::SetEnvironmentVariable('VOLCENGINE_API_KEY', 'your-api-key-here', 'User')
```

配置文件中已预填：
- 模型: `doubao-seedream-5-0-260128` (5.0 Lite)
- 默认尺寸: `2048x2048`
- 可选尺寸: `1024x1024`, `2048x2048`, `4096x4096`

### 5. 免费额度与定价

| 项目 | 说明 |
|------|------|
| **新用户免费** | 200 张图像 |
| **按量计费** | 约 ¥0.03-0.12/张（取决于尺寸） |
| **图片有效期** | b64_json 模式直接本地存储，无过期 |
| **并发限制** | 默认 5 QPS |

---

## 二、智谱AI CogView（GLM 系列）

**优势**: 完全免费版可用、首个支持生成汉字、适合开发测试

### 1. 注册账号

1. 打开 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 点击 **"注册/登录"**，支持手机号/微信扫码
3. 登录后进入 [控制台](https://open.bigmodel.cn/usercenter/apikeys)

### 2. 获取 API Key

1. 在左侧菜单找到 **"API Keys"**
2. 点击 **"创建新的 API Key"**
3. 复制并保存（只显示一次！）

### 3. 配置到项目中

```powershell
# Windows PowerShell - 临时设置
$env:ZHIPU_API_KEY = "your-api-key-here"

# Windows - 永久设置（推荐）
[System.Environment]::SetEnvironmentVariable('ZHIPU_API_KEY', 'your-api-key-here', 'User')
```

⚠️ **注意**：默认使用 `cogview-3-flash`（免费模型）。如需更高质量，可将 `providers.yaml` 中 zhipu 的 `model` 改为 `cogview-4-250304`（付费，约 ¥0.05/张）。

### 4. 免费额度与定价

| 模型 | 价格 | 说明 |
|------|------|------|
| **CogView-3-Flash** | **免费** | 快速生成，适合开发测试 |
| CogView-4 (standard) | 约 ¥0.05/张 | 5-10秒出图 |
| CogView-4 (HD) | 约 ¥0.10/张 | 约20秒，更精细 |
| **图片有效期** | 30 天 | API 返回 URL，系统自动下载到本地 |

### 5. 支持的尺寸

- `1024x1024` (正方形，默认)
- `768x1344` / `1344x768` (竖版/横版)
- `864x1152` / `1152x864`
- `1440x720` / `720x1440` (超宽/超高)

---

## 三、验证配置

重启服务后，在 Workflow Editor 中添加 `text_to_image` 节点，即可在 **provider** 下拉菜单中看到：

```
volcengine  →  火山引擎 Seedream (豆包)
zhipu       →  智谱AI CogView
openai      →  OpenAI DALL-E 3
stability   →  Stability AI
```

或在浏览器中直接访问 API 查看可用 provider 列表：
```
http://localhost:8080/api/text2img/providers
```

---

## 四、目前配置状态

| Provider | 状态 | API Key | 模型 |
|----------|------|---------|------|
| `volcengine` | ✅ enabled | 需配置 `VOLCENGINE_API_KEY` | seedream-5-0-lite |
| `zhipu` | ✅ enabled | 需配置 `ZHIPU_API_KEY` | cogview-3-flash (免费) |
| `openai` | ❌ disabled | 海外，已禁用 | dall-e-3 |
| `stability` | ❌ disabled | 海外，已禁用 | stable-image-generate |

配置好 API Key 环境变量后回到这里，我继续帮你验证端到端的 text_to_image → relief 工作流。
