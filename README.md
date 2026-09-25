# VocalPitchLab

Windows 本地人声音高分析软件，结合音高曲线与主要音符块展示演唱旋律。

- 原曲与分离人声试听、循环与标准音比对。
- 固定默认分析流程，可关闭和声分离。
- 本地歌曲库、深浅主题与音域/时间缩放。

目标交付为 Windows x64 离线安装包，入口为 **VocalPitchLab.exe**，不要求用户自行配置 Python 或 CUDA Toolkit。安装方式见 [INSTALLATION.md](INSTALLATION.md)。详细使用说明后续补充。

## 当前状态

1.0.0 已进入交付封装阶段。本轮封装未追加运行测试，未签名；最低硬件配置尚未确定。第三方模型与二进制的分发事项仍在整理，完整安装包不能仅凭本仓库许可证视为获得全部第三方授权。

## 许可

项目自有代码采用 **GPL-3.0-only**。第三方代码、模型和运行库保留各自条款，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [MODEL_LICENSE_REVIEW.md](MODEL_LICENSE_REVIEW.md)。仓库不包含歌曲、用户数据、模型权重或本机运行环境。
