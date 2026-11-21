"""Analyze one song through the fixed, cached production pipeline."""
import argparse
import json
import time
from pathlib import Path
from vocalpitchlab.runtime.paths import DATA_ROOT, prepare
from vocalpitchlab.analysis.analysis_cache import atomic_json


def execute(file,result_file=None,standalone=True,separation='mel_bs',*,recording=None,stems_only=False,job_id=None):
    prepare()
    def progress(value, message):
        print('VPL_EVENT '+json.dumps(dict(progress=value, message=message), ensure_ascii=False), flush=True)
    def ready(stems):
        print('VPL_STEMS_READY '+json.dumps(dict(id=job_id, stems=stems), ensure_ascii=False), flush=True)
    from vocalpitchlab.analysis.production_pipeline import analyze
    song = analyze(Path(file), separation, progress, recording=recording, stems_only=stems_only, stems_ready=ready)
    if stems_only:
        if result_file:
            atomic_json(Path(result_file), dict(stems=song))
        progress(100, '音轨已就绪')
        return
    previous = sorted((DATA_ROOT/'results').glob('rmvpe-*/index.json'))
    old = json.loads(previous[-1].read_text(encoding='utf-8')) if previous and not standalone else dict(songs=[])
    prefix = 'analysis-' if standalone else 'rmvpe-'
    folder = DATA_ROOT/'results'/(time.strftime(prefix+'%Y%m%d-%H%M%S')+'-'+str(time.time_ns())[-6:])
    folder.mkdir()
    old['songs'] = [s for s in old['songs'] if s['name'] != song['name']] + [song]
    old['created'] = song['created']
    atomic_json(folder/'resource-metrics.json', song['stage_cache'])
    atomic_json(folder/'index.json', old)
    if result_file:
        atomic_json(Path(result_file), dict(song=song, index=str(folder/'index.json')))
    progress(100, '分析完成，结果已保存')
    print(json.dumps(dict(index=str(folder/'index.json'), song=song['name'], duration=song['duration']), ensure_ascii=False), flush=True)


def main():
    from vocalpitchlab.analysis.production_pipeline import SEPARATION_MODES
    p = argparse.ArgumentParser()
    p.add_argument('file'); p.add_argument('--result-file'); p.add_argument('--standalone', action='store_true')
    p.add_argument('--separation', choices=SEPARATION_MODES, default='mel_bs')
    p.add_argument('--stems-only', action='store_true')
    p.add_argument('--recording', type=json.loads)
    args = p.parse_args()
    execute(args.file,args.result_file,args.standalone,args.separation,recording=args.recording,stems_only=args.stems_only)


if __name__ == '__main__':
    main()
