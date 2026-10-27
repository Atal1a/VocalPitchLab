# Windows 构建

需要 Windows x64、Python 3.12、Inno Setup 和 .NET Framework 编译器。

- `resources/reproducible/` 保存依赖清单、下载地址、校验值与补丁。
- `rebuild_environment.py` 从准备好的依赖文件建立独立运行环境。
- `prepare_delivery.py` 汇集应用代码、运行库、模型及许可证文件。
- `privacy_check.py` 检查内部文档、编译缓存和本机路径；额外检查名单由本地 JSON 文件传入，不纳入仓库。
- `VocalPitchLab.iss` 生成安装程序，支持首次安装和覆盖更新。
- `prepare_github_assets.py` 检查发布附件并生成安装说明。
- `prepare_source_bundle.py` 导出源码包，仅包含维护中的单元测试和安装包测试，不包含歌曲、模型权重、用户数据和旧实验脚本。生成压缩包前检查本机路径；`--deny-file` 可追加本地隐私检查名单。

构建脚本使用项目下的 `work/`、`build/` 和 `dist/` 目录。依赖缓存、模型及构建工具需另行准备；源码仓库不包含这些大型文件。模型来源与使用条件见 [第三方说明](../THIRD_PARTY_NOTICES.md) 和 [模型许可记录](../MODEL_LICENSE_REVIEW.md)。

GPU 运行环境固定为 PyTorch 2.7.1、torchaudio 2.7.1 的 CUDA 12.8 构建，配套版本记录在 `resources/reproducible/runtime.lock`。这组构建包含 RTX 50 系列需要的 `sm_120` 内核。`prepare_delivery.py` 会拒绝与锁定版本不一致的 GPU 依赖；更换运行库后需要重新组装完整包，或明确使用包含运行库的更新模式。

使用新缓存目录时，向 `lock_artifacts.py --artifacts <缓存目录>` 和 `rebuild_environment.py --artifacts <缓存目录>` 传入同一目录。缓存内每个包只保留一个目标版本；`wheels/` 与 `vendor-wheels/` 分别对应两个锁定清单。

组装后，用候选目录自带的 Python 检查版本、GPU 实际运算、音频算子以及 `sm_120` 内核：

```powershell
<候选目录>/runtime/python.exe -I -B tests/package_gpu_check.py <候选目录> --output <测试结果目录>/gpu.json
```

GitHub 发布附件包括完整安装程序、配套分卷、源码包、安装说明和更新内容。单文件完整安装包通过夸克网盘提供。

常规安装包构建使用 Ultra64 分组固实压缩：

```powershell
python installer/package_benchmark.py --stage <应用目录> --output <新的输出目录> --version 1.1.1 --profiles ultra64-solid --removals <组装报告目录>/optional-trim.json
```

`build_preview.py` 和沙盒脚本用于本地验证。安装包未进行代码签名。

安装器支持 `/PACKAGEVALIDATION=1` 验证模式，配合 `/DIR=<临时目录>` 使用；不创建快捷方式、卸载记录或修改正式安装的注册信息。此模式仍会检查必要的微软运行组件。正式安装不传此参数。


## 离线安装包体积对比

使用独立目录保存候选包，正式安装包不作为构建输出目录。测试脚本需要构建环境安装 `psutil`。

```powershell
python installer/prepare_delivery.py --version 1.1.1 --stage build/delivery-candidate --dependencies work/repro-build/app --base-runtime build/slim-preview/runtime --report-dir work/delivery-reports
python installer/package_benchmark.py --stage build/delivery-candidate --output work/package-comparison --removals work/delivery-reports/optional-trim.json
```

`package_benchmark.py` 比较 `fast`、`max`、`max-solid`、`ultra64-solid` 四种压缩配置。每组都会生成完整分卷安装包，安装到独立目录并核对文件 SHA-256。构建结果记录附件清单、体积、构建与安装耗时及进程树采样峰值内存。内存值采用 100 毫秒采样，不代表精确瞬时峰值。

常规构建使用 `--profiles ultra64-solid`；不传 `--profiles` 时比较全部配置。中断后使用 `--resume` 继续；输入文件必须保持一致。恢复已完成的配置需要构建结果中包含附件记录，旧格式结果需另选目录重新构建。`--version` 指定安装器版本，`--compiler` 指定 Inno Setup 编译器。

分组固实压缩按应用、模型、Python 依赖、PyTorch/CUDA 和 Qt 设置边界；微软运行组件使用独立压缩块。裁剪仅移除通过引用检查的 Qt 浏览器模块。模型及 GPU 运行库保持原样。覆盖安装根据裁剪清单清理旧文件，只有内容校验值匹配时才删除。

安装后的功能检查使用独立数据目录和本地音频：

```powershell
<安装目录>/runtime/python.exe -I -B tests/package_smoke.py <安装目录> <测试数据目录> <测试音频.wav>
```

该检查禁用 Python 网络连接，覆盖分析、播放、人声切换、任务取消、主题、文件对话框和歌曲库重开。

目录组装默认裁剪已确认未使用的 Qt 浏览器模块；`--keep-unused-qt` 可生成包含这些模块的对照目录。

`--deny-file` 可指定本地隐私检查名单。安装校验后会检查禁止公开的文件及匹配内容。

## 独立更新包

```powershell
python installer/build_update.py --baseline <正式版应用目录> --stage <新版本应用目录> --from-version 1.1.0 --version 1.1.1 --output work/update-1.1.1 --removals <组装报告目录>/optional-trim.json
```

基线必须来自已发布且校验通过的完整安装包。构建器逐文件比较 SHA-256，默认只携带程序和资源的变化。需要替换 Python 运行环境内的依赖时，显式传入 `--include-runtime`；该模式使用分卷，保留原有模型，并为替换及移除的文件预留备份空间。模型、第三方分离代码或 FFmpeg 需要替换时仍使用完整安装包。

包含运行库的更新示例：

```powershell
python installer/build_update.py --baseline <1.1.1 正式安装目录> --stage <1.1.2 应用目录> --from-version 1.1.1 --version 1.1.2 --include-runtime --output <新的更新包目录>
```

更新器验证旧启动器版本和所有复用文件；只接受对应基线或目标版本的文件。程序运行时不更新，目录链接和不完整环境会被拒绝。替换或移除文件前备份，提交前核对完整目标清单；失败或再次运行时恢复备份。旧依赖元数据与其他待移除文件同样参与恢复。重复运行更新包可用，用户数据目录不参与更新。

完整包和更新包使用相同安装身份，卸载记录合并。测试使用 `/PACKAGEVALIDATION=1` 和隔离目录；该参数不绕过版本、校验及恢复检查。
