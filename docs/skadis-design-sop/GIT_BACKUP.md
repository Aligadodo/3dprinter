# Git备份范围

本仓库备份SOP、参数、来源与网格索引、组件定位清单、验证记录及Python工具。床头夹具设计、渲染、核验、打包源码保存在原 `output/bedhead-clamp-concepts` 路径并单独纳入Git；普通生成输出仍忽略。

原收藏3MF、提取STL、缩略图、生成HTML和最终打印工程保留在本机E盘，不包含在本次代码提交中。`components/manifest.json`与`reference-index/catalog.json`用来定位和校验这些资产，并不代表仓库包含其二进制内容。

在新电脑恢复时：先恢复 `E:/3dprint/模型收藏合集/宜家洞洞板系列收藏`，再按reference-guide.md刷新索引和组件。依赖Python、numpy、trimesh、Pillow、markdown；建模另需manifold3d、shapely。绝对路径不同需先调整脚本路径。

完整床头工程重建还依赖 `output/skadis-corner-support/print-kit-v1` 中的种子3MF，以及 `revision-a` 中的原夹体／螺杆网格；请从E盘设计交付或原始收藏恢复。Git备份不能替代原始模型与打印工程的磁盘备份。验证JSON为既有运行证据，本次提交未重新打印或测试承重。
