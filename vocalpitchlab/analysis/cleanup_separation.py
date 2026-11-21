"""List or remove unused separator outputs from a copy of a data directory."""
import argparse
import json
from pathlib import Path

from vocalpitchlab.analysis.analysis_cache import digest_file


def referenced_outputs(value, folder, data):
    if isinstance(value, dict):
        value = value.values()
    elif isinstance(value, str):
        path = Path(value)
        if path.name.lower() == 'v.wav':
            yield (folder / path).resolve()
            # Copied libraries may still use absolute paths from the original location.
            parts = [part.lower() for part in path.parts]
            for index in range(len(parts) - 1):
                if parts[index:index + 2] == ['results', 'stages']:
                    yield data.joinpath(*path.parts[index:]).resolve()
        return
    elif not isinstance(value, list):
        return
    for item in value:
        yield from referenced_outputs(item, folder, data)


def cleanup(data, *, apply=False):
    data = Path(data).resolve(strict=True)
    stages = data/'results'/'stages'
    if not stages.is_dir():
        raise ValueError('Expected a data directory copy containing results/stages')
    manifests = {path: json.loads(path.read_text(encoding='utf-8'))
                 for path in stages.glob('*/*/complete.json')}
    sources = [*(data/'library').rglob('index.json'), *(data/'library').rglob('*-result.json'),
               *(data/'results').rglob('index.json')]
    references = {output for path, record in manifests.items()
                  for output in referenced_outputs(record, path.parent, data)}
    for path in sources:
        record = json.loads(path.read_text(encoding='utf-8'))
        references.update(referenced_outputs(record, path.parent, data))

    outputs = []
    for manifest, record in manifests.items():
        separator = {'vocals': 'separation', 'lead': 'lead-separation'}.get(manifest.parent.parent.name)
        if not separator:
            continue
        published = record['files']['audio']
        audio = (manifest.parent/published['path']).resolve()
        if audio.name != 'vocals.wav' or audio.parent.parent != manifest.parent:
            continue
        work = audio.parent/separator
        temporary = work/'v.wav'
        if (temporary in references or temporary.resolve() != temporary or not temporary.is_file()
                or not (work/'resources.json').is_file()):
            continue
        if not audio.is_file() or audio.stat().st_size != published['size'] or digest_file(audio) != published['sha256']:
            continue
        outputs.append(dict(path=temporary.relative_to(data).as_posix(), bytes=temporary.stat().st_size))
    if apply:
        for output in outputs:
            (data/output['path']).unlink()
    return dict(applied=apply, bytes=sum(output['bytes'] for output in outputs), files=outputs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data_copy', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(cleanup(args.data_copy, apply=args.apply), indent=2))
