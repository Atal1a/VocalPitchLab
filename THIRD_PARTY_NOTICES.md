# Third-party assets and release status

Original VocalPitchLab code is licensed under GPL-3.0-only (GNU GPL version 3, not an automatic grant of later versions). Copyright (c) 2026 VocalPitchLab contributors. The full text is in LICENSE. Third-party code, binaries, weights, datasets and music retain their applicable licenses and notices. This choice does not resolve compatibility or redistribution requirements for the complete bundle; noncommercial model terms are not added to the GPL itself.

| Component | Source / status |
|---|---|
| RVC RMVPE code | MIT; full text and pinned provenance in vendor/LICENSE-RVC and vendor/provenance.json |
| RMVPE weights | Metadata says MIT, but the pinned publisher terms also contain research-only wording applying to package code/files; scope requires clarification. Saved in resources/license-evidence/rmvpe-publisher-terms.txt |
| Kim MelBand RoFormer weights | Author repository revision ac9b0614ab3cd7f77219e18ba494dfd93956c348 says MIT; https://huggingface.co/KimberleyJSN/melbandroformer |
| BS frazer/becruily weights | No explicit model license found; public bundle blocked pending clarification: https://huggingface.co/becruily/bs-roformer-karaoke |
| GAME | Code MIT; GAME 1.0 weights explicitly CC BY-NC-SA 4.0 at https://github.com/openvpi/GAME/releases/tag/v1.0.0. v1.0.3 ONNX exports derive from those weights. Attribution/noncommercial/share-alike conditions apply as relevant; not unrestricted MIT assets |
| PySide6 / Qt | Bundled dependency notices retained; LGPL/GPL/commercial terms vary by component. Shared binaries retained; full distribution compliance review pending |
| audio-separator and dependencies | Bundled distribution metadata/license files retained; local weights_only loader modification retained. Full source/notice review pending |
| FFmpeg | Gyan 2026-07-02 git-95a888b9ca build enables GPL and version3; configuration saved in resources/license-evidence/ffmpeg-build.txt. Matching source/build inputs and notices still required before public distribution |
| Python / PyTorch / ONNX Runtime / other dependencies | Original runtime/license and dist-info files retained; build generates THIRD_PARTY_INVENTORY.json. Inventory is not a completed legal audit |
| Microsoft Visual C++ v14 Redistributable x64 | Original Microsoft installer 14.51.36247.0; source, hash and signature provenance in resources/vc-redist.json. Separate Microsoft license, not project GPL. Used as an offline installer prerequisite; existing shared runtime is never removed by the application uninstaller. Publisher redistribution eligibility remains part of third-party review: https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files |

No songs, listening excerpts, datasets, user library or private credentials belong in the installer. Local preview build uses an allowlist for application files and excludes research outputs. The local preview includes unreviewed models solely for the owner's installation tests; do not publish that artifact.

Open questions are recorded rather than treating download availability as redistribution permission. No publisher has been contacted or granted additional permissions by this work.

Detailed review dated 2026-09-25: MODEL_LICENSE_REVIEW.md. Earlier metadata-only assessments are superseded by that review. No new permission was inferred from another application's use of the same model.
