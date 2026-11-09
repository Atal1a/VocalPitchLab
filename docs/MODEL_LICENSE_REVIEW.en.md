# License review for default models and distribution

[简体中文](MODEL_LICENSE_REVIEW.md)

Reviewed on September 25, 2026. This review examines the evidence for distribution. The analysis pipeline was outside its scope. This is an engineering release review and does not guarantee that every possible right has been cleared.

## Main findings

| Asset | Evidence found | Release handling |
| --- | --- | --- |
| Kim MelBand RoFormer | The model card at the pinned revision explicitly states MIT. No separate license file was found. | Keep the model card, source, and weight hashes. Complete the review after preparing the MIT notice. |
| BS frazer/becruily | The pinned revision's file list has no README or license, and the current model page has no model card. | Explicit distribution permission is missing. Ask the rights holder for clarification. Availability from other sources does not establish permission. |
| GAME small ONNX | The code is MIT. The 1.0.0 model release explicitly states CC BY-NC-SA 4.0, and the 1.0.3 release notes say its exports come from GAME 1.0. | The model license is documented. Follow attribution, noncommercial, and applicable ShareAlike requirements. Commercial use requires separate permission. |
| RMVPE distributed by RVC | The model card says MIT. The pinned publisher terms also say the software is for research use only and refer to code and files in the package. | The scope of the terms is ambiguous. The MIT label alone is insufficient for unconditional approval. Clarify whether the restriction applies to distribution of `rmvpe.pt` and general pitch analysis use. |

GAME's noncommercial restriction applies to the licensed model. The project's own code remains under its separate GPL-3.0-only license, which does not remove model terms. Free public distribution alone does not establish that a particular commercial use complies. The combined distribution still needs a compatibility review.

## Evidence on file

`resources/license-evidence/sources.json` records source URLs, collection dates, and SHA-256 hashes.

- `bs-pinned.json` — API metadata and file list at the pinned BS revision.
- `kim-pinned.json` and `rmvpe-pinned.json` — metadata at the pinned revisions.
- `rmvpe-publisher-terms.txt` — the full license and terms file from the RMVPE publisher repository.
- `game-releases.json` — release notes documenting the 1.0.0 model license and the origin of the 1.0.3 exports.
- `game-v1.0.3-LICENSE.txt` — the license for GAME code. The model weights have separate terms.
- `ffmpeg-build.txt` — the current FFmpeg version and build options.

## Separate review of third-party runtimes

- The current FFmpeg build uses `--enable-gpl` and `--enable-version3`. Provide the source, build information, and third-party notices for the matching binary, or choose a build with complete source information and run format regression tests. The binary was unchanged during this review.
- For PySide6 and Qt, review the modules and bundled third-party components actually distributed. Keep the applicable licenses and meet shared-library replacement requirements. The `dist-info` files cover only part of these obligations.
- PyTorch/CUDA, Python, ONNX Runtime, CREPE, and other dependencies still need component-by-component notices and source records. This review covers four models.

## Next steps

Keep each component's original license and document known terms and gaps. Clarify the license scope for BS and RMVPE. Follow the GAME model's attribution, noncommercial, and ShareAlike terms.

## Official sources

- [BS RoFormer karaoke model](https://huggingface.co/becruily/bs-roformer-karaoke)
- [Kim MelBand RoFormer](https://huggingface.co/KimberleyJSN/melbandroformer)
- [RVC VoiceConversionWebUI](https://huggingface.co/lj1995/VoiceConversionWebUI)
- [GAME 1.0.0 release](https://github.com/openvpi/GAME/releases/tag/v1.0.0)
- [GAME 1.0.3 release](https://github.com/openvpi/GAME/releases/tag/v1.0.3)
- [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
- [FFmpeg legal information](https://www.ffmpeg.org/legal.html)
- [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html)
