# VocalPitchLab 1.1.2

[简体中文](RELEASE_NOTES_1.1.2.md)

## What's new

- Updated the GPU runtime to support RTX 50-series GPUs and improved GPU self-check messages.
- Added **Playback compatibility** to address cases where the original mix or isolated vocals play without sound.
- Hovering over a piano note label highlights its pitch row and the visible note blocks at that pitch. The song list layout also has more room around the scrollbar.
- Fixed analysis failures that could occur with long user directory paths.
- If a runtime component requires a restart, the installer completes installation and then prompts you to restart. There is no need to run it again.

## Installation and upgrades

Use the full installer for a new installation or an upgrade. For the [GitHub split installer](https://github.com/Atal1a/VocalPitchLab/releases/tag/v1.1.2), put the setup executable and all accompanying `.bin` volumes in the same folder. Run the [Quark single-file installer](https://pan.quark.cn/s/fec1530accea) directly.

To upgrade, close the app and install into the existing folder. There is no need to uninstall first. Your song library, settings, and analysis results are preserved. Back up `%LOCALAPPDATA%\VocalPitchLab` before upgrading.

If the original mix or isolated vocals play without sound, enable **Playback compatibility** in Settings, then fully close and reopen the app. There is no need to analyze the song again.

## Compatibility

GPU acceleration requires an NVIDIA driver that supports your GPU. This release requires driver version 570.65 or later. No separate Python or CUDA Toolkit setup is required.

The installers are unsigned. The project code is licensed under GPL-3.0-only. See [Third-party notices](THIRD_PARTY_NOTICES.md) for component and model licenses.
