<a name="chinese"></a>

[简体中文](#chinese) · [English](#english)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/hero-dark.svg">
  <img src="docs/images/hero-light.svg" alt="VocalPitchLab — 开源人声音高分析工具" width="1200">
</picture>

<p align="center">
  面向流行音乐的开源人声音高分析应用，在 Windows 本地运行。
</p>

<p align="center">
  <a href="docs/releases/RELEASE_NOTES_1.2.0.md"><img src="docs/images/badge-version.svg" alt="版本 1.2.0" height="28"></a>
  <a href="docs/INSTALLATION.md"><img src="docs/images/badge-platform.svg" alt="Windows x64" height="28"></a>
  <a href="LICENSE"><img src="docs/images/badge-license.svg" alt="GPL-3.0-only" height="28"></a>
</p>

<p align="center">
  <a href="https://github.com/Atal1a/VocalPitchLab/releases/latest"><strong>GitHub 下载</strong></a>
  &nbsp; · &nbsp;
  <a href="docs/INSTALLATION.md">安装说明</a>
  &nbsp; · &nbsp;
  <a href="https://github.com/Atal1a/VocalPitchLab/issues">问题反馈</a>
</p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/workspace-dark.webp">
  <img src="docs/images/workspace-light.webp" alt="VocalPitchLab 主界面：歌曲库、音高曲线、主要音符块与播放控制" width="1200">
</picture>

## 音高分析

导入歌曲后，软件分离人声并分析音高。连续曲线显示滑音、转音和颤音，主要音符块标出音高与持续时间。支持调整时间和音域范围，查看整段旋律或单个音符。

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/pitch-demo-dark.gif">
  <img src="docs/images/pitch-demo.gif" alt="播放时同步显示音高曲线与当前音名" width="1040">
</picture>

## 钢琴试听

点击曲线左侧的音名，试听对应的标准钢琴音。按住音名可延音，松手释放。可以暂停后逐音比对，也可以循环播放一段乐句，反复听辨音高。

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/piano-demo-dark.gif">
  <img src="docs/images/piano-demo.gif" alt="钢琴试听时，对应音名与音高位置同步高亮" width="1040">
</picture>

## 更多功能

| 功能 | 可以做什么 |
| :--- | :--- |
| **音频分离** | 独立设置人声分离和和声分离，切换原曲与分离人声，或将分离后的音轨导出为 WAV。 |
| **播放与视图** | 循环播放、调整音量，缩放时间与音域，或使用自适应视图。 |
| **歌曲库** | 导入与批量管理歌曲，保存分析结果和查看位置。 |
| **界面** | 支持简体中文、英文、浅色和深色主题，可开启「降低运行负载」。 |

## 开始使用

1. 从 [GitHub Releases](https://github.com/Atal1a/VocalPitchLab/releases/latest) 下载同一版本的安装程序和**全部 `.bin` 分卷**，放在同一文件夹，保持原文件名。
2. 运行安装程序完成安装，无需配置 Python 或 CUDA Toolkit。已有用户先关闭软件，再覆盖安装到原目录，无须先卸载。
3. 打开 VocalPitchLab，点击「导入歌曲」，等待分析完成后播放、查看和比对。

兼容的 NVIDIA 显卡和驱动可以加速分析；没有可用的 GPU 加速时会使用 CPU，分析明显较慢。首次安装、覆盖更新及常见问题，见 [安装说明](docs/INSTALLATION.md)。

部分合唱或高音叠唱可能被和声分离削弱，此时可将当前歌曲的「和声分离」切换为「关」。

原曲或人声无声时，可在设置中开启「兼容播放」，完全退出后重新启动软件，无须重新分析。

## 开发与许可

源码目录、运行方式和依赖见 [开发说明](docs/DEVELOPMENT.md)，版本变化见 [更新记录](docs/CHANGELOG.md)。

项目自有代码采用 [GPL-3.0-only](LICENSE) 许可。第三方组件与模型适用各自许可，见 [第三方说明](docs/THIRD_PARTY_NOTICES.md)。

---

<a name="english"></a>

## English

[简体中文](#chinese) · [Release notes](docs/releases/RELEASE_NOTES_1.2.0.en.md) · [Installation](docs/INSTALLATION.en.md)

VocalPitchLab is an open-source app for analyzing vocal pitch in popular music. It runs locally on Windows.

[Download from GitHub](https://github.com/Atal1a/VocalPitchLab/releases/latest) · [Report an issue](https://github.com/Atal1a/VocalPitchLab/issues)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/workspace-dark.webp">
  <img src="docs/images/workspace-light.webp" alt="VocalPitchLab workspace showing the song library, pitch curve, main note blocks, and playback controls" width="1200">
</picture>

### Pitch analysis

Import a song to separate the vocals and analyze their pitch. The continuous pitch curve shows slides, vocal runs, and vibrato. Note blocks show the pitch and duration of the main notes. Adjust the time window and pitch range to view an entire melody or inspect an individual note.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/pitch-demo-dark.gif">
  <img src="docs/images/pitch-demo.gif" alt="The pitch curve and current note label update as the song plays" width="1040">
</picture>

### Piano preview

Click a note label to the left of the chart to hear its piano pitch. Hold the label to sustain the note and release it to let the note fade. Pause to compare individual notes, or loop a phrase to listen repeatedly.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/piano-demo-dark.gif">
  <img src="docs/images/piano-demo.gif" alt="The note label and its pitch row are highlighted during piano preview" width="1040">
</picture>

### More features

| Feature | What you can do |
| --- | --- |
| **Audio separation** | Set vocal separation and harmony separation independently, switch between the original mix and isolated vocals, and export separated tracks as WAV files. |
| **Playback and view** | Loop a section, adjust the volume, zoom the time window or pitch range, and fit the view to the pitch range. |
| **Song library** | Import and manage songs in batches, and keep analysis results and view positions. |
| **Interface** | Switch between Simplified Chinese and English, use a light or dark theme, and enable **Reduce graphics load**. |

### Get started

1. Download the installer and **all matching `.bin` volumes** for the same version from [GitHub Releases](https://github.com/Atal1a/VocalPitchLab/releases/latest). Keep their original names and place them in the same folder.
2. Run the installer. No separate Python or CUDA Toolkit setup is required. To upgrade, close the app and install into the existing folder. There is no need to uninstall first.
3. Open VocalPitchLab, choose **Import songs**, and wait for analysis to finish before playing and comparing pitches.

A compatible NVIDIA GPU and driver can speed up analysis. Without GPU acceleration, analysis runs on the CPU and takes considerably longer. See the [installation guide](docs/INSTALLATION.en.md) for first-time installation, upgrades, and troubleshooting.

Harmony separation can attenuate some group vocals or layered high notes. If that happens, turn off **Harmony separation** for the current song.

If the original mix or isolated vocals play without sound, turn on **Playback compatibility** in Settings, then close and reopen the app. Existing analysis results can be reused.

### Development and licensing

See the [development guide](docs/DEVELOPMENT.en.md) for the source layout, dependencies, and how to run the app. See the [changelog](docs/CHANGELOG.en.md) for version history.

The project’s own code is licensed under [GPL-3.0-only](LICENSE). Third-party components and models retain their respective licenses. See the [third-party notices](docs/THIRD_PARTY_NOTICES.md).

---

<p align="center">
  VocalPitchLab &nbsp; · &nbsp; <a href="https://github.com/Atal1a">Atalia</a>
</p>
