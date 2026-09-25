# 发布准备与性能边界

当前工作顺序以 [RELEASE_PLAN.md](RELEASE_PLAN.md) 为准：暂停重复打包，优先完善正式发布条件。分卷预览在 Windows Sandbox 中安装成功，但缺少 VC++ 运行库导致首次分析失败；仅在沙盒补装微软官方运行库后，分析、播放和卸载通过。原包仍未通过无前置条件验收，详见 WINDOWS_SANDBOX_QA.md。新增 GPU 运算自检和回退提示尚未重新打包。运行 installer/release_check.py 可列出仍未满足的发布条件。

## 离线裁剪决定（2026-09-25）

按用户决定，暂不做按需安装。安装包保留正式模型和 CUDA 版 PyTorch；兼容 NVIDIA 显卡优先 CUDA，其他设备保留 CPU 回退。仅使用 PyTorch 不能保证所有显卡加速。

已加入可重复的保守裁剪构建，删除开发静态库/头文件、Qt 开发工具和未使用的 FCPE 实验包，共 909,539,011 字节。未改变模型精度和分析算法。45 个正式模型/Torch DLL 校验值与原包一致；裁剪环境通过 QML 任务队列的 20 秒 CUDA 全流程及原曲、人声播放检查。依赖测试目录存在运行时引用，已在验证发现问题后恢复，不能一概删除。详见 installer/BUILD.md 和 outputs/slim-validation。

以下较早记录中的按需分发建议已被本次离线优先决定取代。安装包公开分发仍需完成许可审查与独立干净系统验证。

新版离线预览安装器为 3,945,336,309 字节，比首包减少 111,752,732 字节。隔离安装、包内 Python 的 CUDA 全流程及原曲/人声播放均通过，卸载成功且保留测试用户数据。证据见 outputs/slim-installed-validation；仍不等于独立新电脑验证通过。

## 安装包准备进展（2026-09-24）

以下为最新状态，下方原始评估保留作历史。

- 已制作内置 Python/Qt/分析依赖和模型的本地预览安装包，支持每用户安装、快捷方式和卸载。它不是公开发行包；构建器默认阻止未明确指定 local-preview 的打包。
- 运行代码已拆分 APP_ROOT/DATA_ROOT/MODEL_ROOT；安装版歌曲库/结果在用户 LocalAppData。FFmpeg 从应用 bin 或 PATH 定位，不再依赖 E:/ffmpeg；模型分析配置已移入 resources。
- 自有代码现采用 GPL-3.0-only LICENSE（此前 MIT 为准备阶段记录，已更新）；第三方清单见 THIRD_PARTY_NOTICES.md，实际打包依赖元数据保留在 build/local-preview/THIRD_PARTY_INVENTORY.json。许可审核尚未完成。
- 模型下载器支持固定版本、SHA256、临时文件和安全解压；资源见 resources/model-manifest.json。BS 和 GAME 权重的明确分发授权待确认，公共下载流程不会假装已经获准。
- CREPE 自动降批量、RoFormer 缩窗口/CPU 回退、RMVPE 缩块/CPU 回退已实现；模拟 OOM 与无关异常测试通过。真实开关、任务取消、缓存和 QML 回归通过。
- 同机 CPU 和 4GiB 分配预算的完整 20 秒短片段测试已通过，详见 PERFORMANCE_PREVIEW.md；最低配置仍未确认。
- 打包目录约 7.23GB，首份安装器 4,057,089,041 字节。GitHub Release 单附件须小于 2GiB（https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases）。脚本提供 GithubAssets 分卷选项，但当前首份验收包为单文件，不能直接上传。后续优先裁剪运行库并拆出按需模型/加速资源。
- 当前包未代码签名；尚需独立干净 Windows、升级和整曲低配置测试。Windows Sandbox 验收脚本已准备，不能在无结果日志时宣称通过。
- 实际安装验收：在本机 work/installed-preview 安装成功，用包内 Python 经 QML 队列完成 4 秒 CPU 全流程（约 50.81 秒），卸载返回 0，独立用户数据仍在。记录 outputs/installer-local。Sandbox 启动后没有回传日志，已停止此次测试，不计为干净系统通过。
- 首份本地验收包 SHA256：5F792DC6AEBEA9F18D70C449F219CD058CAD6685004B6D48A2CA735B2B670A62。对应打包快照保留 build/local-preview；后续新增下载器和文档需在下一次构建进入包内，不能假定已存在于这份首包。
- 空目录模型下载实测：RMVPE、Kim、BS、GAME 全部从固定来源下载并通过 SHA256，GAME 解压后的六个文件也逐一匹配既有校验值。使用显式 local-evaluation 模式，仅证明技术下载链路，不表示许可问题已解决。

当前为 Windows 本地研究原型，尚未验证最低配置，不应宣称低配全流程兼容。

- 查看已分析结果与首次分析是两类负载。模型主要用于首次分析；播放、曲线和音符显示不需要反复运行模型。
- 最重的环节是两级 RoFormer 分离。当前使用 float32、batch=1、overlap=4。CREPE 仍运行 tiny/full 两次（界面虽隐藏，后台尚未删减），full 的证据参与曲线可靠性。GAME 使用 ONNX CPU，RMVPE 按 20 秒分块。
- RTX 4080 16GB 现有 RISE 192.88 秒样本：第一阶段记录约 34.34 秒，BS 第二阶段独立实验约 47.3 秒。这不是同一次端到端测量，未含全部加载、CREPE、RMVPE、GAME 和写盘，不能标为完整分析耗时。
- 没有 CUDA 时分析入口会选择 CPU，但尚未做 CPU 完整链路验证；AMD/Intel 显卡没有在当前实现中验证 GPU 加速。低显存没有自动缩块或显存不足回退，仅有失败提示。因此存在慢或显存不足无法完成的情况。
- 发布前应测 4/6/8GB 显存、CPU-only、8/16GB RAM 的真实整曲峰值与耗时。暂不填写未经验证的最低配置表。
- 浮点双声道 44.1kHz WAV 每分钟约 20.2 MiB；多级中间音频及两种缓存会成倍增加磁盘占用。

## 尚需解决

1. 安装脚本仍默认 E:/Python312/python.exe，CUDA 包固定，未覆盖全套 GAME/分离权重下载及干净机器安装。核心分析还读取 results/vocadito-v1/selected-config.json，需要将运行必需配置从研究结果目录迁入可分发资源。
2. 不直接上传当前工作目录：input、library、results、models、datasets、outputs 已加入忽略；outputs 含试听歌曲片段。还需检查 vendor 中的运行库、二进制、模型资产和各文件的来源/许可。
3. 根目录未提供项目 LICENSE；需选择项目许可并完成第三方代码与权重许可整理。代码公开不自动意味着模型可随安装包再分发。
4. 优先做自动资源适配（缩小推理批量/分块、显存不足处理），无须恢复多个算法选择按钮。删除不再使用的实验计算前应验证曲线可靠性及缓存兼容性。

本轮仅修复 UI、补充忽略规则与准备记录，没有创建公开仓库或上传文件。
