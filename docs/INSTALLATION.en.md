# Installation and troubleshooting

[简体中文](INSTALLATION.md)

For VocalPitchLab 1.3.0 on Windows x64. See the [1.3.0 installation guide](releases/INSTALLATION_1.3.0.en.md) for installer, volume, and update filenames.

## Install

1. The CPU edition uses one installer. The NVIDIA edition requires the installer and all its volumes.
2. Keep the NVIDIA installer and volumes in one folder with their original names. Run the `.exe` for your edition and follow the wizard.
3. If a required Microsoft runtime is missing, the installer adds it offline. Windows may request administrator permission. This step is skipped if a sufficiently recent runtime is already installed.
4. If the runtime needs a restart, the wizard prompts after installation finishes. You can restart immediately or later. Start VocalPitchLab after restarting. There is no need to rerun the installer.

After installation, start VocalPitchLab from the Start menu or desktop shortcut, or run `VocalPitchLab.exe` in the installation folder.

A compatible NVIDIA GPU and driver can speed up analysis. The GPU runtime in this release requires a Windows NVIDIA driver version 570.65 or later that supports your GPU model. If GPU acceleration is unavailable, analysis runs on the CPU and takes considerably longer.

## Upgrade

If you have the official 1.2.0 release installed, close VocalPitchLab and run the single-file update to upgrade to the 1.3.0 NVIDIA edition. The update reuses your existing runtime and models. If the wizard cannot detect your installation, select the original folder.

If the update is unavailable for your installation, run the full installer for your edition in the existing folder. To switch between CPU and NVIDIA editions, uninstall the current edition first. The wizard reuses the original installation folder when the same Windows account has a valid installation record.

The full installer replaces the app and runtime while preserving the song library, settings, and analysis results. It also supports first-time installation and repairs missing or modified installation files.

Back up your song library and analysis data in `%LOCALAPPDATA%\VocalPitchLab` before upgrading. If installation is interrupted, run the full installer again to finish or repair the installation.

The source archive is for development. It is optional for regular installation.

## Troubleshooting

- **A volume is missing or a file is damaged.** Check that all files are from the same version and that the browser has not added a suffix such as `(1)` to a filename.
- **The runtime did not finish installing.** Grant administrator permission if Windows requests it. On a managed computer, contact your administrator. Runtime installation logs are in `%LOCALAPPDATA%\VocalPitchLab\installer-logs`. Avoid downloading individual DLLs from unfamiliar sites.
- **The original mix or isolated vocals play without sound.** Enable **Playback compatibility** in Settings. Fully close and reopen the app, then play an existing result. There is no need to run analysis again.
- **Analysis is slow or falls back to the CPU.** Under **Settings → Audio separation**, turn off vocal and harmony separation to analyze pitch directly from the original mix for new imports. Accompaniment may be picked up as vocal pitch. If you use an NVIDIA GPU, check that your driver supports it.
- **Some vocals are missing after separation.** Use the **Harmony separation** control in the playback area to turn it off for the current song. Existing results are reused when available. The first switch may require analysis. The model can attenuate some group vocals and layered high notes.
- **Where data is stored.** The song library and analysis data are stored in `%LOCALAPPDATA%\VocalPitchLab`. Uninstalling preserves this data and leaves the shared Microsoft runtime in place.
