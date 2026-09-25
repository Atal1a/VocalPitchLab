"""Record downloaded wheel hashes and verify publisher checksums before reuse."""
import concurrent.futures
import email
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'work/repro-build'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'VocalPitchLab-build'})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def record(path):
    with zipfile.ZipFile(path) as archive:
        name = next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))
        meta = email.message_from_bytes(archive.read(name))
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    result = dict(file=path.name, name=meta['Name'], version=meta['Version'], sha256=digest,
                  bytes=path.stat().st_size, group=path.parent.name)
    if meta['Name'].lower() in ['torch', 'torchaudio']:
        index = 'https://download.pytorch.org/whl/cu124/' + meta['Name'].lower() + '/'
        links = re.findall(r'href="([^"]+)"', fetch(index).decode())
        link = next(html.unescape(s) for s in links
                    if urllib.parse.unquote(urllib.parse.urlsplit(html.unescape(s)).path).endswith('/'+path.name))
        url = urllib.parse.urljoin(index, link)
        expected = urllib.parse.parse_qs(urllib.parse.urlsplit(url).fragment)['sha256'][0]
        assert expected == digest, path.name
        result.update(url=url, publisher_hash_verified=True)
    else:
        data = json.loads(fetch(f"https://pypi.org/pypi/{meta['Name']}/{meta['Version']}/json"))
        matching = next((f for f in data['urls'] if f['filename'] == path.name), None)
        if matching:
            assert matching['digests']['sha256'] == digest, path.name
            result.update(url=matching['url'], publisher_hash_verified=True)
        else:
            assert meta['Name'].lower() in ['demucs', 'antlr4-python3-runtime'], path.name
            source = next(f for f in data['urls'] if f['packagetype']=='sdist')
            content = fetch(source['url'])
            assert hashlib.sha256(content).hexdigest() == source['digests']['sha256']
            dest=WORK/'sources'; dest.mkdir(exist_ok=True)
            (dest/source['filename']).write_bytes(content)
            result.update(built_from=dict(url=source['url'], file=source['filename'],
                          sha256=source['digests']['sha256']), publisher_hash_verified=False,
                          build_tools={'setuptools': '78.1.0', 'wheel': '0.45.1'},
                          note='Local wheel built from upstream sdist with --no-build-isolation; wheel hash pins installation, not bit-identical rebuilds')
    return result


def main():
    paths = sorted((WORK/'wheels').glob('*.whl')) + sorted((WORK/'vendor-wheels').glob('*.whl'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(record, paths))
    assert {'torch', 'torchaudio'} <= {r['name'].lower() for r in records}, 'CUDA downloads incomplete'
    out=ROOT/'resources/reproducible';out.mkdir(exist_ok=True)
    for group,filename in [('wheels','runtime.lock'),('vendor-wheels','separation.lock')]:
        lines=[f"{r['name']}=={r['version']} --hash=sha256:{r['sha256']}" for r in records if r['group']==group]
        (out/filename).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (out/'artifacts.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(f'Locked {len(records)} wheels; publisher hashes or source provenance verified')


if __name__ == '__main__': main()
