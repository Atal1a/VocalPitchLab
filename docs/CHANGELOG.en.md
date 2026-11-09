# Changelog

[简体中文](CHANGELOG.md)

## 1.2.0

- Added an English interface that can be enabled immediately in Settings.
- Added independent controls for vocal separation and harmony separation. Both are enabled by default. With both off, pitch is analyzed directly from the original mix.
- Added WAV export for separated tracks. Available tracks depend on the separation settings used for analysis.
- Made piano previews more responsive, added hold-to-sustain and release, and raised the maximum preview volume.
- Reduced redundant pitch chart redraws during playback and added the **Reduce graphics load** setting.
- Improved the queue display during batch imports and fixed a message that failed to reappear when unsupported files were dropped repeatedly.

## 1.1.2

- Updated the GPU runtime with support for the Blackwell architecture used by RTX 50-series GPUs.
- GPU self-check messages now distinguish runtime incompatibility, older drivers, and insufficient video memory, with guidance for each case.
- Added **Playback compatibility**, which uses Windows media components. Restart the app after changing this setting.
- Hovering over a piano note label highlights its pitch row and all visible note blocks at that pitch.
- Adjusted the spacing around the song list scrollbar.
- Fixed analysis failures caused by long temporary audio paths when the user data directory path was long.
- If a runtime component requires a restart, app installation finishes first and prompts for a restart at the end. The installer does not need to be run again.

## 1.1.1

- Reduced the download size of the full offline installer.
- Added a standalone update package for 1.1.0 that reuses the installed runtime and models.
- Added pre-update file checks and recovery after an interrupted update.

## 1.1.0

### Performance

- Shortened overall analysis time.
- Reduced redundant loading when importing songs in succession.
- Improved analysis stability when system or GPU memory is low.

### Features and usability

- Improved note block generation and display, reducing fragmented and missed notes.
- Added per-song harmony separation controls.
- Added automatic pitch-range fitting and improved chart navigation and zoom.
- Improved playback controls and pitch indicators.
- Made the interface more consistent and simplified settings and help text.

## 1.0.0

- Local vocal pitch analysis on Windows, with a continuous pitch curve and main note blocks showing the sung melody.
- Vocal separation, original and isolated vocal playback, loop playback, and piano pitches for comparison.
- Song library management, task cancellation, saved view positions, and light and dark themes.
- Full offline installer.
