# Development

[简体中文](DEVELOPMENT.md)

Use Python 3.12 and the dependencies in `requirements.txt`. From the project root, run:

```powershell
python main.py
```

You can also run `python -m vocalpitchlab`. See `resources/` for model and configuration files, and the [Windows build guide](../installer/BUILD.en.md) for packaging.

## Project layout

- `vocalpitchlab/ui/` — interface, chart rendering, and interaction.
- `vocalpitchlab/analysis/` — analysis pipeline, pitch and note detection, caching, and background tasks.
- `vocalpitchlab/audio/` — audio input, vocal separation, model reuse, and piano preview.
- `vocalpitchlab/runtime/` — paths, hardware detection, resource policies, and model file management.
- `qml/` — interface components and themes.
- `installer/` — environment setup, installer builds, and release checks.
- `tests/` — checks for project layout, entry points, background processes, installers, privacy filtering, and updates.
- `vendor/` — third-party code with its original attribution and licenses.

Use `VPL_DATA_DIR` and `VPL_MODEL_DIR` to set the data and model directories. Resource paths are resolved relative to the project or installation directory, regardless of the current working directory.

To analyze audio in the background, run `python main.py --analyze <audio-path>`. For batch jobs, `--analysis-worker` accepts newline-delimited JSON on standard input.

See the [playback performance guide](PERFORMANCE.en.md) for chart benchmarks, CPU limits, WARP, and fixed-memory virtual machines.
