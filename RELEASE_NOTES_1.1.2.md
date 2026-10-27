# VocalPitchLab 1.1.2

## 更新内容

- 更新 GPU 运行库，支持 RTX 50 系列，改进 GPU 自检提示。
- 新增“兼容播放”选项，改善部分设备上的原曲、人声无声问题。
- 悬停钢琴音名时，高亮对应音高行及可见的同音高块，改进歌曲列表布局。
- 修复用户目录较长时可能出现的分析失败。
- 运行组件需要重启时，先完成安装，再统一提示重启，无须重新运行安装程序。

## 安装与升级

首次安装和升级均使用完整包。[GitHub 分卷版](https://github.com/Atal1a/VocalPitchLab/releases/latest)需将安装程序与全部 `.bin` 分卷放在同一文件夹；[夸克单文件版](https://pan.quark.cn/s/fec1530accea)直接运行安装程序。

已有用户关闭软件后，覆盖安装到原目录，无须先卸载。歌曲库、设置和分析结果会保留，建议提前备份 `%LOCALAPPDATA%\VocalPitchLab`。

原曲或人声无声时，在设置中开启“兼容播放”，完全退出后重新启动软件，无须重新分析。

## 兼容说明

GPU 加速需要支持具体显卡的 NVIDIA 驱动，本版运行库要求 570.65 或更新版本。无需配置 Python 或 CUDA Toolkit。

安装包未签名。代码采用 GPL-3.0-only，第三方组件与模型许可见 `THIRD_PARTY_NOTICES.md`。
