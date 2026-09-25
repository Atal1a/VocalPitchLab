"""Report evidence gaps without marking unverified release requirements complete."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(stage=None):
    checks = []
    def add(name, passed, detail):
        checks.append(dict(name=name, status='pass' if passed else 'blocked', detail=detail))
    for name in ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'resources/pitch-config.json']:
        add(name, (ROOT / name).is_file(), name)
    for model in json.loads((ROOT / 'resources/model-manifest.json').read_text(encoding='utf-8')):
        approved = model['redistribution'] == 'approved'
        add('model-permission:' + model['path'], approved,
            model['license'] + '; metadata review alone is not final distribution clearance')
        if not model.get('archive'):
            path = ROOT / 'models' / model['path']
            digest = None
            if path.is_file():
                with path.open('rb') as f:
                    digest = hashlib.file_digest(f, 'sha256').hexdigest()
            add('model-integrity:' + model['path'], digest == model['sha256'], 'Pinned SHA256')
    evidence_path=ROOT/'outputs/clean-environment-offline/checks.json'
    clean=False
    if evidence_path.is_file():
        evidence=json.loads(evidence_path.read_text(encoding='utf-8'))
        clean=all(evidence.get(k) is True for k in ['clean_dependencies','python_worker_network_blocked','default_analysis','cancellation','settings_persistence'])
        hashes=evidence.get('application_hashes',{})
        clean=clean and bool(hashes) and all((ROOT/name).is_file() and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in hashes.items())
    add('clean-environment-build',clean,'Fixed-pipeline Python environment rebuilt from hash-locked wheels and tested; see outputs/clean-environment-offline. Not a clean Windows certification.')
    for name, detail in {
        'third-party-distribution': 'Qt/FFmpeg and transitive runtime license/source obligations remain under review',
        'clean-windows': 'Offline VC++ prerequisite integration added after Sandbox diagnosed the old preview. User requested no further tests; new integration is not compiled or validated. See WINDOWS_SANDBOX_QA.md',
        'hardware-matrix': 'RTX 4080 tested; physical low-VRAM/low-RAM and other GPU generations not verified',
        'upgrade-migration': 'Existing user library/settings upgrade and rollback not yet verified',
    }.items():
        add(name, False, detail)
    if stage:
        stage = Path(stage)
        for name in ['quick_app.py', 'hardware_check.py', 'resource_policy.py', 'lab.py',
                     'vocal_separator.py', 'rmvpe_adapter.py']:
            packaged = stage / name
            add('stage-current:' + name, packaged.is_file() and packaged.read_bytes() == (ROOT/name).read_bytes(),
                'Compiled previews must be rebuilt only after release preparation is complete')
        leaked = [name for name in ['input','outputs','datasets','library','.git','.venv'] if (stage/name).exists()]
        add('private-data-exclusion', not leaked, ', '.join(leaked) or 'No private data directories found at stage root')
    return dict(ready=all(c['status']=='pass' for c in checks), checks=checks)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage')
    parser.add_argument('--output', default=str(ROOT/'outputs/release-preflight.json'))
    args = parser.parse_args()
    report = check(args.stage)
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Release ready: {report['ready']}; blocked checks: {sum(c['status']=='blocked' for c in report['checks'])}")
    raise SystemExit(0 if report['ready'] else 1)
