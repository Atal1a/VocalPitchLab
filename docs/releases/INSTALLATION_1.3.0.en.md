# Install VocalPitchLab 1.3.0

[简体中文](INSTALLATION_1.3.0.md)

Both Windows x64 editions can install and analyze audio offline.

| Edition | Installer files |
| --- | --- |
| CPU | `VocalPitchLab-1.3.0-windows-x64-cpu-offline-setup.exe` |
| NVIDIA | `VocalPitchLab-1.3.0-windows-x64-setup.exe` and its `-1.bin`, `-2.bin`, and `-3.bin` volumes |

Use the CPU edition on computers without a compatible NVIDIA GPU. The NVIDIA edition can accelerate analysis. Its CUDA 12.8 runtime requires Windows NVIDIA driver 570.65 or later and support for your GPU.

Keep the NVIDIA installer and all three volumes in the same folder with their original names. Run the `.exe` for your edition and follow the wizard. If prompted to restart, do so before opening the app.

## Upgrading from 1.2.0

Existing 1.2.0 Windows x64 installations can use `VocalPitchLab-1.3.0-windows-x64-update-from-1.2.0.exe` to upgrade to the 1.3.0 NVIDIA edition. Close VocalPitchLab before running the update. Select the existing installation folder if the wizard cannot find it. The update reuses the runtime and models and keeps the library, settings, and analysis results.

To upgrade from another version to the NVIDIA edition or to repair missing or modified installation files, run the full NVIDIA installer in the existing installation folder.

To repair the CPU edition, run the full CPU installer in the existing installation folder.

## Switching editions

Uninstall the current edition in Windows Settings, then install the CPU or NVIDIA edition. Uninstalling keeps the library, settings, and analysis results under `%LOCALAPPDATA%\VocalPitchLab`.
