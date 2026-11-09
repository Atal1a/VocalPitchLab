"""Export aligned tracks from a completed analysis."""
from contextlib import ExitStack
from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import soundfile as sf

from vocalpitchlab.analysis.analysis_cache import digest_file


@dataclass(frozen=True)
class CachedVocals:
    folder: Path
    digest: str

    def current_path(self):
        try:
            record = json.loads((self.folder / 'complete.json').read_text(encoding='utf-8'))['files']['audio']
            audio = (self.folder / record['path']).resolve()
            if (audio.is_relative_to(self.folder) and record['sha256'] == self.digest
                    and audio.is_file() and audio.stat().st_size == record['size']):
                return audio
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            pass
        return None

    def recover_path(self, interrupted):
        # A rebuilt stage can publish a new manifest while its previous audio
        # still belongs to an older song result.
        for candidate in self.folder.glob('*/vocals.wav'):
            if interrupted():
                return None
            try:
                audio = candidate.resolve()
                if audio.is_relative_to(self.folder) and digest_file(audio, interrupted) == self.digest:
                    return audio
            except (OSError, RuntimeError):
                continue
        if interrupted():
            return None
        raise FileNotFoundError('The cached vocal track is missing')


def full_vocal_path(song, lead):
    if song.get('full_vocals') and Path(song['full_vocals']).is_file():
        return Path(song['full_vocals'])
    # Earlier v2 results recorded the vocal stage identity instead of its path.
    if 'vocals' in song.get('stage_cache', {}):
        try:
            stage = song['stage_cache']['vocals']
            root = (lead.parents[3] / 'vocals').resolve()
            folder = (root / stage['key']).resolve()
            if folder.parent != root:
                return None
            cache = CachedVocals(folder, stage['content']['audio'])
            return cache.current_path() or (cache if next(folder.glob('*/vocals.wav'), None) else None)
        except (OSError, ValueError, KeyError, IndexError, TypeError, RuntimeError):
            return None
    # v1 stored both outputs beside one another.
    if song.get('algorithm', {}).get('pipeline') == 'lead-default-v1':
        return lead.with_name('all-vocals.wav')


def stem_sources(song):
    """Map track names to one source or two sources to subtract."""
    mode = song.get('algorithm', {}).get('separation', 'htdemucs')
    audio = song.get('audio', {})
    if mode == 'original' or not audio.get('vocals') or not audio.get('original'):
        return {}
    original, vocals = Path(audio['original']), Path(audio['vocals'])
    if vocals.resolve() == original.resolve():
        return {}
    if mode == 'mel_bs':
        full = full_vocal_path(song, vocals)
        stems = {'lead-vocals': (vocals,)}
        if full is not None:
            stems['instrumental'] = (original, full)
            stems['backing-vocals'] = (full, vocals)
    elif mode == 'bs_only':
        stems = {'lead-vocals': (vocals,), 'backing-mix': (original, vocals)}
    else:
        stems = {'vocals': (vocals,), 'instrumental': (original, vocals)}
    return {name: sources for name, sources in stems.items()
            if all(isinstance(source, CachedVocals) or source.is_file() for source in sources)}


def export_wav(destination, sources, interrupted=lambda: False):
    """Preserve sample alignment and gain, and replace the destination only on success."""
    sources = [source.recover_path(interrupted) if isinstance(source, CachedVocals) else source
               for source in sources]
    if None in sources or interrupted():
        return
    with NamedTemporaryFile(dir=destination.parent, prefix='.vpl-', suffix='.tmp', delete=False) as file:
        temporary = Path(file.name)
    try:
        with ExitStack() as stack:
            inputs = [stack.enter_context(sf.SoundFile(path)) for path in sources]
            primary = inputs[0]
            shape = (primary.samplerate, primary.channels, primary.frames)
            if primary.frames <= 0:
                raise ValueError('Empty audio track')
            if any((audio.samplerate, audio.channels, audio.frames) != shape for audio in inputs[1:]):
                raise ValueError('Unaligned audio tracks')
            # Reserve space for the RIFF header as well as the float32 samples.
            wav_format = 'RF64' if primary.frames * primary.channels * 4 >= (1 << 32) - 1024 else 'WAV'
            output = stack.enter_context(sf.SoundFile(
                temporary, 'w', primary.samplerate, primary.channels, format=wav_format, subtype='FLOAT'
            ))
            buffers = [np.empty((min(primary.frames, 65536), primary.channels), dtype='float32')
                       for _ in inputs]
            for offset in range(0, primary.frames, 65536):
                if interrupted():
                    return
                frames = min(65536, primary.frames - offset)
                blocks = [audio.read(out=buffer[:frames]) for audio, buffer in zip(inputs, buffers)]
                if any(len(block) != frames for block in blocks):
                    raise ValueError('Incomplete audio track')
                block = blocks[0]
                if len(blocks) == 2:
                    block -= blocks[1]
                if not np.isfinite(block).all():
                    raise ValueError('Invalid audio samples')
                try:
                    output.write(block)
                except AssertionError as error:
                    # soundfile asserts when libsndfile reports a short write.
                    raise OSError('Incomplete WAV write') from error
        if not interrupted():
            if sf.info(temporary).frames != shape[2]:
                raise OSError('Incomplete WAV file')
            temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
