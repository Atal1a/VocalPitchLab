# 默认模型与分发许可核查

核查日期：2026-09-25。仅核查发布依据，不更改现有分析流程。该记录是工程发布审核，不是对所有潜在权利的法律保证。

## 核心结论

| 资产 | 已找到的依据 | 当前发布处理 |
|---|---|---|
| Kim MelBand RoFormer | 固定版本模型卡明确标注 MIT；未发现单独 LICENSE 文件 | 保留模型卡、来源、权重哈希；整理 MIT 通知后完成审核 |
| BS frazer/becruily | 固定版本文件清单没有 README/许可，当前模型页也无模型卡 | 缺少明确分发授权；需要权利人澄清，不能因为别人提供下载就视为获准 |
| GAME small ONNX | GAME 代码 MIT，但 1.0.0 模型发布明确 CC BY-NC-SA 4.0；1.0.3 发布说明明确由 GAME 1.0 导出 | 许可已找到，不再标为完全未知；按非商业条件、署名及适用的相同方式共享义务处理。商业用途需要另行许可 |
| RVC 分发的 RMVPE | 模型卡标 MIT，但固定版本《使用需遵守的协议-LICENSE.txt》还写有“本软件仅供研究使用”，并提及包内代码和文件 | 许可文本存在范围歧义，不能只依据 MIT 标签作无条件批准；需澄清该条款是否适用于 rmvpe.pt 的分发和一般音高分析用途 |

GAME 的非商业限制针对所许可的模型，不能直接推论自有代码必须全部改成 CC 许可；同样，自有代码使用 GPL-3.0-only 也不能消除模型条款。免费公开发布不自动证明任何具体商业场景合规。自有代码改为 GPL 后，完整组合的许可兼容性仍需核对，不能直接断言所有组件可一并分发。

## 已保存的证据

resources/license-evidence/sources.json 记录来源 URL、采集日期和 SHA256。

- bs-pinned.json：BS 固定版本 API 元数据及文件清单。
- kim-pinned.json、rmvpe-pinned.json：固定版本元数据。
- rmvpe-publisher-terms.txt：RMVPE 发布仓库的完整许可/使用条款文件。
- game-releases.json：发布说明，包括 1.0.0 的模型许可与 1.0.3 导出来源链。
- game-v1.0.3-LICENSE.txt：GAME 代码许可，不能冒充权重许可。
- ffmpeg-build.txt：当前 FFmpeg 版本与编译选项。

## 第三方运行库的独立工作

- FFmpeg 当前启用 --enable-gpl、--enable-version3，不能笼统当作 LGPL 构建。需补齐对应二进制版本的源码、构建信息和第三方依赖通知；或选取来源资料完整的替代构建并做格式回归测试。没有擅自更换二进制。
- PySide6/Qt 要逐个核对实际分发模块和附带第三方组件，保留适用许可及可替换共享库条件；仅保留 dist-info 不等于完成全部分发义务。
- PyTorch/CUDA、Python、ONNX Runtime、CREPE 与其他依赖仍需完成逐项通知和来源清单。此次四个模型核查不冒充全依赖合规审核完成。

## 下一项具体工作

按用户决定，暂不联系作者；各组件保留原许可，在仓库中公开记录已知条款和缺口。BS 和 RMVPE 的澄清项保留待办，不继续准备或发送联系消息。GAME 已有条件许可，可继续整理署名与许可文本，但当前不把整包标为可无限制商用。

与此同时可以推进独立的干净构建，不必等待作者答复才做技术准备。公开发布仍须解决这些实际缺口。未重新编译或上传安装包。

## 官方来源

- https://huggingface.co/becruily/bs-roformer-karaoke
- https://huggingface.co/KimberleyJSN/melbandroformer
- https://huggingface.co/lj1995/VoiceConversionWebUI
- https://github.com/openvpi/GAME/releases/tag/v1.0.0
- https://github.com/openvpi/GAME/releases/tag/v1.0.3
- https://creativecommons.org/licenses/by-nc-sa/4.0/
- https://www.ffmpeg.org/legal.html
- https://doc.qt.io/qtforpython-6/licenses.html
