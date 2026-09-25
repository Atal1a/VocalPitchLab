# 干净 Python 环境重建验收

日期：2026-09-25。仅本地技术验收，不是公开分发许可或全新 Windows 认证；没有重新编译安装包。

## 已完成

- 用 Windows x64 CPython 3.12.0 创建独立 venv，未复制旧 `.venv` 或旧安装包的 site-packages。
- 主运行环境 75 个 wheel，隔离的分离运行库 6 个 wheel。79 个上游 wheel 对照 PyPI/PyTorch 发布者 SHA256；antlr4-python3-runtime 和 demucs 从上游 sdist 用固定 setuptools 78.1.0 / wheel 0.45.1 构建，并保存源码来源及哈希。
- 所有安装输入固定在 resources/reproducible/artifacts.json；runtime.lock、separation.lock 使用 SHA256。实际安装采用 `--no-index --no-deps --require-hashes`，无安装期在线解析。
- 分离库原版与本地代码比较仅一处不同：RoFormer 权重加载增加 weights_only=True。补丁、修改前后哈希均已保存，应用失败会中止构建。
- 模型、配置、FFmpeg 和两份模型索引共 14 个文件固定哈希。权重复用已校验缓存，不重复下载。模型索引是离线运行所需输入，不能只保留权重。
- 应用源文件按允许清单复制到独立目录，使用新的歌曲库和结果目录。NumPy、PyTorch、PySide6 的实际导入路径均属于新环境。
- 修复 FFmpeg 查找顺序：显式 VPL_FFMPEG 优先，其次应用附带文件，最后 PATH。避免默认被系统 PATH 中的其他版本替换。

## 验证结果

证据：outputs/clean-environment/checks.json、outputs/clean-environment-offline/checks.json。

- QML 启动、默认 Kim → BS → RMVPE 连续 → GAME/曲线音符流程通过，使用 CUDA。
- 20 秒 RISE 片段完成分析；原曲与独立人声播放进度正常前进。
- Windows MIDI 钢琴设备成功打开、发送音符与停止；为避免干扰，测试将 expression 设为 0，未做听感验收。
- 正在进行的任务可取消、任务可删除，旧结果保留。
- 设置与歌曲库关闭后重新打开仍正确。
- 第二轮通过包装分析工作进程阻止 Python socket 外连；全流程通过。此项不是对整台 Windows 禁网，也不声称检查了所有原生库网络行为。
- 发布检查 now 根据验收报告和源文件哈希判断干净环境项，源文件变化后需重新验证。

## 重复安装（维护者使用）

在项目根目录，用独立的 Windows x64 Python 3.12 执行：

```powershell
python installer/rebuild_environment.py --local-evaluation --stage work/repro-build/app-next
```

默认读取 work/repro-build 下的 wheels、vendor-wheels。可以用 `--artifacts` 指向保留的输入目录。stage 必须是 work 下不存在的新目录，不覆盖工作环境。脚本先校验全部 wheel 和本机模型文件，离线安装后应用补丁、复制应用源码及资源。

验收示例（使用新环境的解释器，data 目录必须不存在）：

```powershell
work/repro-build/app-next/runtime/Scripts/python.exe -I installer/clean_environment_check.py --app work/repro-build/app-next --audio outputs/lead-separation/rise/input.wav --data work/repro-build/qa-next --output outputs/clean-environment-next
```

测试歌曲是本地验收输入，不提交到仓库或安装包。可替换为自己的音频。

## 输入获取与范围

预编译 wheel 的固定下载 URL 与发布者哈希见 artifacts.json；GPU 包来自 PyTorch cu124 官方索引，其他包来自 PyPI。源码构建的两个 wheel 需保留本轮 wheel 工件，其输入 sdist、构建工具版本和日志已记录。**当前保证由同一组固定 wheel 重复安装；不声称源码重编译后 wheel 压缩文件逐字节一致。** `lock_artifacts.py` 是维护者更新依赖时生成锁的工具，不应在普通重建时重新生成校验值。

主运行环境 `pip check` 通过。分离库采用独立 vendor 目录和固定 RoFormer 路线；其完整上游包另声明 diffq-fixed、onnx-weekly、onnx2torch-py313、samplerate，当前未安装。代码审查定位到未启用的其他架构等路径，固定流程实测通过；这不是完整 audio-separator 安装。installer/audit_dependency_scope.py 会显式列出这些差异并对新增意外缺失报错，不能把主环境 pip check 说成全部上游依赖无缺失。

## 仍需进行

- Windows Sandbox 已暴露并验证 VC++ 运行库缺失：原预览包分析失败，沙盒补装官方运行库后分析、播放与卸载通过。正式安装包须补齐离线前置依赖再验收，详见 WINDOWS_SANDBOX_QA.md；真实 GPU 驱动仍需另测。
- 由这套新环境生成独立运行时的打包路径；旧 build_preview.py 仍是开发环境复制式预览入口，不自动升级为正式构建。
- Python 解释器发行物来源/校验、wheel 工件长期保存及构建工具输入的进一步归档。
- 真实整曲低配置、其他 GPU 代际和升级迁移测试。
- 模型与第三方组件的许可问题仍按 RELEASE_PLAN.md 保留。
