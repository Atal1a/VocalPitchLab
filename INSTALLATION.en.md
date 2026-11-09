# Installation and troubleshooting

[简体中文](INSTALLATION.md)

For the VocalPitchLab 1.2.0 full offline installers for Windows x64.

## Install

1. For the split installer, use `VocalPitchLab-1.2.0-windows-x64-setup.exe` and all accompanying `.bin` volumes. For the single-file installer, use `VocalPitchLab-1.2.0-windows-x64-offline-setup.exe`.
2. For the split installer, put all files from the same version in one folder and keep their original names. Run the corresponding `.exe` and follow the wizard. The volumes do not need to be extracted separately. No separate Python or CUDA Toolkit setup is required.
3. If a required Microsoft runtime is missing, the installer adds it offline. Windows may request administrator permission. This step is skipped if a sufficiently recent runtime is already installed.
4. If the runtime needs a restart, the wizard prompts after installation finishes. You can restart immediately or later. Start VocalPitchLab after restarting. There is no need to rerun the installer.

After installation, start VocalPitchLab from the Start menu or desktop shortcut, or run `VocalPitchLab.exe` in the installation folder.

A compatible NVIDIA GPU and driver can speed up analysis. The GPU runtime in this release requires a Windows NVIDIA driver version 570.65 or later that supports your GPU model. If GPU acceleration is unavailable, analysis runs on the CPU and takes considerably longer.

## Upgrade

If you have the official 1.1.2 release installed, close VocalPitchLab and run `VocalPitchLab-1.2.0-windows-x64-update-from-1.1.2.exe`. The update reuses your existing runtime and models. If the wizard cannot detect your installation, select the original folder manually. Use a full installer for other versions, or if files in your existing installation are missing or modified.

You can use either full installer to upgrade without uninstalling first. Close VocalPitchLab and run the installer. If you use the same Windows account and the previous installation record is valid, the wizard reuses the original installation folder. If the folder was moved or the wizard cannot detect it, select the existing folder manually.

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
