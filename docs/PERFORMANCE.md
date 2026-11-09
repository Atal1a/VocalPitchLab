# 播放性能测试

[English](PERFORMANCE.en.md)

测试入口为 `tests/package_playback_benchmark.py`，使用原生 Windows 和 Direct3D 11 显示完整界面。默认生成两首四分钟的合成测试歌曲，不需要运行分析模型。测试环境需要项目依赖和 `psutil`。

每次使用新的输出目录。测试歌曲、临时歌曲库、截图和结果均保存在该目录中。传入已有歌曲库时，只读取其分析结果，并在输出目录创建独立的歌曲库配置。

## 常规对照

在项目根目录运行：

```powershell
python tests/package_playback_benchmark.py --output work/playback-native --seconds 10 --spans 3 20 39 40 0 --scales 1 1.5 2 --repeat 2 --show-window
```

`--spans` 指定显示的时间范围，`0` 表示整首。`--scales` 指定目标显示缩放，结果中的 `effective_dpr` 是实际使用的倍率。测试窗口需要保持可见；遮挡、最小化和远程桌面都可能影响呈现节奏。`--show-window` 显示测试窗口；省略时将窗口置于底层，适合功能检查，不适合据此判断屏幕上的流畅程度。

使用已有分析结果：

```powershell
python tests/package_playback_benchmark.py --output work/playback-song --library library/index.json --song-index 0 --seconds 30 --show-window
```

所选歌曲和另一首用于切歌检查的歌曲需要已有完整、有效的展示缓存。旧结果需要补齐时，测试会退出，不自动迁移原结果。交互检查会跳转到 30、42、50 秒，适合长度超过一分钟的歌曲。

比较两个源码版本时，使用同一测试脚本、同一组参数，并通过 `--app-root` 指定另一份源码目录。每组至少重复两次，并交替运行版本，减少启动次序和温度变化的影响。

## CPU 压力

```powershell
python tests/package_playback_benchmark.py --output work/playback-cpu --seconds 10 --cpu-cores 2 --cpu-core-budget 0.5 --show-window
```

这会将测试进程限制到两个可用逻辑处理器，并通过 Windows Job Object 将进程组的平均 CPU 时间预算限制到约半个逻辑处理器。预算按整机逻辑处理器数量换算，实际值会写入结果。限制只作用于本次测试的工作进程及其后续子进程。

CPU 配额耗尽后，系统会暂停该进程组，直到下一个调度区间。这是调度压力测试，不能对应某款旧 CPU。只限制核心数也不会降低现代处理器的单核执行速度。超过 64 个逻辑处理器的主机暂不支持本脚本的 CPU 预算换算。

## 软件图形路径

```powershell
python tests/package_playback_benchmark.py --output work/playback-warp --renderer warp --seconds 10 --show-window
```

此模式使用 Direct3D 11 的 WARP 软件光栅化路径，保留界面的图层和效果。脚本会检查渲染日志，确认实际使用了 Microsoft Basic Render Driver。它可以覆盖缺少硬件图形加速的情况，不能代表某款旧核显。

不要用 Qt 的纯软件后端代替完整界面对照；该后端不支持部分着色器效果，可能遗漏需要测量的内容。

## 固定内存虚拟机

Hyper-V 测试机可以配置为两档：

| 配置 | 虚拟处理器 | 固定内存 |
|---|---:|---:|
| 8GB | 4 | 8GB |
| 4GB | 2 | 4GB |

在安装了 Hyper-V 管理工具的主机上，先关闭专用测试虚拟机，再运行：

```powershell
./installer/configure_performance_vm.ps1 -VMName 'VPL-Test' -Profile 4gb -WhatIf
./installer/configure_performance_vm.ps1 -VMName 'VPL-Test' -Profile 4gb
```

脚本只调整指定的现有虚拟机，不创建虚拟机、不安装 Windows，也不自动关闭运行中的系统。动态内存会关闭。默认 CPU 上限为 100%，需要单独测试 CPU 调度压力时可加 `-CpuMaximum 50`。

在虚拟机内运行同一测试入口，并记录虚拟图形驱动及连接方式。应用进程的内存上限不能代替整机固定内存测试；前者主要覆盖分配失败，不能复现低内存系统的缓存和换页行为。

## 后台分析与结果

`--analysis-audio <音频路径>` 可在播放测量期间启动一次真实后台分析。输入会复制到测试目录，避免与已有歌曲的路径去重规则冲突。它需要完整模型和分析依赖，结果写入测试数据目录。测量结束后会关闭仍在运行的测试任务。结果包含测量结束时的分析阶段；仅处于加载阶段的测量不能代表推理期间的竞争。若分析完成后界面切换到新歌曲，`analysis_replaced_playback` 会标记这一情况，此组数据不能作为同一歌曲稳态播放的对照。

每组测试输出 `result.json`、`renderer.log`、`worker.log` 和前后截图；总目录输出 `summary.json`。主要字段如下：

| 字段 | 含义 |
|---|---|
| `frame_intervals` | 不同播放更新实际呈现的间隔，排除同一更新的重复交换通知 |
| `paint_cost` | 整幅图的绘制耗时；纹理复用期间可能为零次 |
| `presentation_delay` | 播放更新通知到首次呈现的等待时间 |
| `event_loop_delay` | 界面事件循环相对 20 毫秒探针的额外延迟 |
| `interactions` | 跳转、缩放、整首视图的调用耗时、状态更新时间和首次呈现时间 |
| `cpu_percent_one_core` | 界面进程各线程合计 CPU 时间，单个逻辑处理器满载为 100%；不含后台分析进程 |
| `peak_tree_rss_bytes` | 采样得到的测试进程树驻留内存峰值，不等于完整显存或整机内存需求 |
| `cache` | 当前图块数量、图像内存及测量期间的图块生成和界面更新耗时 |

先比较刷新间隔的第 95 百分位、超过 50／100 毫秒的停顿次数和事件循环延迟，再看平均 CPU 与内存。首次生成缓存、缩放和切歌应单独检查。测量开销、窗口遮挡和虚拟机图形路径都会影响结果。

时钟相位只对比软件媒体时钟，不测量扬声器的实际出声延迟。图块分配失败时，界面会释放图像缓存，并在本次运行中使用逐帧绘制；该回退不会改变分析数据。

模拟环境用于比较改动。最低配置和实际流畅程度仍需在目标实体电脑上使用安装包验证。
