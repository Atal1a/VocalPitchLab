# 安装 VocalPitchLab 1.3.0

[English](INSTALLATION_1.3.0.en.md)

适用于 Windows x64。两种版本都可离线安装和分析。

| 版本 | 安装文件 |
| --- | --- |
| CPU | `VocalPitchLab-1.3.0-windows-x64-cpu-offline-setup.exe` |
| NVIDIA | `VocalPitchLab-1.3.0-windows-x64-setup.exe` 和同名的 `-1.bin`、`-2.bin`、`-3.bin` 分卷 |

CPU 版适用于没有兼容 NVIDIA 显卡的电脑。NVIDIA 版可加速分析。CUDA 12.8 运行库需要 Windows NVIDIA 驱动 570.65 或更新版本，并支持所用显卡。

把 NVIDIA 安装程序和三个分卷放在同一文件夹，保留原文件名。运行对应版本的 `.exe`，按向导安装。若向导提示重启，请在重启后再打开应用。

## 从 1.2.0 升级

已安装 1.2.0 Windows x64 版时，可以用 `VocalPitchLab-1.3.0-windows-x64-update-from-1.2.0.exe` 升级到 1.3.0 NVIDIA 版。关闭 VocalPitchLab 后运行更新程序。若向导未找到原安装目录，请手动选择该目录。更新会复用运行库和模型，保留歌曲库、设置和分析结果。

从其他版本升级到 NVIDIA 版，或修复缺失、被修改的安装文件时，使用 NVIDIA 完整安装包并选原安装目录。

修复 CPU 版时，使用 CPU 完整安装包并选原安装目录。

## 切换安装版本

在 Windows 设置中卸载现有版本，再安装 CPU 或 NVIDIA 版。卸载会保留 `%LOCALAPPDATA%\VocalPitchLab` 下的歌曲库、设置和分析结果。
