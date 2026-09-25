"""Prepare a small source repository without songs, model weights or local environments."""
from pathlib import Path
import shutil
from application_files import MODULES, VENDOR

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/github-source-1.0.0'

def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if src.is_dir():shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    else:shutil.copy2(src,dst)

def main():
    if OUT.exists():raise SystemExit('Source export already exists; preserve existing work')
    OUT.mkdir(parents=True)
    for name in MODULES:copy(ROOT/(name+'.py'),OUT/(name+'.py'))
    for name in ['assets','qml','installer','resources','note-settings.json','LICENSE',
                 'THIRD_PARTY_NOTICES.md','MODEL_LICENSE_REVIEW.md','INSTALLATION.md',
                 'CHANGELOG.md','DEFAULT_PIPELINE.md','CLEAN_BUILD.md','WINDOWS_SANDBOX_QA.md',
                 'PERFORMANCE_PREVIEW.md','RELEASE_PLAN.md','RELEASE_READINESS.md','requirements.txt']:
        copy(ROOT/name,OUT/name)
    for name in VENDOR:copy(ROOT/'vendor'/name,OUT/'vendor'/name)
    (OUT/'.gitignore').write_text('work/\nbuild/\ndist/\ninput/\noutputs/\nresults/\nmodels/\nlibrary/\ndatasets/\n.venv/\nbin/\n__pycache__/\n*.pyc\n.env\n',encoding='utf-8')
    (OUT/'README.md').write_text('''# VocalPitchLab

Windows 本地人声音高分析软件，结合音高曲线与主要音符块展示演唱旋律。

- 原曲与分离人声试听、循环与标准音比对。
- 固定默认分析流程，可关闭和声分离。
- 本地歌曲库、深浅主题与音域/时间缩放。

目标交付为 Windows x64 离线安装包，入口为 **VocalPitchLab.exe**，不要求用户自行配置 Python 或 CUDA Toolkit。安装方式见 [INSTALLATION.md](INSTALLATION.md)。详细使用说明后续补充。

## 当前状态

1.0.0 已进入交付封装阶段。本轮封装未追加运行测试，未签名；最低硬件配置尚未确定。第三方模型与二进制的分发事项仍在整理，完整安装包不能仅凭本仓库许可证视为获得全部第三方授权。

## 许可

项目自有代码采用 **GPL-3.0-only**。第三方代码、模型和运行库保留各自条款，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [MODEL_LICENSE_REVIEW.md](MODEL_LICENSE_REVIEW.md)。仓库不包含歌曲、用户数据、模型权重或本机运行环境。
''',encoding='utf-8')
    archive=ROOT/'dist/VocalPitchLab-1.0.0-source'
    archive.parent.mkdir(exist_ok=True)
    shutil.make_archive(str(archive),'zip',OUT)
    print(OUT)

if __name__=='__main__':main()
