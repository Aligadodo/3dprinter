"""node_types.py - Node type registry for the workflow system.

Each node type defines typed input/output ports and configurable parameters.
Ports carry file paths between workflow nodes (not binary data).
"""

import web.schemas as schemas


class PortSpec:
    def __init__(self, name: str, type_: str, required: bool = True, label: str = "", label_zh: str = ""):
        self.name = name
        self.type = type_
        self.required = required
        self.label = label or name
        self.label_zh = label_zh or name

    def to_dict(self) -> dict:
        return {"name": self.name, "type": self.type, "required": self.required,
                "label": self.label, "label_zh": self.label_zh}


class NodeType:
    def __init__(self, id_: str, label: str, category: str,
                 inputs: list[PortSpec] = None, outputs: list[PortSpec] = None,
                 params: dict = None, color: str = "#444", gpu: bool = False,
                 inline: bool = False, label_zh: str = ""):
        self.id = id_
        self.label = label
        self.label_zh = label_zh
        self.category = category
        self.inputs = inputs or []
        self.outputs = outputs or []
        self.params = params or {}
        self.color = color
        self.inline = inline
        self.gpu = gpu

    def to_dict(self) -> dict:
        params_out = {}
        for key, spec in self.params.items():
            meta = PARAM_META.get(f"{self.id}:{key}") or PARAM_META.get(key, {})
            entry = dict(spec) if isinstance(spec, dict) else {"default": spec, "type": "string"}
            entry["label"] = meta.get("label", key)
            entry["label_zh"] = meta.get("label_zh", key)
            entry["desc"] = meta.get("desc", "")
            entry["desc_zh"] = meta.get("desc_zh", "")
            params_out[key] = entry
        d = {
            "id": self.id,
            "label": self.label,
            "category": self.category,
            "inputs": [p.to_dict() for p in self.inputs],
            "outputs": [p.to_dict() for p in self.outputs],
            "params": params_out,
            "color": self.color,
        }
        if self.label_zh:
            d["label_zh"] = self.label_zh
        return d


# ---------------------------------------------------------------------------
# Node type definitions
# ---------------------------------------------------------------------------

NODE_TYPES: dict[str, NodeType] = {}

def _register(nt: NodeType):
    NODE_TYPES[nt.id] = nt


_register(NodeType(
    "text_to_image",
    label="Text → Image",
    category="generate",
    inputs=[
        PortSpec("prompt", "string", required=True),
    ],
    outputs=[
        PortSpec("image", "image", required=True),
    ],
    params={
        "provider": {"type": "choice", "default": "volcengine", "choices": ["volcengine", "zhipu", "openai", "stability"]},
        "size": {"type": "choice", "default": "1024x1024", "choices": ["1024x1024", "2048x2048", "4096x4096", "1792x1024", "1024x1792", "768x1344", "1152x864"]},
    },
    color="#e67e22",
))

_register(NodeType(
    "relief",
    label="浮雕 Relief",
    category="process",
    inputs=[
        PortSpec("image", "image", required=True),
    ],
    outputs=[
        PortSpec("stl", "stl", required=True),
        PortSpec("color_preview", "image", required=False),
    ],
    params={
        "width": {"type": "float", "default": 160.0, "min": 20, "max": 500},
        "height": {"type": "float", "default": 120.0, "min": 20, "max": 500},
        "max_depth": {"type": "float", "default": 3.0, "min": 0.5, "max": 10.0},
        "base_thickness": {"type": "float", "default": 0.5, "min": 0.2, "max": 5.0},
        "detail": {"type": "float", "default": 0.25, "min": 0.0, "max": 1.0},
        "colors": {"type": "int", "default": 0, "min": 0, "max": 4},
        "pixel_spacing": {"type": "float", "default": 0.08, "min": 0.05, "max": 0.5},
    },
    color="#3498db",
))

_register(NodeType(
    "lithophane",
    label="夜灯 Lithophane",
    category="process",
    inputs=[
        PortSpec("image", "image", required=True),
    ],
    outputs=[
        PortSpec("stl", "stl", required=True),
        PortSpec("color_preview", "image", required=False),
    ],
    params={
        "width": {"type": "float", "default": 160.0, "min": 20, "max": 500},
        "height": {"type": "float", "default": 120.0, "min": 20, "max": 500},
        "max_depth": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0},
        "base_thickness": {"type": "float", "default": 0.6, "min": 0.3, "max": 3.0},
        "detail": {"type": "float", "default": 0.15, "min": 0.0, "max": 1.0},
        "colors": {"type": "int", "default": 0, "min": 0, "max": 4},
    },
    color="#2ecc71",
))

_register(NodeType(
    "layered_relief",
    label="套色浮雕 Layered",
    category="process",
    inputs=[
        PortSpec("image", "image", required=True),
    ],
    outputs=[
        PortSpec("stl", "stl", required=True),
        PortSpec("3mf", "file", required=False),
        PortSpec("color_map", "json", required=True),
        PortSpec("color_preview", "image", required=False),
    ],
    params={
        "width": {"type": "float", "default": 160.0, "min": 20, "max": 500},
        "height": {"type": "float", "default": 120.0, "min": 20, "max": 500},
        "colors": {"type": "int", "default": 4, "min": 2, "max": 16},
        "layer_height": {"type": "float", "default": 0.4, "min": 0.2, "max": 1.0},
        "base_thickness": {"type": "float", "default": 0.3, "min": 0.2, "max": 1.0},
        "edge_smooth": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0},
        "pixel_spacing": {"type": "float", "default": 0.08, "min": 0.05, "max": 0.5},
        "format": {"type": "choice", "default": "stl", "choices": ["stl", "3mf"]},
        "printer": {"type": "choice", "default": "P1S", "choices": ["P1S", "A1"]},
        "multi_color_mode": {"type": "choice", "default": "both", "choices": ["auto", "manual", "both"]},
    },
    color="#9b59b6",
))

_register(NodeType(
    "triposr",
    label="TripoSR 快速3D",
    category="process",
    inputs=[
        PortSpec("image", "image", required=True),
    ],
    outputs=[
        PortSpec("mesh", "stl", required=True),
        PortSpec("preview", "image", required=False),
    ],
    params={
        "format": {"type": "choice", "default": "glb", "choices": ["glb", "obj"]},
        "resolution": {"type": "int", "default": 256, "min": 64, "max": 384},
        "foreground_ratio": {"type": "float", "default": 0.85, "min": 0.7, "max": 0.95},
        "no_bg_remove": {"type": "bool", "default": False},
        "auto_prep": {"type": "bool", "default": True},
    },
    color="#e74c3c",
    gpu=True,
))

_register(NodeType(
    "hunyuan",
    label="Hunyuan3D 高质量",
    category="process",
    inputs=[
        PortSpec("image", "image", required=True),
    ],
    outputs=[
        PortSpec("mesh", "stl", required=True),
        PortSpec("preview", "image", required=False),
    ],
    params={
        "mode": {"type": "choice", "default": "geometry", "choices": ["geometry", "full"]},
        "steps": {"type": "int", "default": 15, "min": 5, "max": 50},
        "resolution": {"type": "int", "default": 256, "min": 128, "max": 384},
        "seed": {"type": "int", "default": 42, "min": 0, "max": 2147483647},
        "format": {"type": "choice", "default": "glb", "choices": ["glb", "obj", "stl"]},
        "skip_bg_remove": {"type": "bool", "default": False},
        "auto_prep": {"type": "bool", "default": True},
    },
    color="#c0392b",
    gpu=True,
))

_register(NodeType(
    "views",
    label="六视图 Views",
    category="process",
    inputs=[
        PortSpec("mesh", "stl", required=True),
    ],
    outputs=[
        PortSpec("grid", "image", required=True),
        PortSpec("views_dir", "dir", required=False),
    ],
    params={
        "resolution": {"type": "int", "default": 1024, "min": 256, "max": 4096},
        "no_grid": {"type": "bool", "default": False},
    },
    color="#1abc9c",
))

_register(NodeType(
    "repair",
    label="网格修复 Repair",
    category="process",
    inputs=[
        PortSpec("mesh", "stl", required=True),
    ],
    outputs=[
        PortSpec("repaired_mesh", "stl", required=True),
    ],
    params={
        "output_format": {"type": "choice", "default": "stl", "choices": ["stl", "obj", "3mf"]},
        "scale": {"type": "float", "default": 1.0, "min": 0.1, "max": 10.0},
    },
    color="#f39c12",
))

_register(NodeType(
    "model_prep",
    label="打印准备 Model Prep",
    category="process",
    inputs=[
        PortSpec("mesh", "stl", required=True),
    ],
    outputs=[
        PortSpec("mesh", "stl", required=True),
        PortSpec("preview", "image", required=False),
    ],
    params={
        "output_format": {"type": "choice", "default": "stl", "choices": ["stl", "3mf", "obj"]},
        "simplify": {"type": "int", "default": 50000, "min": 0, "max": 1000000},
        "repair": {"type": "bool", "default": True},
        "fill_holes": {"type": "bool", "default": True},
        "target_size_mm": {"type": "float", "default": 100.0, "min": 0.0, "max": 500.0},
        "ground": {"type": "bool", "default": True},
    },
    color="#e67e22",
))

_register(NodeType(
    "mesh_simplify",
    label="网格简化 Simplify",
    category="process",
    inputs=[
        PortSpec("mesh", "stl", required=True),
    ],
    outputs=[
        PortSpec("mesh", "stl", required=True),
    ],
    params={
        "target_faces": {"type": "int", "default": 50000, "min": 1000, "max": 1000000},
        "method": {"type": "choice", "default": "quadric", "choices": ["quadric", "cluster"]},
    },
    color="#1abc9c",
))

_register(NodeType(
    "mesh_smooth",
    label="网格平滑 Smooth",
    category="process",
    inputs=[
        PortSpec("mesh", "stl", required=True),
    ],
    outputs=[
        PortSpec("mesh", "stl", required=True),
    ],
    params={
        "iterations": {"type": "int", "default": 3, "min": 1, "max": 20},
        "lambda": {"type": "float", "default": 0.5, "min": 0.0, "max": 1.0},
        "mu": {"type": "float", "default": -0.53, "min": -1.0, "max": 0.0},
    },
    color="#1abc9c",
))

_register(NodeType(
    "mesh_scale",
    label="网格缩放 Scale",
    category="process",
    inputs=[
        PortSpec("mesh", "stl", required=True),
    ],
    outputs=[
        PortSpec("mesh", "stl", required=True),
    ],
    params={
        "scale": {"type": "float", "default": 1.0, "min": 0.01, "max": 100.0},
        "target_width": {"type": "float", "default": 0.0, "min": 0.0, "max": 1000.0},
        "uniform": {"type": "bool", "default": True},
    },
    color="#1abc9c",
))

_register(NodeType(
    "output_file",
    label="📁 Output",
    category="output",
    inputs=[
        PortSpec("file", "any", required=True),
    ],
    outputs=[],
    color="#95a5a6",
))

# ═══════════════════════════════════════════
#  Image Processing Nodes (inline, PIL-based)
# ═══════════════════════════════════════════

_register(NodeType(
    "image_resize",
    label="图像缩放 Resize",
    category="process",
    inputs=[PortSpec("image", "image", required=True)],
    outputs=[PortSpec("image", "image", required=True)],
    params={
        "width": {"type": "int", "default": 512, "min": 64, "max": 4096},
        "height": {"type": "int", "default": 512, "min": 64, "max": 4096},
        "fit": {"type": "choice", "default": "cover", "choices": ["cover", "contain", "stretch", "scale_width", "scale_height"]},
        "filter": {"type": "choice", "default": "lanczos", "choices": ["lanczos", "bilinear", "bicubic", "nearest"]},
    },
    color="#3498db",
    inline=True,
))

_register(NodeType(
    "image_grayscale",
    label="灰度转换 Grayscale",
    category="process",
    inputs=[PortSpec("image", "image", required=True)],
    outputs=[PortSpec("image", "image", required=True)],
    params={
        "method": {"type": "choice", "default": "luminosity", "choices": ["luminosity", "average", "lightness", "red_channel", "green_channel", "blue_channel"]},
    },
    color="#3498db",
    inline=True,
))

_register(NodeType(
    "image_crop",
    label="图像裁切 Crop",
    category="process",
    inputs=[PortSpec("image", "image", required=True)],
    outputs=[PortSpec("image", "image", required=True)],
    params={
        "x": {"type": "int", "default": 0, "min": 0},
        "y": {"type": "int", "default": 0, "min": 0},
        "width": {"type": "int", "default": 512, "min": 1},
        "height": {"type": "int", "default": 512, "min": 1},
        "aspect_ratio": {"type": "choice", "default": "free", "choices": ["free", "1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"]},
    },
    color="#3498db",
    inline=True,
))

_register(NodeType(
    "image_adjust",
    label="图像调节 Adjust",
    category="process",
    inputs=[PortSpec("image", "image", required=True)],
    outputs=[PortSpec("image", "image", required=True)],
    params={
        "brightness": {"type": "float", "default": 0.0, "min": -1.0, "max": 1.0},
        "contrast": {"type": "float", "default": 1.0, "min": 0.0, "max": 3.0},
        "saturation": {"type": "float", "default": 1.0, "min": 0.0, "max": 3.0},
        "sharpness": {"type": "float", "default": 0.0, "min": 0.0, "max": 2.0},
    },
    color="#3498db",
    inline=True,
))

_register(NodeType(
    "image_convert",
    label="格式转换 Convert",
    category="process",
    inputs=[PortSpec("image", "image", required=True)],
    outputs=[PortSpec("image", "image", required=True)],
    params={
        "format": {"type": "choice", "default": "png", "choices": ["png", "jpeg", "webp", "bmp", "tiff"]},
        "quality": {"type": "int", "default": 95, "min": 1, "max": 100},
        "optimize": {"type": "bool", "default": True},
    },
    color="#3498db",
    inline=True,
))

_register(NodeType(
    "remove_background",
    label="AI 去背景 Remove BG",
    category="process",
    inputs=[PortSpec("image", "image", required=True)],
    outputs=[PortSpec("image", "image", required=True), PortSpec("mask", "image", required=False)],
    params={
        "model": {"type": "choice", "default": "u2net", "choices": ["u2net", "u2netp", "u2net_human_seg", "isnet-general-use"]},
        "alpha_matting": {"type": "bool", "default": False},
        "bg_color": {"type": "string", "default": ""},
    },
    color="#e67e22",
    inline=True,
))

_register(NodeType(
    "image_effect",
    label="图片特效 Effect",
    category="process",
    inputs=[PortSpec("image", "image", required=True)],
    outputs=[PortSpec("image", "image", required=True)],
    params={
        "style": {"type": "choice", "default": "pixelate", "choices": [
            "pixelate", "posterize", "oil_paint", "watercolor", "pencil_sketch",
            "cartoon", "ink_wash", "impressionist", "macaron", "sepia",
            "halftone", "emboss", "neon", "duotone", "charcoal",
            "vintage_film", "kaleidoscope",
        ], "choices_zh": [
            "像素风", "海报化", "油画", "水彩", "铅笔素描",
            "卡通", "水墨画", "印象派", "马卡龙", "怀旧棕褐",
            "网目印刷", "浮雕", "霓虹", "双色调", "炭笔画",
            "胶片质感", "万花筒",
        ]},
        "strength": {"type": "float", "default": 0.8, "min": 0.0, "max": 1.0},
        "detail": {"type": "int", "default": 5, "min": 1, "max": 10},
        "color_scheme": {"type": "choice", "default": "warm", "choices": ["warm", "cool", "vivid", "muted"], "choices_zh": ["暖色调", "冷色调", "鲜艳", "柔和"]},
    },
    color="#e91e63",
    inline=True,
))


# ---------------------------------------------------------------------------
# Bilingual param labels and descriptions
# Keys match param names across all node types. Shared params (e.g. "width")
# use the most common meaning; node-specific overrides can be added as needed.
# ---------------------------------------------------------------------------

PARAM_META: dict[str, dict] = {
    # ── text_to_image ──
    "provider": {
        "label": "Provider", "label_zh": "服务商",
        "desc": "AI image generation service to use",
        "desc_zh": "选择AI生图服务商，需提前配置API密钥(config/providers.yaml)",
    },
    "size": {
        "label": "Size", "label_zh": "尺寸",
        "desc": "Output image resolution (width×height)",
        "desc_zh": "输出图片分辨率",
    },

    # ── Relief / Lithophane / Layered ──
    "width": {
        "label": "Width", "label_zh": "宽度",
        "desc": "Target width in millimeters",
        "desc_zh": "目标宽度(毫米)",
    },
    "height": {
        "label": "Height", "label_zh": "高度",
        "desc": "Target height in millimeters",
        "desc_zh": "目标高度(毫米)",
    },
    "max_depth": {
        "label": "Max Depth", "label_zh": "最大深度",
        "desc": "Maximum relief depth in mm. Larger = more 3D contrast",
        "desc_zh": "浮雕最大深度(毫米)，越大立体感越强",
    },
    "base_thickness": {
        "label": "Base Thickness", "label_zh": "底厚",
        "desc": "Bottom base thickness in mm. Keeps the print structurally sound",
        "desc_zh": "底部基座厚度(毫米)，保证结构强度",
    },
    "detail": {
        "label": "Detail", "label_zh": "细节度",
        "desc": "Detail sampling step in mm. Smaller = finer detail but slower",
        "desc_zh": "细节采样步长(毫米)，越小越精细但越慢",
    },
    "colors": {
        "label": "Colors", "label_zh": "颜色数",
        "desc": "Number of color layers (0 = grayscale / no color)",
        "desc_zh": "颜色层数(0=灰度/无颜色)",
    },
    "pixel_spacing": {
        "label": "Pixel Spacing", "label_zh": "像素间距",
        "desc": "Pixel spacing in mm for the generated mesh",
        "desc_zh": "生成网格的像素间距(毫米)",
    },
    "layer_height": {
        "label": "Layer Height", "label_zh": "层高",
        "desc": "Height of each color layer in mm",
        "desc_zh": "每层颜色层的高度(毫米)",
    },
    "edge_smooth": {
        "label": "Edge Smooth", "label_zh": "边缘平滑",
        "desc": "Edge smoothing amount. Higher = softer edges between layers",
        "desc_zh": "边缘平滑强度，越大层间过渡越柔和",
    },
    "format": {
        "label": "Format", "label_zh": "输出格式",
        "desc": "Output file format",
        "desc_zh": "输出文件格式。STL通用性强；3MF支持颜色信息",
    },

    # ── TripoSR ──
    "resolution": {
        "label": "Resolution", "label_zh": "分辨率",
        "desc": "Output mesh resolution. Higher = more detail but more VRAM",
        "desc_zh": "输出网格分辨率，越高细节越多但显存消耗越大",
    },
    "foreground_ratio": {
        "label": "Foreground Ratio", "label_zh": "前景比例",
        "desc": "Expected ratio of foreground object in input image (0-1)",
        "desc_zh": "输入图片中前景物体占比(0-1)，用于裁剪优化",
    },
    "auto_prep": {
        "label": "Auto Prep", "label_zh": "自动打印准备",
        "desc": "Automatically repair, simplify, and convert to STL after generation",
        "desc_zh": "生成后自动进行水密修复、减面和格式转换",
    },

    # ── Hunyuan3D ──
    "mode": {
        "label": "Mode", "label_zh": "模式",
        "desc": "Generation mode: geometry = mesh only, full = mesh + texture",
        "desc_zh": "生成模式：geometry=仅几何体，full=几何体+纹理",
    },
    "steps": {
        "label": "Steps", "label_zh": "推理步数",
        "desc": "Number of diffusion inference steps. More = better quality but slower",
        "desc_zh": "扩散推理步数，越多质量越好但越慢",
    },
    "seed": {
        "label": "Seed", "label_zh": "随机种子",
        "desc": "Random seed for reproducible results. Same seed + same input = same output",
        "desc_zh": "随机种子，相同种子+相同输入=相同输出",
    },

    # ── Views ──
    "no_grid": {
        "label": "No Grid", "label_zh": "禁用网格",
        "desc": "Output individual views instead of a combined grid image",
        "desc_zh": "输出单独的六视图文件而非拼接网格图",
    },

    # ── Repair ──
    "output_format": {
        "label": "Output Format", "label_zh": "输出格式",
        "desc": "File format for the repaired mesh",
        "desc_zh": "修复后网格的文件格式",
    },
    "scale": {
        "label": "Scale", "label_zh": "缩放",
        "desc": "Uniform scale factor applied to the mesh",
        "desc_zh": "模型等比缩放倍数。1.0=原始大小，2.0=放大一倍",
    },

    # ── mesh_simplify ──
    "target_faces": {
        "label": "Target Faces", "label_zh": "目标面数",
        "desc": "Desired number of triangular faces after simplification. Lower = smaller file",
        "desc_zh": "简化后期望的三角面数量，越低文件越小",
    },
    "mesh_simplify:method": {
        "label": "Method", "label_zh": "算法",
        "desc": "Simplification algorithm: quadric = best quality, cluster = faster",
        "desc_zh": "简化算法：quadric=二次误差(质量好)，cluster=聚类(速度快)",
    },
    "image_grayscale:method": {
        "label": "Method", "label_zh": "算法",
        "desc": "Grayscale conversion method: luminosity, average, lightness, or single channel",
        "desc_zh": "灰度转换算法：luminosity(亮度加权)、average(平均)、lightness(明度)、单通道",
    },

    # ── mesh_smooth ──
    "iterations": {
        "label": "Iterations", "label_zh": "迭代次数",
        "desc": "Number of smoothing passes. Higher = smoother but more shrinkage",
        "desc_zh": "平滑迭代次数，越多越平滑但可能收缩",
    },
    "lambda": {
        "label": "Lambda", "label_zh": "收缩系数 λ",
        "desc": "Taubin smooth scaling factor. Positive value controls smoothing amount",
        "desc_zh": "Taubin平滑缩放系数，正值控制平滑强度",
    },
    "mu": {
        "label": "Mu", "label_zh": "膨胀系数 μ",
        "desc": "Taubin expansion factor. Negative value counteracts volume shrinkage",
        "desc_zh": "Taubin膨胀系数，负值抵消体积收缩",
    },

    # ── mesh_scale ──
    "target_width": {
        "label": "Target Width", "label_zh": "目标宽度",
        "desc": "Target physical width in mm. 0 = disabled (use scale factor instead)",
        "desc_zh": "目标物理宽度(毫米)，0=禁用(使用缩放倍数)",
    },
    "uniform": {
        "label": "Uniform", "label_zh": "等比缩放",
        "desc": "Scale all axes uniformly (keep proportions)",
        "desc_zh": "三轴等比缩放(保持比例)",
    },

    # ── model_prep ──
    "output_format": {
        "label": "Output Format", "label_zh": "输出格式",
        "desc": "Output file format for the prepared mesh",
        "desc_zh": "导出文件的格式。STL=通用打印格式，3MF=现代格式(含元数据)",
    },
    "simplify": {
        "label": "Target Faces", "label_zh": "目标面数",
        "desc": "Target face count after decimation. 0=skip. 50000 is good for printing",
        "desc_zh": "简化后的目标面数。0=跳过。打印建议 50000",
    },
    "repair": {
        "label": "Repair", "label_zh": "水密修复",
        "desc": "Make mesh watertight via PyMeshFix (recommended for printing)",
        "desc_zh": "使用 PyMeshFix 进行水密修复，推荐用于打印",
    },
    "fill_holes": {
        "label": "Fill Holes", "label_zh": "填充孔洞",
        "desc": "Fill small holes in the mesh surface",
        "desc_zh": "填充网格表面的小孔洞",
    },
    "target_size_mm": {
        "label": "Target Size (mm)", "label_zh": "目标尺寸 (mm)",
        "desc": "Scale mesh to this maximum dimension in mm. 0=keep original size",
        "desc_zh": "将模型缩放至该最大尺寸(毫米)。0=保持原始大小",
    },
    "ground": {
        "label": "Ground to Base", "label_zh": "落地",
        "desc": "Center and set z-min to 0 so the model sits flat on the print bed",
        "desc_zh": "居中并将模型底部放置在打印平台上(z=0)",
    },

    # ── image_resize ──
    "fit": {
        "label": "Fit Mode", "label_zh": "适配模式",
        "desc": "cover=crop to fill, contain=letterbox, stretch=deform, scale_width/scale_height=by one axis",
        "desc_zh": "cover=裁切填充, contain=留白, stretch=拉伸变形, scale_width/scale_height=按单轴缩放",
    },
    "filter": {
        "label": "Filter", "label_zh": "采样算法",
        "desc": "Resampling filter: lanczos=sharpest, bilinear=smooth, bicubic=balanced, nearest=pixelated",
        "desc_zh": "重采样算法：lanczos=最锐利, bilinear=平滑, bicubic=均衡, nearest=像素风",
    },

    # ── image_grayscale ──
    # (method already defined above)

    # ── image_crop ──
    "x": {
        "label": "X", "label_zh": "起点X",
        "desc": "Crop start X coordinate (pixels from left)",
        "desc_zh": "裁切起点X坐标(从左边缘算起的像素数)",
    },
    "y": {
        "label": "Y", "label_zh": "起点Y",
        "desc": "Crop start Y coordinate (pixels from top)",
        "desc_zh": "裁切起点Y坐标(从上边缘算起的像素数)",
    },
    "aspect_ratio": {
        "label": "Aspect Ratio", "label_zh": "宽高比",
        "desc": "Constrain crop to a preset aspect ratio. 'free' = no constraint",
        "desc_zh": "裁切宽高比预设，free=不限制",
    },

    # ── image_adjust ──
    "brightness": {
        "label": "Brightness", "label_zh": "亮度",
        "desc": "Brightness adjustment. -1=black, 0=unchanged, 1=white",
        "desc_zh": "亮度调整。-1=全黑, 0=不变, 1=全白",
    },
    "contrast": {
        "label": "Contrast", "label_zh": "对比度",
        "desc": "Contrast adjustment. 0=flat gray, 1=unchanged, 3=high contrast",
        "desc_zh": "对比度调整。0=全灰, 1=不变, 3=高对比",
    },
    "saturation": {
        "label": "Saturation", "label_zh": "饱和度",
        "desc": "Color saturation. 0=grayscale, 1=unchanged, 3=oversaturated",
        "desc_zh": "色彩饱和度。0=灰度, 1=不变, 3=过饱和",
    },
    "sharpness": {
        "label": "Sharpness", "label_zh": "锐度",
        "desc": "Image sharpness. 0=unchanged, 2=very sharp",
        "desc_zh": "图像锐度。0=不变, 2=非常锐利",
    },

    # ── image_convert ──
    "quality": {
        "label": "Quality", "label_zh": "质量",
        "desc": "Output quality (1-100). Only applies to JPEG/WebP. Higher = larger file",
        "desc_zh": "输出质量(1-100)，仅对JPEG/WebP生效，越高文件越大",
    },
    "optimize": {
        "label": "Optimize", "label_zh": "优化压缩",
        "desc": "Apply extra compression optimization (smaller file, slightly slower)",
        "desc_zh": "启用额外压缩优化(文件更小，稍慢)",
    },

    # ── remove_background ──
    "model": {
        "label": "Model", "label_zh": "AI模型",
        "desc": "Background removal model: u2net=general, u2netp=lightweight, u2net_human_seg=portrait, isnet=high-precision",
        "desc_zh": "去背景AI模型：u2net=通用, u2netp=轻量, u2net_human_seg=人像, isnet=高精度",
    },
    "alpha_matting": {
        "label": "Alpha Matting", "label_zh": "Alpha抠图",
        "desc": "Enable alpha matting for finer edge detail (slower but higher quality)",
        "desc_zh": "启用Alpha抠图获取更精细边缘(更慢但质量更高)",
    },
    "bg_color": {
        "label": "BG Color", "label_zh": "替换背景色",
        "desc": "Replace transparent background with a color. Empty = keep transparency. e.g. 'white', '#ffffff', '255,0,0'",
        "desc_zh": "替换透明背景为指定颜色。留空=保持透明。如 'white', '#ffffff', '255,0,0'",
    },
    # ── image_effect ──
    "style": {
        "label": "Style", "label_zh": "特效风格",
        "desc": "Select the image effect style to apply. 16 styles across 4 categories (Artistic, Retro, Color, Distortion)",
        "desc_zh": "选择要应用的图片特效风格，共16种，涵盖艺术模拟、复古故障、色彩处理、变形抽象4大类",
    },
    "strength": {
        "label": "Strength", "label_zh": "混合强度",
        "desc": "Effect blend strength: 0.0=original image, 1.0=full effect",
        "desc_zh": "效果混合强度：0.0=原始图片，1.0=完全效果",
    },
    "image_effect:detail": {
        "label": "Detail", "label_zh": "细节级别",
        "desc": "Effect detail/intensity level (1-10). Meaning varies by style: pixel size for pixelate, color levels for posterize, brush size for paint effects, etc.",
        "desc_zh": "效果细节/强度级别(1-10)。含义随风格变化：像素风=像素大小，海报化=色彩层数，油画=笔触粗细，网点=网点大小等",
    },
    "color_scheme": {
        "label": "Color Scheme", "label_zh": "配色方案",
        "desc": "Color palette preset. warm=warm tones, cool=cool tones, vivid=bright saturated, muted=soft subtle. Used by duotone, macaron, sepia, vintage_film, neon",
        "desc_zh": "配色预设：warm=暖色调，cool=冷色调，vivid=鲜艳明亮，muted=柔和淡雅。适用于双色调、马卡龙、怀旧棕褐、胶片质感、霓虹",
    },
    # ── multi_color_mode (layered_relief) ──
    "multi_color_mode": {
        "label": "Multi-Color Mode", "label_zh": "多色模式",
        "desc": "auto=full 3MF (Bambu auto-assigns filaments), manual=3MF+color_config.json, both=generate both",
        "desc_zh": "auto=完整3MF（拓竹自动配色），manual=3MF+color_config.json（人工配置），both=同时生成两种",
    },
    # ── no_bg_remove / skip_bg_remove ──
    "no_bg_remove": {
        "label": "Skip BG Remove", "label_zh": "跳过背景移除",
        "desc": "Skip background removal (use if input already has transparent background)",
        "desc_zh": "跳过背景移除（如果输入图片已去背景）",
    },
    "skip_bg_remove": {
        "label": "Skip BG Remove", "label_zh": "跳过背景移除",
        "desc": "Skip background removal (use if input already has transparent background)",
        "desc_zh": "跳过背景移除（如果输入图片已去背景）",
    },
    # ── mesh_align:method ──
    "mesh_align:method": {
        "label": "Method", "label_zh": "方法",
        "desc": "surface=local frame alignment, icp=iterative closest point",
        "desc_zh": "surface=局部坐标系对齐, icp=迭代最近点",
    },
# ── Mesh Boolean ───────────────────────────────────────────────────
    "bool_op": {
        "label": "Boolean Op", "label_zh": "布尔运算",
        "desc": "Boolean operation: union (merge), diff (subtract), intersect (overlap)",
        "desc_zh": "布尔运算: union(合并)/diff(减去)/intersect(交集)",
    },
    # ── Mesh Stitch ─────────────────────────────────────────────────
    "stitch_smooth": {
        "label": "Smooth Steps", "label_zh": "平滑次数",
        "desc": "Number of HC Laplacian smoothing iterations (default: 3)",
        "desc_zh": "HC 拉普拉斯平滑迭代次数",
    },
    "stitch_lambda": {
        "label": "Lambda", "label_zh": "Lambda",
        "desc": "Smoothing lambda value (default: 0.1)",
        "desc_zh": "平滑 lambda 值",
    },
    # ── Mesh Decorate ───────────────────────────────────────────────
    "deco_texture": {
        "label": "Texture Image", "label_zh": "纹理图像",
        "desc": "PNG image to project onto mesh surface via UV",
        "desc_zh": "PNG 图片，通过 UV 映射到 Mesh 表面",
    },
    "deco_displacement": {
        "label": "Displacement", "label_zh": "位移强度",
        "desc": "Max displacement in mesh units (default: 0.5)",
        "desc_zh": "最大位移量（Mesh 单位）",
    },
    # ── Mesh Transform ───────────────────────────────────────────────
    "tf_translate": {
        "label": "Translate", "label_zh": "平移",
        "desc": "Translate by dx,dy,dz (default: 0,0,0)",
        "desc_zh": "沿 X/Y/Z 轴平移量",
    },
    "tf_rotate": {
        "label": "Rotate", "label_zh": "旋转",
        "desc": "Rotate by angle (degrees) around axis (default: 0,0,1)",
        "desc_zh": "绕轴旋转角度（度）",
    },
    "tf_scale": {
        "label": "Scale", "label_zh": "缩放",
        "desc": "Uniform scale factor (default: 1.0)",
        "desc_zh": "等比例缩放系数",
    },
    # ── Mesh Select ──────────────────────────────────────────────────
    "sel_bbox": {
        "label": "Bounding Box", "label_zh": "包围盒",
        "desc": "Select vertices within bounding box: xmin,ymin,zmin,xmax,ymax,zmax (default: all)",
        "desc_zh": "在包围盒内的顶点: xmin,ymin,zmin,xmax,ymax,zmax",
    },
}
# ---------------------------------------------------------------------------

# ── Mesh Boolean Node ───────────────────────────────────────────────────────
_register(NodeType(
    "mesh_boolean",
    label="Mesh Boolean",
    label_zh="布尔运算",
    category="mesh_ops",
    inputs=[
        PortSpec("mesh_a", "mesh", required=True, label="Mesh A", label_zh="Mesh A"),
        PortSpec("mesh_b", "mesh", required=True, label="Mesh B", label_zh="Mesh B"),
    ],
    outputs=[PortSpec("mesh", "mesh", required=True)],
    params={
        "bool_op": {"type": "choice", "default": "union", "choices": ["union", "diff", "intersect"]},
    },
    color="#9370db",
))

# ── Mesh Stitch Node ─────────────────────────────────────────────────────────
_register(NodeType(
    "mesh_stitch",
    label="Mesh Stitch",
    label_zh="Mesh 缝合",
    category="mesh_ops",
    inputs=[PortSpec("mesh", "mesh", required=True)],
    outputs=[PortSpec("mesh", "mesh", required=True)],
    params={
        "stitch_smooth": {"type": "int", "default": 3, "min": 0, "max": 20},
        "stitch_lambda": {"type": "float", "default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01},
    },
    color="#9370db",
))

# ── Mesh Decorate Node ───────────────────────────────────────────────────────
_register(NodeType(
    "mesh_decorate",
    label="Mesh Decorate",
    label_zh="曲面装饰",
    category="mesh_ops",
    inputs=[
        PortSpec("mesh", "mesh", required=True),
        PortSpec("texture", "image", required=True),
    ],
    outputs=[PortSpec("mesh", "mesh", required=True)],
    params={
        "deco_displacement": {"type": "float", "default": 0.5, "min": 0.0, "max": 10.0, "step": 0.1},
    },
    color="#9370db",
))

# ── Mesh Transform Node ──────────────────────────────────────────────────────
_register(NodeType(
    "mesh_transform",
    label="Mesh Transform",
    label_zh="几何变换",
    category="mesh_ops",
    inputs=[PortSpec("mesh", "mesh", required=True)],
    outputs=[PortSpec("mesh", "mesh", required=True)],
    params={
        "tf_translate": {"type": "string", "default": "0,0,0"},
        "tf_rotate_angle": {"type": "float", "default": 0, "min": -360, "max": 360, "step": 1},
        "tf_rotate_axis": {"type": "string", "default": "0,0,1"},
        "tf_scale": {"type": "float", "default": 1.0, "min": 0.01, "max": 100, "step": 0.1},
    },
    color="#9370db",
    inline=True,
))

# ── Mesh Select Node ─────────────────────────────────────────────────────────
_register(NodeType(
    "mesh_select",
    label="Mesh Select",
    label_zh="Mesh 选择",
    category="mesh_ops",
    inputs=[PortSpec("mesh", "mesh", required=True)],
    outputs=[PortSpec("mesh", "mesh", required=True)],
    params={
        "sel_bbox": {"type": "string", "default": ""},
    },
    color="#9370db",
    inline=True,
))

# ── Mesh Cut Node ────────────────────────────────────────────────────────────
_register(NodeType(
    "mesh_cut",
    label="Mesh Cut",
    label_zh="Mesh 切割",
    category="mesh_ops",
    inputs=[PortSpec("mesh", "mesh", required=True)],
    outputs=[
        PortSpec("mesh_outer", "mesh", required=True, label="Outer", label_zh="外侧"),
        PortSpec("mesh_inner", "mesh", required=False, label="Inner", label_zh="内侧"),
    ],
    params={
        "cut_plane_co": {"type": "string", "default": "0,0,0"},
        "cut_plane_no": {"type": "string", "default": "0,0,1"},
        "cut_fill": {"type": "bool", "default": True},
    },
    color="#9370db",
))

# ── Mesh Align Node ───────────────────────────────────────────────────────────
_register(NodeType(
    "mesh_align",
    label="Mesh Align",
    label_zh="Mesh 对齐",
    category="mesh_ops",
    inputs=[
        PortSpec("mesh_a", "mesh", required=True, label="Target", label_zh="目标"),
        PortSpec("mesh_b", "mesh", required=True, label="Source", label_zh="源"),
    ],
    outputs=[PortSpec("mesh_aligned", "mesh", required=True)],
    params={
        "method": {"type": "choice", "default": "surface", "choices": ["surface", "icp"]},
    },
    color="#9370db",
))

CATEGORIES = {
    "input":     {"label": "Input",      "label_zh": "输入"},
    "generate":  {"label": "Generate",   "label_zh": "生成"},
    "process":   {"label": "Process",    "label_zh": "处理"},
    "output":    {"label": "Output",    "label_zh": "输出"},
    "mesh_ops":  {"label": "Mesh Ops",   "label_zh": "高级Mesh",  "collapsed": True},
    "other":     {"label": "Other",      "label_zh": "其他",      "collapsed": True},
}

_register(NodeType(
    "file_input",
    label="File Input",
    label_zh="文件输入",
    category="input",
    inputs=[],
    outputs=[PortSpec("file", "file", required=True)],
    params={"accept": ".png,.jpg,.jpeg,.stl,.3mf,.obj,.glb"},
    color="#4a9eff",
))

_register(NodeType(
    "text_input",
    label="Text Input",
    label_zh="文本输入",
    category="input",
    inputs=[],
    outputs=[PortSpec("text", "string", required=True)],
    params={"multiline": False, "placeholder": "Enter text prompt..."},
    color="#50c878",
))


def get_node_type(node_type_id: str) -> NodeType | None:
    clean_id = node_type_id.replace("wf_", "", 1) if node_type_id.startswith("wf_") else node_type_id
    return NODE_TYPES.get(clean_id)


def all_node_types() -> list[dict]:
    return [nt.to_dict() for nt in NODE_TYPES.values()]


def node_pipeline_map() -> dict[str, str]:
    """Map node type ID → pipeline_type for scheduler submission."""
    return {
        "relief": "relief",
        "lithophane": "lithophane",
        "layered_relief": "layered_relief",
        "triposr": "triposr",
        "hunyuan": "hunyuan",
        "views": "views",
        "repair": "repair",
        "model_prep": "model_prep",
        "mesh_simplify": "mesh_simplify",
        "mesh_smooth": "mesh_smooth",
        "mesh_scale": "mesh_scale",
        "mesh_boolean": "mesh_boolean",
        "mesh_stitch": "mesh_stitch",
        "mesh_cut": "mesh_cut",
        "mesh_align": "mesh_align",
        "mesh_decorate": "mesh_decorate",
    }


def node_input_port_map() -> dict[str, str]:
    """Map node type ID → name of the primary input port."""
    return {
        "text_to_image": "prompt",
        "relief": "image",
        "lithophane": "image",
        "layered_relief": "image",
        "triposr": "image",
        "hunyuan": "image",
        "views": "mesh",
        "repair": "mesh",
        "model_prep": "mesh",
        "mesh_simplify": "mesh",
        "mesh_smooth": "mesh",
        "mesh_scale": "mesh",
        "mesh_boolean": "mesh_a",
        "mesh_stitch": "mesh",
        "mesh_cut": "mesh",
        "mesh_align": "mesh_a",
        "mesh_decorate": "mesh",
        "mesh_transform": "mesh",
        "mesh_select": "mesh",
    }


def get_input_node_ids(graph: dict) -> list[str]:
    """Scan a workflow graph for nodes whose type is in the 'input' category."""
    input_ids = []
    title_to_type = {
        "file_input": "file_input", "File Input": "file_input", "File": "file_input",
        "text_input": "text_input", "Text Input": "text_input",
    }
    for n in graph.get("nodes", []):
        nt_def = get_node_type(n.get("type", ""))
        if nt_def and nt_def.category == "input":
            input_ids.append(str(n.get("id")))
        elif not nt_def and not n.get("type"):
            # Backward compat: try to infer type from title for corrupted workflows
            inferred = title_to_type.get(n.get("title", ""))
            if inferred:
                nt_def = get_node_type(inferred)
                if nt_def and nt_def.category == "input":
                    input_ids.append(str(n.get("id")))
    return input_ids
