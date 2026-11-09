# Playback performance tests

[简体中文](PERFORMANCE.md)

Run `tests/package_playback_benchmark.py` on Windows. The benchmark uses Direct3D 11 to render the full interface. By default it generates two four-minute synthetic songs without running any analysis models. Install the project dependencies and `psutil` in the test environment.

Use a fresh output directory for each run. Test songs, the temporary song library, screenshots, and results are stored there. If you supply an existing library, the benchmark reads its analysis results and creates a separate library configuration in the output directory.

## Standard comparison

From the project root, run:

```powershell
python tests/package_playback_benchmark.py --output work/playback-native --seconds 10 --spans 3 20 39 40 0 --scales 1 1.5 2 --repeat 2 --show-window
```

`--spans` sets the visible time range. Use `0` for the whole song. `--scales` sets the target display scale. The results report the actual scale as `effective_dpr`. Keep the test window visible. Covering or minimizing it, or running over Remote Desktop, can affect presentation timing. `--show-window` displays the test window. Without it, the window stays at the bottom of the window stack, which is suitable for functional checks but not for assessing on-screen smoothness.

To use existing analysis results:

```powershell
python tests/package_playback_benchmark.py --output work/playback-song --library library/index.json --song-index 0 --seconds 30 --show-window
```

The selected song and the second song used to test switching tracks must have complete, valid presentation caches. If an older result is missing required data, the benchmark exits without migrating it. The interaction checks seek to 30, 42, and 50 seconds, so use songs longer than one minute.

When comparing source revisions, use the same test script and arguments, and point `--app-root` at the other source tree. Repeat each configuration at least twice and alternate revisions to reduce the effects of run order and temperature changes.

## CPU pressure

```powershell
python tests/package_playback_benchmark.py --output work/playback-cpu --seconds 10 --cpu-cores 2 --cpu-core-budget 0.5 --show-window
```

This limits the test process to two available logical processors and uses a Windows Job Object to cap the process group's average CPU time at about half of one logical processor. The budget is converted using the host's total logical processor count. The actual value is recorded in the results. The limits apply only to the test worker and its child processes.

When the group uses up its CPU quota, Windows pauses it until the next scheduling interval. This stresses scheduling but cannot reproduce a specific older CPU. Restricting the number of cores alone also leaves modern single-core performance unchanged. The script does not currently convert CPU budgets on hosts with more than 64 logical processors.

## Software graphics

```powershell
python tests/package_playback_benchmark.py --output work/playback-warp --renderer warp --seconds 10 --show-window
```

This uses Direct3D 11's WARP software rasterizer while retaining the interface layers and effects. The script checks the rendering log for Microsoft Basic Render Driver. This covers rendering without hardware graphics acceleration and does not represent a specific older integrated GPU.

Use the full interface for comparisons. Qt's software backend omits some shader effects, which can leave parts of the interface out of the measurement.

## Fixed-memory virtual machines

Use either of these Hyper-V test configurations:

| Profile | Virtual processors | Fixed memory |
| --- | --- | --- |
| 8 GB | 4 | 8 GB |
| 4 GB | 2 | 4 GB |

On a host with the Hyper-V management tools, shut down the dedicated test VM and run:

```powershell
./installer/configure_performance_vm.ps1 -VMName 'VPL-Test' -Profile 4gb -WhatIf
./installer/configure_performance_vm.ps1 -VMName 'VPL-Test' -Profile 4gb
```

The script configures the specified existing VM. It does not create a VM, install Windows, or shut down a running system. It disables dynamic memory and sets the CPU limit to 100% by default. Use `-CpuMaximum 50` to test CPU scheduling pressure separately.

Run the same benchmark inside the VM and record the virtual graphics driver and connection method. An app process memory limit mainly tests allocation failures. A fixed-memory VM also exercises system-wide caching and paging under low memory.

## Background analysis and results

`--analysis-audio <audio-path>` starts a real background analysis during the playback measurement. The input is copied into the test directory to avoid the song library's duplicate-path rule. This requires all models and analysis dependencies. Results are written to the test data directory, and any running test analysis is stopped when measurement ends. The result records the analysis stage at that point. A run that only reaches loading does not measure contention during inference. If analysis finishes and the app switches to the new song, `analysis_replaced_playback` marks the run. Exclude such runs when comparing steady playback of the same song.

Each run produces `result.json`, `renderer.log`, `worker.log`, and before-and-after screenshots. The top-level directory contains `summary.json`.

| Field | Meaning |
| --- | --- |
| `frame_intervals` | Time between presented playback updates. Repeated frame swap notifications for the same update are excluded. |
| `paint_cost` | Time to draw the entire chart. There may be no chart paints while textures are reused. |
| `presentation_delay` | Time from a playback update notification until it is first presented. |
| `event_loop_delay` | Extra UI event loop latency measured against a 20 ms probe. |
| `interactions` | Call duration, state update time, and first presentation time for seeking, zooming, and switching to whole-song view. |
| `cpu_percent_one_core` | Combined CPU time of all UI process threads. One fully occupied logical processor is 100%. Background analysis processes are excluded. |
| `peak_tree_rss_bytes` | Sampled peak resident memory for the test process tree. This is separate from total GPU memory and system memory requirements. |
| `cache` | Tile count, image memory, and time spent building tiles and updating the interface during the run. |

Compare the 95th-percentile presentation interval, the number of stalls over 50 and 100 ms, and event loop delay before comparing average CPU and memory use. Check initial cache construction, zooming, and song switching separately. Measurement overhead, covered windows, and VM graphics can affect the results.

Clock phase compares software media clocks. It does not measure the time until sound reaches the speakers. If tile allocation fails, the app releases the image cache and falls back to drawing each frame for the rest of the session. Analysis data is unaffected.

Simulated environments help compare revisions. Verify minimum requirements and actual playback smoothness with an installed build on the target hardware.
