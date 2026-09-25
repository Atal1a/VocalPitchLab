"""Expose omitted upstream dependencies for the intentionally scoped separator adapter."""
import argparse
import importlib.metadata as md
import json
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

p=argparse.ArgumentParser();p.add_argument('--app',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
args=p.parse_args()
runtime=args.app/'runtime/Lib/site-packages';vendor=args.app/'vendor/separation-runtime'
distributions=list(md.distributions(path=[str(runtime),str(vendor)]))
installed={canonicalize_name(d.metadata['Name']):d.version for d in distributions}
gaps=[]
for d in distributions:
    for text in d.requires or []:
        requirement=Requirement(text)
        if requirement.marker and not requirement.marker.evaluate({'extra':''}):continue
        actual=installed.get(canonicalize_name(requirement.name))
        if actual is None or (requirement.specifier and actual not in requirement.specifier):
            gaps.append(dict(package=d.metadata['Name'],requires=text,installed=actual))
args.output.parent.mkdir(parents=True,exist_ok=True)
allowed={'diffq-fixed','onnx-weekly','onnx2torch-py313','samplerate'}
unexpected=[g for g in gaps if canonicalize_name(g['package'])!='audio-separator' or
            canonicalize_name(Requirement(g['requires']).name) not in allowed or g['installed'] is not None]
args.output.write_text(json.dumps(dict(gaps=gaps,unexpected=unexpected,scope='Only the fixed RoFormer route is supported; do not claim complete audio-separator feature/dependency support'),indent=2),encoding='utf-8')
print(json.dumps(gaps,indent=2))
raise SystemExit(1 if unexpected else 0)
