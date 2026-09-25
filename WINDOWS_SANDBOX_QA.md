# 干净 Windows 沙盒验收

本测试使用真实 Windows Sandbox 来宾系统，区别于宿主机上的新 Python 环境。安装文件、输入音频只读映射，结果目录可写；网络关闭、vGPU 关闭、内存设置为 8192 MB。测试使用安装包内置 Python，不预装 Python、CUDA Toolkit 或开发依赖。

## 重复执行

先保留现有沙盒工作，关闭沙盒。准备一个短 WAV 测试文件和包含安装器及全部分卷的目录，在项目根目录执行：

```powershell
powershell -NoProfile -File installer/prepare_sandbox.ps1 -SetupDirectory dist/github-offline-preview -AudioFile work/sandbox-input/sample.wav
```

打开输出的 validate.wsb。准备脚本不会启用系统功能或修改虚拟化设置。运行时自动安装、创建 QML 引擎、执行默认分析、检查原曲和人声播放进度、卸载并检查用户数据保留。只有输出 acceptance.json 的 status 为 passed 才表示这些项目通过；单纯打开桌面不算通过。

输出包含系统身份、安装器 SHA256、安装日志、分析日志和结果。若沙盒启动失败，可能没有来宾日志，需要区分系统启动故障与软件安装故障。

## 覆盖边界

- sandbox_check.py 使用 Qt offscreen；验证 QML 创建和业务流程，不代替可见窗口的渲染、交互和听感验收。
- 使用 CPU 是为了检验无 CUDA 环境下的依赖完整性，不代表推荐用户用 CPU 分析，也不能确定最低配置。
- 关闭 vGPU 的沙盒不验证 NVIDIA CUDA、不同驱动和 GPU 代际兼容性。
- 短片段不能代替整曲、峰值内存压力、升级迁移或 Windows 10 测试。
- 当前预览安装包早于最新源码、GPU 运算自检、FFmpeg 查找修正与许可证更新。结果只适用于记录哈希对应的包，正式构建必须重跑。

## 本轮结果

后续更新：VC++ 离线安装处理已写入 installer/vc_redist.iss，官方文件已保存。用户要求补齐后不再测试，因此没有对新增集成重跑验收，也没有重编译现有安装器。以下结果仅为此前的沙盒记录。

2026-09-25：初次启动丢失连接；修正配置中 vGPU 的大小写并重启后成功进入来宾系统。不能据此认定大小写就是断连的唯一原因。

实际结果见 outputs/sandbox-clean。分卷预览安装成功且无需重启，安装约 5 分 42 秒；来宾身份 WDAGUtilityAccount / Windows 11 Enterprise，安装前未发现 Python。

首次默认分析失败于人声分离库导入 ONNX Runtime：`onnxruntime_pybind11_state` 报 DLL load failed，同时 Torch 提示缺少 Microsoft Visual C++ Redistributable。原包不能标为干净系统可用。失败证据保留在 acceptance.json、sandbox-error.txt 和工作进程日志。

已从微软官方 `https://aka.ms/vc14/vc_redist.x64.exe` 获取运行库，宿主验证 Microsoft Corporation 有效数字签名，仅在沙盒中安装以验证修复方向。版本 14.51.36247；哈希和安装日志保存在同一结果目录。该补装不属于原安装包，也不等于已修好发布包。正式方案必须包含离线运行库供应、许可记录、所需权限/重启处理，以及无额外操作的重新验收。

补装返回 0、无需重启后，使用全新的测试数据目录重跑：4 秒音频完成默认分析，耗时 88.141 秒；原曲与独立人声播放进度检查通过。另启动实际 launch.py，通过沙盒窗口确认主界面、歌曲库和图表区域能够显示；未做全套视觉或听感验收。卸载返回 0，内置 Python 被移除，外部用户数据保留。证据在 outputs/sandbox-clean/after-vc，结论为 **补装后通过基础流程，原安装包仍未通过无前置条件验收**。
