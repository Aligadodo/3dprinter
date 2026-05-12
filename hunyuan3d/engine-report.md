# Hunyuan3D-2.1 引擎分析报告

## 基本信息

| 项目 | 内容 |
|------|------|
| 名称 | Hunyuan3D-2.1 (混元3D-2.1) |
| 开发者 | 腾讯混元 |
| 开源协议 | 待确认 (腾讯开源) |
| 论文 | arXiv (待查) |
| 代码仓库 | github.com/Tencent/Hunyuan3D-2 |
| 发布时间 | 2025 |

## 技术特点

### 相比 TripoSR 的优势

| 特性 | TripoSR | Hunyuan3D-2.1 |
|------|---------|---------------|
| 几何精度 | 中 | 高 |
| UV 纹理 | 仅顶点色 | 独立 UV 纹理 |
| 多视图输入 | 不支持 | 支持 |
| 材质输出 | 无 | PBR 材质 |
| VRAM 需求 | ~2.5GB | ~8-16GB |
| 推理时间 | ~2s | ~30s |
| 输出格式 | glb/obj | glb/obj/fbx |

### 两阶段架构

```
Stage A: 几何生成
  单视图/多视图 → 稀疏3D → 稠密3D → 网格提取
  VRAM: ~8GB (geometry only)

Stage B: 纹理生成
  几何 + 输入图片 → UV 展开 + 纹理投射 + PBR 材质
  VRAM: ~16GB (with texture)
```

## 6GB VRAM 适配策略

### 实测数据 (RTX 3060 Laptop 6GB, 64GB RAM)

| 指标 | 值 |
|------|-----|
| 模型加载 | ~25-42s (因共享内存 swap 波动) |
| VRAM after load | 6.86 GB (超出 6GB, 溢出到共享内存) |
| Diffusion 速度 | 67-287s/step (严重受热降频影响) |
| VAE decode | 2-6s/chunk (430 chunks for 128³) |
| 5-step 总时间 | ~36 min (扩散18min + 解码17min + 后处理) |
| 25-step 预估 | ~2.5-3 hours |
| 输出质量 | 57K verts, 115K faces, watertight |

### 实际采用方案: 分段加载 (Latent-then-Decode)
1. DiT pipeline 生成 latents (GPU, fp16, VRAM溢出→慢)
2. Pipeline VAE 不使用，单独加载 VAE 解码
3. latents2mesh 逐块提取 (num_chunks=5000)
4. 后处理: FloaterRemover + DegenerateFaceRemover

### 性能瓶颈
- **VRAM 溢出是主要瓶颈**: DiT 3B + VAE 328M + conditioner 304M ≈ 7.4GB fp16, 超出 6GB 1.4GB
- **热降频严重**: RTX 3060 Laptop 持续高负载下 GPU 核心频率降低, 从67s/step恶化到287s/step
- **无加速优化**: FlashVDM decoder 不可用 (需要额外模型)

### 改进方向
- 研究 int8 量化降低 VRAM (理论可达 3.7GB)
- 探索 Hunyuan3D-2.1 mini 版本 (更小模型)
- 外部散热方案缓解热降频

## WinPortable 整合包

### 已知整合包

1. **混元3D 2.1 + ComfyUI 便携版** (B站)
   - 包含: ComfyUI + 模型 + 环境 + 工作流
   - 大小: ~30GB (含所有模型)
   
2. **一键启动整合包** (GitHub: aidayang/Hunyuan3D-2.1-windows-OneClick)
   - 免安装，直接运行
   - 较小的下载大小

### 注意事项

- 安装路径不能有空格或中文
- 需要更新 NVIDIA 驱动到最新版
- 内存建议 ≥20GB (我们有 64GB，充足)
- 部分整合包基于 ComfyUI 工作流，非独立 CLI

## CLI 集成计划

WinPortable 下载完成后，需要：

1. **探查目录结构**: 了解模型文件位置、Python 环境、入口脚本
2. **提取推理核心**: 从 ComfyUI 工作流中提取核心推理代码
3. **编写 CLI wrapper**: 创建 `hunyuan-to-3d.py`，类似 `image-to-3d.py`
4. **6GB 适配**: 配置 fp16 + CPU offload
5. **管线集成**: 在 `pipeline.py` 中添加 `--engine hunyuan` 参数

### 目标 CLI 接口

```bash
python scripts/hunyuan-to-3d.py photo.jpg \
    --mode geometry-only \
    --resolution 512 \
    --fp16 \
    --cpu-offload
```

## 对比总结

| 场景 | 推荐引擎 |
|------|---------|
| 快速预览 | TripoSR |
| 简单形状打印 | TripoSR + Mesh Repair |
| 高精度几何 | Hunyuan3D-2.1 (geometry only) |
| 全彩纹理 | Hunyuan3D-2.1 (full, CPU offload) |
| 批量处理 | TripoSR (速度快) |
| 多视图重建 | Hunyuan3D-2.1 |
