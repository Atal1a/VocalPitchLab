# Building on Windows

[简体中文](BUILD.md)

Requirements: Windows x64, Python 3.12, Inno Setup, and the .NET Framework compiler.

- `resources/reproducible/` contains dependency manifests, download URLs, hashes, and patches.
- `rebuild_environment.py` builds a self-contained runtime from prepared dependency files.
- `prepare_delivery.py` assembles application code, libraries, models, and license files.
- `privacy_check.py` checks for internal documentation, compiled caches, and local machine paths. Additional patterns can be supplied in a local JSON file outside the repository.
- `VocalPitchLab.iss` builds the installer for first-time installation and in-place upgrades.
- `prepare_github_assets.py` validates release attachments and generates installation instructions.
- `prepare_source_bundle.py` exports the source archive. It includes maintained unit and installer tests and excludes songs, model weights, user data, and old experimental scripts. The export is checked for local paths before archiving. Use `--deny-file` to add a local privacy checklist.

Build scripts use the project's `work/`, `build/`, and `dist/` directories. Prepare the dependency cache, models, and build tools separately. The source repository excludes these large files. See the [third-party notices](../docs/THIRD_PARTY_NOTICES.md) and [model license review](../docs/MODEL_LICENSE_REVIEW.en.md) for sources and terms.

The GPU environment uses the CUDA 12.8 builds of PyTorch 2.7.1 and torchaudio 2.7.1. See `resources/reproducible/runtime.lock` for the pinned versions. These builds include the `sm_120` kernels needed by RTX 50-series GPUs. `prepare_delivery.py` rejects GPU dependencies that do not match the locked versions. After changing the runtime, rebuild the full installer or explicitly build an update that includes the runtime.

For a new cache, pass the same directory to `lock_artifacts.py --artifacts <cache-dir>` and `rebuild_environment.py --artifacts <cache-dir>`. Keep only the target version of each package. The `wheels/` and `vendor-wheels/` directories correspond to the two lockfiles.

After assembly, use the candidate's bundled Python to check versions, GPU execution, audio operations, and the `sm_120` kernels:

```powershell
<candidate-dir>/runtime/python.exe -I -B tests/package_gpu_check.py <candidate-dir> --output <test-output-dir>/gpu.json
```

GitHub release attachments include the full installer, its volumes, the source archive, installation instructions, and release notes. The single-file full installer is distributed through Quark Drive.

Standard installer builds use grouped solid Ultra64 compression:

```powershell
python installer/package_benchmark.py --stage <app-dir> --output <new-output-dir> --version 1.1.1 --profiles ultra64-solid --removals <assembly-report-dir>/optional-trim.json
```

`build_preview.py` and the sandbox scripts are for local validation. The installers are unsigned.

Use `/PACKAGEVALIDATION=1` with `/DIR=<temporary-dir>` for installation tests. This mode skips shortcuts and uninstall records and leaves normal installation registration untouched. It still checks for the required Microsoft runtime. Omit this parameter for a regular installation.

## Comparing offline installer sizes

Use a separate directory for candidate builds. Keep release installers outside the build output directory. Install `psutil` in the build environment to run the benchmark.

```powershell
python installer/prepare_delivery.py --version 1.1.1 --stage build/delivery-candidate --dependencies work/repro-build/app --base-runtime build/slim-preview/runtime --report-dir work/delivery-reports
python installer/package_benchmark.py --stage build/delivery-candidate --output work/package-comparison --removals work/delivery-reports/optional-trim.json
```

`package_benchmark.py` compares four profiles: `fast`, `max`, `max-solid`, and `ultra64-solid`. Each profile produces a full split installer, installs it into a separate directory, and verifies the installed files by SHA-256. The report lists the attachments, download size, build and installation times, and sampled peak process-tree memory. Memory is sampled every 100 ms.

Use `--profiles ultra64-solid` for regular builds. Omitting `--profiles` tests every profile. After an interruption, use `--resume` with the same inputs. Resuming a completed profile requires a saved attachment record. For older results that lack it, rebuild in a fresh directory. Use `--version` to set the installer version and `--compiler` to select the Inno Setup compiler.

Grouped solid compression puts the application, models, Python dependencies, PyTorch/CUDA, and Qt in separate groups. The Microsoft runtime has its own compression block. Trimming removes only Qt browser modules that passed the reference check. Models and the GPU runtime are kept intact. On an in-place upgrade, the installer removes files from the trim list only if their content hashes match.

For post-installation checks, use a separate data directory and a local audio file:

```powershell
<install-dir>/runtime/python.exe -I -B tests/package_smoke.py <install-dir> <test-data-dir> <test-audio.wav>
```

The check disables Python network connections and exercises analysis, playback, switching between audio sources, task cancellation, themes, the file dialog, and reopening the song library.

Assembly trims confirmed unused Qt browser modules by default. Use `--keep-unused-qt` to assemble a comparison build with those modules included.

Use `--deny-file` to supply a local privacy checklist. After the test installation, the benchmark checks for excluded files and matching content.

## Standalone update packages

```powershell
python installer/build_update.py --baseline <released-app-dir> --stage <new-app-dir> --from-version 1.1.0 --version 1.1.1 --output work/update-1.1.1 --removals <assembly-report-dir>/optional-trim.json
```

Use a verified, released full installation as the baseline. The builder compares SHA-256 hashes file by file. By default it includes only changed application files and resources. To replace dependencies inside the Python runtime, pass `--include-runtime` explicitly. This mode uses split volumes, keeps the installed models, and reserves backup space for files to be replaced or removed. Use a full installer to replace models, third-party separation code, or FFmpeg.

Example of an update that includes the runtime:

```powershell
python installer/build_update.py --baseline <official-1.1.1-app-dir> --stage <1.1.2-app-dir> --from-version 1.1.1 --version 1.1.2 --include-runtime --output <new-update-output-dir>
```

The updater checks the installed launcher version and all files it will reuse. It accepts only the expected baseline or target files and rejects running apps, directory links, and incomplete installations. It backs up files before replacing or removing them and verifies the full target manifest before committing the update. If the update fails or is run again, it restores any pending backup. Recovery also covers old dependency metadata and other files marked for removal. You can rerun an update safely. The user data directory is outside the update.

Full installers and standalone updates share the same installation identity and update the same uninstall record. Use `/PACKAGEVALIDATION=1` with an isolated directory to test the update. Version, integrity, and recovery checks still apply.
