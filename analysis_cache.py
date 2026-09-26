"""Content-addressed stages with process locks and atomic completion manifests."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from app_paths import DATA_ROOT


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextlib.contextmanager
def locked(path):
    """OS releases this lock even when the analysis worker is killed."""
    with Path(path).open('a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        if os.name == 'nt':
            import msvcrt
            while True:
                try:
                    stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(.2)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def stage(name, signature, producer):
    """Producer returns named files within its private work directory.

    Only a valid manifest publishes a stage. Interrupted/failed work directories
    remain unreferenced; no existing user result is removed or overwritten.
    """
    key = hashlib.sha256(json.dumps(signature, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    folder = DATA_ROOT / 'results' / 'stages' / name / key
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / 'complete.json'
    with locked(folder / '.lock'):
        try:
            saved = json.loads(manifest.read_text(encoding='utf-8'))
            paths = {k: folder / v['path'] for k, v in saved['files'].items()}
            if saved['signature'] == signature and paths and all(
                p.resolve().is_relative_to(folder.resolve()) and p.is_file()
                and p.stat().st_size == saved['files'][k]['size']
                and digest_file(p) == saved['files'][k]['sha256'] for k, p in paths.items()
            ):
                return paths, dict(key=key, content={k:v['sha256'] for k,v in saved['files'].items()}, hit=True, seconds=0)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        work = folder / ('work-' + uuid.uuid4().hex)
        work.mkdir()
        start = time.perf_counter()
        paths = {k: Path(v) for k, v in producer(work).items()}
        if not paths or not all(p.resolve().is_relative_to(work.resolve()) and p.is_file() and p.stat().st_size > 0 for p in paths.values()):
            raise ValueError('Incomplete stage: ' + name)
        seconds = time.perf_counter() - start
        files = {k: dict(path=p.relative_to(folder).as_posix(), size=p.stat().st_size, sha256=digest_file(p)) for k, p in paths.items()}
        atomic_json(manifest, dict(signature=signature, seconds=seconds, files=files))
        return paths, dict(key=key, content={k:v['sha256'] for k,v in files.items()}, hit=False, seconds=round(seconds, 3))
