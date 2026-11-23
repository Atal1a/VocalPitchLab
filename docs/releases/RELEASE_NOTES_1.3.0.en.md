# VocalPitchLab 1.3.0

[简体中文](RELEASE_NOTES_1.3.0.md)

## New features

- Export tracks as soon as separation finishes while pitch and note analysis continues in the background. Choose **Tracks only** on import to separate first and run full analysis from the task later.

## Bug fixes

- Changing harmony separation uses the recording saved in the library. Reimport the same recording to repair damaged analysis and keep its library entry and saved view.
- Fixed playback stopping when a loop ends at the end of the song.
- Fixed duplicate entries after reimporting and undoing removal, and incorrect Shift selection counts after batch removal.

## Performance improvements

- Faster batch queuing and song reopening, with less disk I/O when saving playback position.
- Separation removes temporary audio after use, reducing disk usage.

## Installation and upgrades

Added a CPU offline installer. The NVIDIA offline installer remains available for GPU acceleration. Existing 1.2.0 Windows x64 installations can upgrade to the NVIDIA edition with a single-file update. See the [installation guide](INSTALLATION_1.3.0.en.md).

- The full CPU installer can repair an existing CPU installation with a missing edition marker.
- If an update fails and rolls back, the Windows installed apps list shows the previous version again.
