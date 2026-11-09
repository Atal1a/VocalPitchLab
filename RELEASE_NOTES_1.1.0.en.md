# VocalPitchLab 1.1.0

[简体中文](RELEASE_NOTES_1.1.0.md)

## Performance improvements

- Shortened overall analysis time.
- Reduced redundant loading when importing songs in succession.
- Improved analysis stability when system or GPU memory is low.

## Features and usability

- Improved note block generation and display, reducing fragmented and missed notes.
- Added per-song harmony separation controls.
- Added automatic pitch-range fitting and improved chart navigation and zoom.
- Improved playback controls and pitch indicators.
- Made the interface more consistent and simplified settings and help text.

## Installation and upgrades

Download `setup.exe` and all `.bin` volumes for this version. Put them in one folder and run the installer. For an upgrade, close the app and install into the existing folder. There is no need to uninstall first. Back up your song library before upgrading.

The installer includes Python, the models, and the CUDA runtime. No separate setup is required. GPU acceleration requires a compatible NVIDIA GPU and driver.

The project code is licensed under GPL-3.0-only. Third-party components and models retain their respective licenses. See [Third-party notices](THIRD_PARTY_NOTICES.md).
