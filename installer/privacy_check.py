"""Reject local-only files and source-machine paths before distribution."""
import argparse
import json
from pathlib import Path

EXCLUDED = {'__pycache__', '.git', '.venv', '.env', 'BRAND.md',
            'PERFORMANCE_PREVIEW.md', 'CLEAN_BUILD.md', 'RELEASE_PLAN.md',
            'RELEASE_READINESS.md', 'WINDOWS_SANDBOX_QA.md', 'RELEASE_1_1_QA.md',
            'LOCAL_REFINE' + 'MENT_QA.md', 'PIPELINE_REFINE' + 'MENT.md',
            'audio-separator.exe', 'audio-separator-remote.exe'}
TEXT_SUFFIXES = {'.py', '.md', '.txt', '.json', '.yaml', '.yml', '.ini',
                 '.cfg', '.toml', '.ps1', '.cmd', '.iss', '.cs', '.svg', '.html'}


def ignore_private_files(directory, names):
    return [name for name in names if name in EXCLUDED or name.endswith(('.pyc', '.pyo', '.pdb'))]


def inspect(stage, forbidden=()):
    stage = Path(stage).resolve()
    findings = []
    files = 0
    for path in stage.rglob('*'):
        if not path.is_file():
            continue
        files += 1
        relative = path.relative_to(stage)
        if any(part in EXCLUDED for part in relative.parts) or path.suffix in {'.pyc', '.pyo', '.pdb'}:
            findings.append({'path': relative.as_posix(), 'reason': 'private file or build cache'})
        if path.suffix.lower() in TEXT_SUFFIXES:
            content = path.read_text(encoding='utf-8', errors='replace').lower().replace('\\', '/')
            for text in forbidden:
                if text and text.lower().replace('\\', '/') in content:
                    findings.append({'path': relative.as_posix(), 'reason': 'private identifier or build path'})
                    break
    return {'files_checked': files, 'findings': findings, 'passed': not findings}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', type=Path)
    parser.add_argument('--deny-file', type=Path, help='Local JSON list of private strings; never publish this file')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    forbidden = json.loads(args.deny_file.read_text(encoding='utf-8')) if args.deny_file else []
    report = inspect(args.stage, forbidden)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
