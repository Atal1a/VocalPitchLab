"""Validate GitHub release attachments and generate installation instructions."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRECTORY = ROOT / 'dist/VocalPitchLab-1.3.0'
SETUP = re.compile(r'VocalPitchLab-(\d+\.\d+\.\d+)-windows-x64(-cpu-offline|-offline)?-setup\.exe')


def volumes(attachments, installer, *, required=False):
    pattern = re.compile(re.escape(installer.stem) + r'-(\d+)\.bin')
    numbered = sorted(
        (int(match[1]), path) for path in attachments if (match := pattern.fullmatch(path.name))
    )
    if required and not numbered:
        raise SystemExit(f'No volumes for {installer.name}')
    if [number for number, _ in numbered] != list(range(1, len(numbered) + 1)):
        raise SystemExit(f'Volume numbering is incomplete for {installer.name}')
    return [path for _, path in numbered]


def prepare(directory):
    attachments = sorted(path for path in directory.rglob('VocalPitchLab-*') if path.is_file())
    names = [path.name.casefold() for path in attachments]
    if len(names) != len(set(names)):
        raise SystemExit('Duplicate release attachment names')
    setups = [(path, match) for path in attachments if (match := SETUP.fullmatch(path.name))]
    versions = {match[1] for _, match in setups}
    if len(versions) != 1:
        raise SystemExit('Expected compiled installers for one release version')
    version = versions.pop()
    prefix = f'VocalPitchLab-{version}-windows-x64'
    update_name = re.compile(re.escape(prefix) + r'-update-from-(\d+\.\d+\.\d+)\.exe')
    lines = [f'VocalPitchLab {version} · Windows x64', '', '首次安装或修复', '']
    assets = []

    for setup, match in setups:
        split = match[2] is None
        edition = 'CPU' if match[2] == '-cpu-offline' else 'NVIDIA'
        parts = volumes(attachments, setup, required=True) if split else []
        assets.extend([setup, *parts])
        lines.extend((f'{edition} 版（{"分卷" if split else "单文件"}）', f'- {setup.name}'))
        lines.extend(f'- {part.name}' for part in parts)
        lines.append('')

    if any(match[2] is None for _, match in setups):
        lines.append('将 NVIDIA 安装程序和配套分卷放在同一文件夹，保留原文件名。')
    lines.append('运行所选版本的安装程序。修复已有安装时，先关闭软件再覆盖到原目录。')
    if any(match[2] == '-cpu-offline' for _, match in setups):
        lines.append('切换 CPU 与 NVIDIA 版时，先卸载现有版本。卸载会保留歌曲库、设置和分析结果。')
    lines.append('安装可离线进行。若向导提示重启，重启后再打开软件。')

    updates = [(path, match) for path in attachments if (match := update_name.fullmatch(path.name))]
    for update, match in updates:
        parts = volumes(attachments, update)
        assets.extend([update, *parts])
        lines.extend(('', f'从 {match[1]} 升级', '', f'- {update.name}'))
        lines.extend(f'- {part.name}' for part in parts)
        if parts:
            lines.append('把更新程序和配套分卷放在同一文件夹。')
        lines.append('关闭软件后运行更新程序。若找不到原安装目录，请在向导中选择该目录。')
    if updates:
        lines.append('如果版本不适用，或安装文件缺失、被修改，请用对应的完整安装包。')

    source_name = f'VocalPitchLab-{version}-source.zip'
    assets.extend(path for path in attachments if path.name == source_name)
    rows = []
    for path in assets:
        size = path.stat().st_size
        if not 0 < size < 2 * 1024**3:
            raise SystemExit(f'Invalid GitHub asset size: {path.name}: {size}')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        rows.append(dict(name=path.name, path=path.relative_to(directory).as_posix(), bytes=size, sha256=digest))

    (directory / '安装说明.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8-sig')
    (directory / 'assets.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIRECTORY)
    print(json.dumps(prepare(parser.parse_args().directory.resolve()), indent=2))


if __name__ == '__main__':
    main()
