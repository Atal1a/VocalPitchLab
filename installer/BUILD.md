# Windows 构建

需要 Windows x64、Python 3.12、Inno Setup 和 .NET Framework 编译器。

- `resources/reproducible/` 保存依赖清单、下载地址、校验值与补丁。
- `rebuild_environment.py` 从准备好的依赖文件建立独立运行环境。
- `prepare_delivery.py` 汇集应用代码、运行库、模型及许可证文件。
- `VocalPitchLab.iss` 生成安装程序，支持首次安装和覆盖更新。
- `prepare_github_assets.py` 生成分卷校验文件与安装说明。
- `prepare_source_bundle.py` 导出源码包，不包含歌曲、模型权重、用户数据和本机测试记录。

构建脚本使用项目下的 `work/`、`build/` 和 `dist/` 目录。依赖缓存、模型及构建工具需另行准备；源码仓库不包含这些大型文件。模型来源与使用条件见 `../THIRD_PARTY_NOTICES.md` 和 `../MODEL_LICENSE_REVIEW.md`。

安装包编译示例：

```powershell
ISCC /DStageDir=<应用目录的绝对路径> /DGithubAssets installer/VocalPitchLab.iss
```

`build_preview.py` 和沙盒脚本用于本地验证。安装包未进行代码签名。
