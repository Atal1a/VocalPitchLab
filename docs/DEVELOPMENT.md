# 开发

使用 Python 3.12 和 `requirements.txt` 中的依赖，在项目根目录运行：

```powershell
python main.py
```

也可使用 `python -m vocalpitchlab`。模型与配置见 `resources/`，构建方法见 [Windows 构建](../installer/BUILD.md)。

## 目录

- `vocalpitchlab/ui/`：界面、图表绘制与交互。
- `vocalpitchlab/analysis/`：分析流程、音高与音符、缓存及后台任务。
- `vocalpitchlab/audio/`：音频读取、人声分离、模型复用及钢琴试听。
- `vocalpitchlab/runtime/`：路径、硬件检测、资源策略及模型文件管理。
- `qml/`：界面组件与主题。
- `installer/`：环境准备、安装包构建与交付检查。
- `tests/`：目录结构、启动入口、后台进程，以及安装包、隐私过滤和更新流程检查。
- `vendor/`：保留原始署名与许可的第三方代码。

`VPL_DATA_DIR` 和 `VPL_MODEL_DIR` 可指定数据与模型目录。资源路径以项目或安装目录为基准，不依赖当前工作目录。

后台分析入口：`python main.py --analyze <音频路径>`。批量任务使用 `--analysis-worker`，通过标准输入接收逐行 JSON。
