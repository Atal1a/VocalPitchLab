# VocalPitchLab 1.2.0

[简体中文](RELEASE_NOTES_1.2.0.md)

## Performance improvements

- **Less drawing work during playback.** The pitch chart reuses rendered sections of the curve and note blocks. The playhead updates independently, so fewer parts of the chart need to be redrawn. To turn off sidebar blur and panel shadows, enable **Reduce graphics load** under **Settings → Appearance**.
- **Run only the separation steps you need.** Under **Settings → Audio separation**, you can turn **Vocal separation** and **Harmony separation** on or off independently. Both are enabled by default. If you only need to isolate vocals from the accompaniment, turn off harmony separation to skip that step. Turning both off analyzes pitch directly from the original mix for new imports. This can save time, though accompaniment may be picked up as vocal pitch.

## New and improved features

- **Export separated tracks.** After analysis, select **Export tracks** in the playback area to save the available tracks as WAV files. With both separation steps enabled, you can export lead vocals, instrumental, and backing vocals as separate tracks. With only vocal separation enabled, you can export vocals and instrumental. With only harmony separation enabled, you can export lead vocals and a combined backing-vocals-and-instrumental track.
- **Improved piano preview.** Preloaded samples play sooner when you click a note label to the left of the chart. Hold the label to sustain the note and release it to let the note fade. The maximum preview volume is also higher, making it easier to compare piano notes with the original song.
- **English interface.** Choose **English** under **Settings → Language**. The song library, playback controls, charts, and analysis messages switch immediately. The app remembers your choice.

This release also fixes several issues with batch imports and interface messages.

## Installation and upgrades

Use a full installer for Windows x64. For the split installer, put the setup executable and all accompanying `.bin` files in the same folder. For the single-file installer, run the setup executable directly.

If you have the official 1.1.2 release, you can use the standalone update to reuse your installed runtime and models. You can also close the app and run a full installer in the original folder. Both methods preserve your song library, settings, and analysis results. See the [installation guide](INSTALLATION.en.md).
