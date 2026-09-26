"""Validate offline installer volumes and prepare local release attachments."""
from pathlib import Path
import hashlib
import json
import argparse

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/VocalPitchLab-1.1.0-windows-x64'


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=OUT)
    OUT = parser.parse_args().directory.resolve()
    setups = list(OUT.glob('*-setup.exe'))
    if len(setups) != 1:
        raise SystemExit('Expected one compiled installer in the release directory')
    setup = setups[0]
    volumes = sorted(OUT.glob(setup.stem + '-*.bin'))
    if not volumes:
        raise SystemExit('No installer volumes found')
    rows = []
    for path in [setup, *volumes]:
        size = path.stat().st_size
        if not 0 < size < 2 * 1024**3:
            raise SystemExit(f'Invalid GitHub asset size: {path.name}: {size}')
        with path.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        rows.append(dict(name=path.name, bytes=size, sha256=digest))
    (OUT / 'SHA256SUMS.txt').write_text(
        ''.join(f"{r['sha256']}  {r['name']}\n" for r in rows), encoding='ascii')
    names = '\n'.join(f"- {r['name']}" for r in rows)
    (OUT / '安装说明.txt').write_text(
        'VocalPitchLab 1.1.0 · Windows x64 离线安装包\n\n'
        '1. 下载下列全部文件，放在同一文件夹；不要改名。\n'
        '2. 双击其中的 Setup 可执行文件，按向导安装。\n'
        '   已安装旧版时可直接覆盖更新，无须先卸载；更新前请关闭软件并备份歌曲库。\n'
        '3. 不要单独打开或解压 .bin 文件，不需要安装 7-Zip。\n'
        '4. 安装过程无需联网下载 Python、模型或 CUDA 运行库。\n\n'
        '缺少微软 VC++ 运行组件时会离线补装，可能需要管理员权限。\n'
        '若提示重启，请保存工作、重启 Windows 后重新运行安装器。\n\n'
        + names + '\n\n'
        '提示缺少文件：确认全部分卷已下载且名称未被浏览器添加 (1) 等后缀。\n'
        '提示文件损坏：用 SHA256SUMS.txt 检查并重新下载对应文件。\n'
        'GPU 加速需要兼容的 NVIDIA 显卡和驱动；未支持的设备使用 CPU，分析会较慢。\n'
        '卸载保留用户歌曲库和分析数据。\n\n'
        '项目代码与第三方模型适用不同许可，详见安装目录中的 THIRD_PARTY_NOTICES.md。\n',
        encoding='utf-8-sig')
    (OUT / 'assets.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
