"""Build an offline file update from verified release payloads."""
import argparse
import json
import re
from pathlib import Path, PureWindowsPath

from package_benchmark import ROOT, digest, manifest, measure, verify, write_include


def safe_path(value):
    p = PureWindowsPath(value)
    if (not value or p.is_absolute() or p.drive or any(x in value for x in ':\t\n\r\'"{};')
            or any(x in ('', '.', '..') for x in value.replace('\\', '/').split('/'))
            or any(x.endswith((' ', '.')) or x.upper().split('.')[0] in
                   {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)), *(f'LPT{i}' for i in range(10))}
                   for x in p.parts)):
        raise ValueError('Unsafe release path')
    return p.as_posix()


def plan_update(old, new):
    def index(rows):
        result = {}
        for row in rows:
            path = safe_path(row['path'])
            if path.casefold() in result or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
                raise ValueError('Duplicate path or invalid hash')
            result[path.casefold()] = dict(row, path=path)
        return result
    before, after = index(old), index(new)
    changes = [r for k, r in after.items() if k not in before or r['sha256'] != before[k]['sha256']]
    # A running embedded Python/Qt environment is not upgraded by this patch format.
    # Dependency or model replacements use the full installer instead.
    if any(r['path'].startswith(('runtime/', 'models/', 'vendor/', 'bin/')) for r in changes):
        raise ValueError('Runtime/model replacements require the full installer')
    removed = [r for k, r in before.items() if k not in after]
    checks = [dict(path=r['path'], old=before.get(k, {}).get('sha256', '-'), new=r['sha256'])
              for k, r in after.items()]
    return changes, removed, checks


def validate_removals(removed, approved):
    allowed = {safe_path(r['path']).casefold(): r['sha256'] for r in approved}
    for row in removed:
        path = row['path']
        if path.startswith('models/'):
            raise ValueError('Model removal requires a full installer')
        if path.startswith(('runtime/', 'vendor/', 'bin/')) and allowed.get(path.casefold()) != row['sha256']:
            raise ValueError('Dependency removal requires a matching audited removal manifest')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--stage', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--from-version', required=True)
    p.add_argument('--removals', type=Path, help='Audited optional dependency removal report')
    p.add_argument('--version', required=True)
    p.add_argument('--compiler', type=Path, default=ROOT/'work/installer-tools/inno/ISCC.exe')
    a = p.parse_args()
    for v in (a.from_version, a.version):
        if not re.fullmatch(r'\d+\.\d+\.\d+', v):
            raise SystemExit('Use a three-component version')
    if tuple(map(int, a.version.split('.'))) <= tuple(map(int, a.from_version.split('.'))):
        raise SystemExit('Target version must be newer')
    old_dir, stage, out = a.baseline.resolve(), a.stage.resolve(), a.output.resolve()
    if out.exists() or out.is_relative_to(stage) or out.is_relative_to(old_dir):
        raise SystemExit('Choose a fresh output outside the release payloads')
    old, new = manifest(old_dir), manifest(stage)
    changes, removed, checks = plan_update(old, new)
    validate_removals(removed, json.loads(a.removals.read_text(encoding='utf-8'))['files'] if a.removals else [])
    if not changes or not any(r['path'] == 'VocalPitchLab.exe' for r in changes):
        raise SystemExit('Update requires a versioned launcher')
    out.mkdir(parents=True)
    (out/'target-manifest.json').write_text(json.dumps(new, indent=2), encoding='utf-8')
    (out/'baseline-manifest.json').write_text(json.dumps(old, indent=2), encoding='utf-8')
    (out/'plan.json').write_text(json.dumps(dict(from_version=a.from_version, version=a.version,
        changed=changes, removed=removed, reused_files=len(new)-len(changes)), indent=2), encoding='utf-8')
    (out/'checks.tsv').write_text('\n'.join(f"{r['path']}\t{r['old']}\t{r['new']}" for r in checks), encoding='utf-8-sig')
    (out/'removed.tsv').write_text('\n'.join(f"{r['path']}\t{r['sha256']}" for r in removed), encoding='utf-8-sig')
    (out/'changed.txt').write_text('\n'.join(r['path'] for r in changes), encoding='utf-8-sig')
    write_include(stage, changes, out/'files.iss', True)
    lines = (out/'files.iss').read_text(encoding='utf-8-sig').splitlines()
    ordered = sorted(changes, key=lambda r: (r['component'], r['path']))
    (out/'files.iss').write_text('\n'.join(line +
        f"; AfterInstall: CheckUpdatedFile('{row['path']}', '{row['sha256']}')"
        for line, row in zip(lines, ordered)), encoding='utf-8-sig')
    sources = out/'build-sources'; sources.mkdir()
    for name in ('Update.iss', 'update_guard.iss'):
        (sources/name).write_bytes((ROOT/'installer'/name).read_bytes())
    metrics = measure([str(a.compiler), '/Q', f'/DStageDir={stage}', f'/DUpdateDir={out}',
        f'/DAppVersion={a.version}', f'/DFromVersion={a.from_version}',
        f'/DInstalledSize={sum(r["bytes"] for r in new)}',
        str(ROOT/'installer/Update.iss')], out/'build.log')
    exe = next(out.glob('*.exe'))
    (out/'SHA256SUMS.txt').write_text(f'{digest(exe)}  {exe.name}\n', encoding='utf-8')
    (out/'build-result.json').write_text(json.dumps(dict(build=metrics, bytes=exe.stat().st_size,
        sha256=digest(exe), changed_files=len(changes), reused_files=len(new)-len(changes)), indent=2))
    verify(stage, new); verify(old_dir, old)
    print(json.dumps(dict(file=str(exe), bytes=exe.stat().st_size, changed_files=len(changes))), flush=True)


if __name__ == '__main__':
    main()
