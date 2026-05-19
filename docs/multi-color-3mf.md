# Bambu Studio 3MF 格式规范

## 概述

Bambu Studio 使用 OPC（Open Packaging Conventions）ZIP 格式存储 3MF 文件。内部采用 XML 格式的 mesh（`<mesh><vertices>/<triangles>`），而非二进制 STL。本文档记录从官方导出文件逆向工程得到的完整格式规范。

**关键发现（2026-05-19）**：Bambu Studio **不识别**二进制 STL 格式的 `object_N.model`。所有官方文件内部均使用 XML mesh 格式。这是之前所有 3MF 解析失败的 Root Cause。

---

## 文件结构

```
3MF.zip/
├── [Content_Types].xml              # OPC 内容类型注册
├── _rels/.rels                      # 根关系（指向 3dmodel.model）
├── 3D/
│   ├── 3dmodel.model               # 场景图 + 元数据 + build plate
│   ├── _rels/3dmodel.model.rels    # 模型→mesh 关系（指向 object_2.model）
│   └── Objects/
│       └── object_2.model           # XML mesh 数据（id=1 的 mesh object）
├── Metadata/
│   ├── project_settings.config     # 完整 slicer 配置（filament 颜色等）
│   ├── model_settings.config       # plate 布局 + filament 映射
│   ├── custom_gcode_per_layer.xml  # Z高度换丝事件（MultiAsSingle）
│   ├── slice_info.config            # slicer 版本头
│   ├── cut_information.xml          # 连接器切割信息
│   ├── filament_sequence.json       # AMS 槽位分配（MultiAsSingle 模式下通常为空）
│   ├── plate_1.png                  # 缩略图（必须存在）
│   ├── plate_no_light_1.png
│   ├── top_1.png
│   └── pick_1.png
└── Auxiliaries/                     # 官方缩略图文件夹（Bambu Studio 可正常打开的关键）
    ├── Model Pictures/
    │   └── {guid}.webp
    ├── Profile Pictures/
    │   └── {guid}.webp
    └── .thumbnails/
        ├── thumbnail_3mf.png
        ├── thumbnail_small.png
        └── thumbnail_middle.png
```

---

## 核心文件详解

### 1. `3D/3dmodel.model` — 场景图

顶级 `object id="2"` 包含 `<components>` 引用内部 mesh object。

```xml
<?xml version='1.0' encoding='UTF-8'?>
<model xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
       xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
       xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"
       unit="millimeter" xml:lang="en-US" requiredextensions="p">
  <metadata name="Application">BambuStudio-02.03.00.70</metadata>
  <metadata name="BambuStudio:3mfVersion">1</metadata>
  <metadata name="BambuStudio:CopyRight">[]</metadata>
  <metadata name="BambuStudio:Copyright">[]</metadata>
  <metadata name="BambuStudio:Designer">拾光漫行</metadata>
  <metadata name="BambuStudio:DesignerUserId">3799092001</metadata>
  <metadata name="BambuStudio:DesignModelId">CN968e8d2b8bb783</metadata>
  <metadata name="BambuStudio:DesignProfileId">92745964</metadata>
  <metadata name="BambuStudio:DesignRegion">CN</metadata>
  <!-- ... more metadata ... -->

  <resources>
    <object id="2" p:UUID="00000002-61cb-4c03-9d28-80fed5dfa1dc" type="model">
      <components>
        <!-- 注意: path 指向 object_2.model，但 objectid="1" -->
        <component p:path="/3D/Objects/object_2.model" objectid="1"
                   p:UUID="00020000-b206-40ff-9872-83e8017abed1"
                   transform="1 0 0 0 1 0 0 0 1 0 0 0" />
      </components>
    </object>
  </resources>

  <build p:UUID="2c7c17d8-22b5-4d84-8835-1976022ea369">
    <item objectid="2" p:UUID="00000002-b1ec-4553-aec9-835e5b724bb4"
          transform="1 0 0 0 1 0 0 0 1 128 128 1.16"
          printable="1" />
  </build>
</model>
```

**要点：**
- `object id="2"` 在 3dmodel.model 中引用 `objectid="1"` 的内部 object
- `p:path="/3D/Objects/object_2.model"` — 存档中的文件名
- `<item objectid="2">` 引用顶级 object，`transform` 最后三项是 X/Y/Z 位置偏移
- UUID 前缀规则：`00000002-`（scene graph object）、`00020000-`（inner mesh component）

### 2. `3D/Objects/object_2.model` — XML Mesh（关键！）

**Bambu Studio 使用 XML mesh 格式，不识别二进制 STL。**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
 xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
 xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"
 xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
 requiredextensions="p">
 <metadata name="BambuStudio:3mfVersion">1</metadata>
 <resources>
  <!-- 注意：inner mesh object id="1"，不是 "2" -->
  <object id="1" p:UUID="00020000-81cb-4c03-9d28-80fed5dfa1dc" type="model">
   <mesh>
    <vertices>
     <vertex x="-42.200001" y="-75" z="0.245068"/>
     <vertex x="-42" y="-74.800003" z="0.230552"/>
     <!-- ... more vertices ... -->
    </vertices>
    <triangles>
     <triangle v1="0" v2="1" v3="2"/>
     <triangle v1="1" v2="3" v3="2"/>
     <!-- ... more triangles ... -->
    </triangles>
   </mesh>
  </object>
 </resources>
 <build/>
</model>
```

**UUID 前缀：`00020000-`**，这是 inner mesh object 的固定前缀模式。

### 3. `Metadata/model_settings.config` — 最关键的文件

此文件决定 Bambu Studio 能否正确解析模型。多色识别依赖于 `filament_maps` 和 `filament_volume_maps` 字段。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="2">
    <metadata key="name" value="鬼灭_Front_84x150.stl"/>
    <metadata key="extruder" value="1"/>
    <metadata face_count="640032"/>           <!-- 必须与实际 mesh 面数一致 -->
    <part id="1" subtype="normal_part">
      <metadata key="name" value="鬼灭_Front_84x150.stl"/>
      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>  <!-- 4x4 单位矩阵 -->
      <metadata key="source_object_id" value="0"/>   <!-- 重要：官方用 "0"，不是 "1" -->
      <metadata key="source_volume_id" value="0"/>
      <metadata key="source_offset_x" value="0"/>
      <metadata key="source_offset_y" value="0"/>
      <metadata key="source_offset_z" value="1.16"/>   <!-- Z 偏移 = 模型高度 -->
      <mesh_stat face_count="640032"      <!-- 必须与 face_count 一致 -->
                 edges_fixed="0"
                 degenerate_facets="0"
                 facets_removed="0"
                 facets_reversed="0"
                 backwards_edges="0"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value=""/>
    <metadata key="locked" value="false"/>
    <metadata key="filament_map_mode" value="Auto For Flush"/>
    <metadata key="filament_maps" value="1 1 1 1"/>   <!-- 多色：必须存在此字段 -->
    <metadata key="filament_volume_maps" value="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"/>  <!-- 16 个槽位 -->
    <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>   <!-- 必须 -->
    <metadata key="thumbnail_no_light_file" value="Metadata/plate_no_light_1.png"/>
    <metadata key="top_file" value="Metadata/top_1.png"/>
    <metadata key="pick_file" value="Metadata/pick_1.png"/>
    <model_instance>
      <metadata key="object_id" value="2"/>
      <metadata key="instance_id" value="0"/>
      <metadata key="identify_id" value="4753"/>
    </model_instance>
  </plate>
  <assemble>
    <assemble_item object_id="2" instance_id="0"
     transform="1 0 0 0 1 0 0 0 1 101.28 0 2.32"
     offset="0 0 0" />
  </assemble>
</config>
```

**必填字段（缺失 = 解析失败）：**

| 路径 | 值 | 说明 |
|------|-----|------|
| `object/metadata[@face_count]` | int | 三角形数量，必须与 mesh 一致 |
| `part/metadata[@matrix]` | `1 0 0 0 1 0 0 0 1 0 0 0` | 4x4 单位矩阵 |
| `part/metadata[@source_object_id]` | `"0"` | 官方用 "0"，不要用 "1" |
| `part/mesh_stat[@face_count]` | int | 必须等于 object face_count |
| `plate/metadata[@filament_volume_maps]` | 16个空格分隔的0 | `"0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"` |

### 4. `Metadata/custom_gcode_per_layer.xml` — 换丝事件

MultiAsSingle 模式：单模型多色，在 Z 高度边界处触发换丝。

```xml
<?xml version="1.0" encoding="UTF-8"?>
<custom_gcodes_per_layer>
 <plate>
  <plate_info id="1"/>
  <!-- type="2" = 换丝事件；extruder 从 2 开始（1 是默认起始 extruder）-->
  <layer top_z="0.88" type="2" extruder="2" color="#FF0000" extra="" gcode="tool_change"/>
  <layer top_z="1.36" type="2" extruder="3" color="#F4EE2A" extra="" gcode="tool_change"/>
  <layer top_z="1.68" type="2" extruder="4" color="#FFFFFF" extra="" gcode="tool_change"/>
  <mode value="MultiAsSingle"/>
 </plate>
</custom_gcodes_per_layer>
```

- `type="2"` = 换丝事件类型
- `extruder` 值为 2-4，对应实际 extruder 索引
- 颜色为hex大写 RGB
- 最后一行（最高层）不需要换丝事件
- `extruder="2"` 表示切换到第二个 filament（第一个是 extruder 1，默认激活）

### 5. `Metadata/slice_info.config` — Slicer 版本

```xml
<?xml version="1.0" encoding="UTF-8"?>
<config>
  <header>
    <header_item key="X-BBL-Client-Type" value="slicer"/>
    <header_item key="X-BBL-Client-Version" value="02.03.00.70"/>
  </header>
</config>
```

版本号需与 `3D/3dmodel.model` 中 `Application` 字段匹配。

### 6. `3D/_rels/3dmodel.model.rels` — Mesh 关系

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/Objects/object_2.model"
                Id="rel-1"
                Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
```

**注意**：`Id="rel-1"` 使用带连字符的格式，不是 `rel1`。

### 7. `Metadata/filament_sequence.json` — AMS 槽位分配

MultiAsSingle 模式下通常为空：

```json
{"plate_1":{"nozzle_sequence":[],"optimal_assignment":[],"sequence":[]}}
```

官方文件通常**不包含此文件**（在 MultiAsSingle 模式下）。包含空对象占位符也不会出错。

---

## UUID 命名模式

经官方文件验证的模式：

| 角色 | UUID 格式 | 示例 |
|------|----------|------|
| Scene graph object (id=2) | `00000002-{12 hex}` | `00000002-61cb-4c03-9d28-80fed5dfa1dc` |
| Build item | `00000002-{12 hex}` | `00000002-b1ec-4553-aec9-835e5b724bb4` |
| Inner mesh component | `00020000-{12 hex}` | `00020000-b206-40ff-9872-83e8017abed1` |
| Inner mesh object (id=1) | `00020000-{12 hex}` | `00020000-81cb-4c03-9d28-80fed5dfa1dc` |

---

## 多色打印实现方案

### MultiAsSingle 模式

单模型多色，通过 Z 高度触发的 `tool_change` 事件切换丝材。

**工作流程：**
1. Extruder 1 在 Z=0 时默认激活
2. 每到一个颜色层的 Z 高度边界，触发 `tool_change` 切换到下一个 extruder
3. 最后（最高）颜色层之后不再需要事件

**对于 N 颜色，有 N-1 个换丝事件：**

```
Band 1 (Z: 0→0.4mm)  → extruder 1 [默认]
Band 2 (Z: 0.4→0.8mm) → @ Z=0.4 触发 tool_change → extruder 2
Band 3 (Z: 0.8→1.2mm) → @ Z=0.8 触发 tool_change → extruder 3
Band 4 (Z: 1.2→1.6mm) → @ Z=1.2 触发 tool_change → extruder 4
[最高层之后无需事件]
```

### Filament 颜色配置

在 `project_settings.config` 中通过 `filament_colour` 数组配置：

```json
"filament_colour": ["#3E3E80", "#BE3E80", "#3FBE80", "#BFBE80"]
```

---

## 生成策略（2026-05-19 最终方案）

### 核心思路

使用官方确认可打开的 3MF 文件（`test_minimal_swap.3mf`）作为 base，只替换必要部分：

```
官方 base.3mf (可正常打开)
  ├── 保留: Auxiliaries/ (缩略图文件夹，Bambu Studio 识别关键)
  ├── 保留: slice_info.config, cut_information.xml, _rels/.rels
  ├── 替换: 3D/Objects/object_2.model ← 我们的 XML mesh
  ├── 替换: Metadata/model_settings.config ← 更新 face_count
  └── 添加: Metadata/custom_gcode_per_layer.xml ← MultiAsSingle 换丝事件
           Metadata/project_settings.config ← filament 颜色配置
```

### `_get_base_3mf_path()` 函数

首次调用时从 `output/test_minimal_swap.3mf` 复制到 `scripts/templates/bambu/base.3mf`，后续稳定引用此文件。

```python
def _get_base_3mf_path():
    """Locate or copy the official Bambu Studio base 3MF for multi-color export."""
    tpl_dir = _resolve_template_dir()
    base_path = os.path.join(tpl_dir, "base.3mf")
    if not os.path.exists(base_path):
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "output", "test_minimal_swap.3mf")
        if os.path.exists(src):
            shutil.copy2(src, base_path)
    return base_path
```

### STL → XML Mesh 转换

```python
def _build_xml_mesh(verts, faces, obj_id=1, obj_uuid=None):
    """将顶点/面数组转换为 Bambu Studio XML mesh 格式。"""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<model unit="millimeter" xml:lang="en-US"',
        ' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"',
        ' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"',
        ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"',
        ' requiredextensions="p">',
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>',
        ' <resources>',
        f'  <object id="{obj_id}" p:UUID="{obj_uuid}" type="model">',
        '   <mesh>',
        '    <vertices>',
    ]
    for x, y, z in verts:
        lines.append(f'     <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>')
    lines.append('    </vertices>')
    lines.append('    <triangles>')
    for a, b, c in faces:
        lines.append(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>')
    lines.append('    </triangles>')
    lines.append('   </mesh>')
    lines.append('  </object>')
    lines.append(' </resources>')
    lines.append(' <build/>')
    lines.append('</model>')
    return '\n'.join(lines).encode('utf-8')
```

---

## 已知问题与修复记录

### Root Cause: 二进制 STL 格式不被识别（2026-05-19）

**问题**：Bambu Studio 打开 3MF 报"没有任何几何信息"。

**根因**：之前的实现将二进制 STL 写入 `object_N.model`。Bambu Studio 内部使用 XML mesh 格式，**完全不识别二进制 STL**。

**修复**：使用 trimesh 加载 STL，再用 `_build_xml_mesh()` 生成 XML 格式写入 `object_2.model`。

### model_settings.config 缺失关键字段

**问题**：缺少 `face_count`、`matrix`、`source_offset_*`、`mesh_stat` 等字段。

**修复**：从 trimesh 获取 face_count，全部按照官方格式生成各字段。特别注意 `source_object_id` 应设为 `"0"`（官方值）。

### Auxiliaries 文件夹缺失导致缩略图加载警告

**问题**：文件能打开但提示"包含自定义 Gcode 和打印预设"。

**根因**：缺少官方缩略图文件夹结构。

**修复**：使用官方 base.3mf 作为骨架，其包含完整的 Auxiliaries/ 结构。

### G-code 双转义

**问题**：`json.dumps` 在 `_resolve_template_json` 中双重转义 G-code 中的换行符。

**修复**：移除 `_escape_gcode()` 预处理函数，Raw G-code 直接传入，单次 `json.dumps` 处理所有转义。

### Compound-string 占位符未解析

**问题**：`"{{BED_SIZE_X}}x0"` 类字符串未被解析。

**修复**：精确匹配返回 Python 对象，包含占位符的字符串进行正则替换。

---

## CLI 使用方法

```bash
# 自动模式：生成完整 3MF（Bambu Studio 自动处理 filament 分配）
python scripts/image-to-layered-relief.py photo.jpg --colors 4 --format 3mf --printer P1S --multi-color-mode auto

# 手动模式：同时生成人类可读的 color_config.json
python scripts/image-to-layered-relief.py photo.jpg --colors 4 --format 3mf --printer P1S --multi-color-mode manual

# 双模式：同时生成两者
python scripts/image-to-layered-relief.py photo.jpg --colors 4 --format 3mf --printer P1S --multi-color-mode both

# A1 打印机 2 色
python scripts/image-to-layered-relief.py photo.jpg --colors 2 --format 3mf --printer A1
```

---

## 文件输出结构

```
layered_relief/
├── {name}_color_preview.png        # 量化颜色预览图
├── {name}_{N}color.stl             # 水密网格 STL
├── {name}_color_map.json           # Z高度→颜色带映射
├── {name}_color_config.json        # 人类可读的 filament 分配指南（manual 模式）
└── {name}_{N}color.3mf             # 完整 Bambu Studio 项目文件
```

---

## 版本历史

| 日期 | 变更 |
|------|------|
| 2026-05-19 | 发现 Root Cause：XML mesh 格式替代二进制 STL；采用官方 base.3mf 架构；source_object_id=0 |
| 2026-05-19 | 添加 `--multi-color-mode auto\|manual\|both`；添加中文颜色名称；修复多处字段问题 |
| 2026-05-15 | 修复 model_settings.config 缺失 face_count、matrix、source_offset、mesh_stat、filament_volume_maps |
| 2026-05-14 | 修复 custom_gcode_per_layer.xml 中 extruder 索引（band order +1，跳过最后 band） |
| 2026-05-13 | 修复 compound-string 占位符解析 |
| 2026-05-13 | 移除 `_escape_gcode()` 修复 G-code 双转义 |