"""Identity of an imported file and of its decoded playback audio."""
from pathlib import Path

from vocalpitchlab.analysis.analysis_cache import digest_file


class RecordingChanged(ValueError):
    pass


def source_signature(path):
    stat = path.stat()
    return [stat.st_size, stat.st_mtime_ns]


def decoded_hash(song):
    cached = song.get('stage_cache', {}).get('decode', {}).get('content', {}).get('audio')
    if cached:
        return cached
    try:
        return digest_file(song['audio']['original'])
    except OSError:
        return None


def same_recording(first, second):
    a, b = first.get('source_sha256'), second.get('source_sha256')
    if a and b and a != b:
        return False
    original_a, original_b = decoded_hash(first), decoded_hash(second)
    if original_a and original_b:
        return original_a == original_b
    return bool(a and a == b)


def recording_request(song):
    return dict(original=song['audio']['original'], decoded_sha256=decoded_hash(song),
                source_sha256=song.get('source_sha256'), source_signature=song.get('source_signature'),
                decode_key=song.get('stage_cache', {}).get('decode', {}).get('key'))


def prepared_original(recording):
    path = Path(recording['original'])
    expected = recording['decoded_sha256']
    if expected:
        try:
            if digest_file(path) == expected:
                return path
        except OSError:
            pass
    return None
