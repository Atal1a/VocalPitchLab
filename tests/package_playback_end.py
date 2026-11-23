"""Exercise dual-track playback at the end of a song in the Qt application loop."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import soundfile as sf


def seed_library(folder):
    folder.mkdir()
    sample_rate = 44100
    frames = 176416
    time_axis = np.arange(frames) / sample_rate
    original, vocals = folder / 'original.wav', folder / 'vocals.wav'
    vocal_samples = .02 * np.sin(2 * np.pi * 220 * time_axis)
    original_samples = vocal_samples + .02 * np.sin(2 * np.pi * 330 * time_axis)
    for path, samples in ((original, original_samples), (vocals, vocal_samples)):
        sf.write(path, np.column_stack((samples, samples)), sample_rate, subtype='FLOAT')
    curve = folder / 'curve.csv'
    curve.write_text('time_seconds,midi_float,periodicity_or_probability\n0,57,1\n2,57,1\n4,57,1\n',
                     encoding='utf-8')
    song = dict(name='Playback test', duration=frames / sample_rate, source=str(original),
                audio=dict(original=str(original), vocals=str(vocals)), algorithm=dict(separation='mel_bs'),
                curves=dict(crepe_full=str(curve)))
    (folder / 'index.json').write_text(json.dumps(dict(songs=[song])), encoding='utf-8')


def exercise(controller, positions, result, loops):
    from PySide6.QtMultimedia import QMediaPlayer

    player = controller.player
    vocal_player = controller.vocal_player
    playback = QMediaPlayer.PlaybackState
    media = QMediaPlayer.MediaStatus
    yield 'load both tracks', lambda: player.duration() >= 4000 and vocal_player.duration() >= 4000
    controller.setVolume(.1)
    start, duration = 3.25, controller.song['duration']
    for source, visible, end in (('original', True, duration), ('vocals', False, duration),
                                 ('vocals', True, 3.75)):
        controller.setSource(source)
        controller.setPresentationVisible(visible)
        controller.setLoopRange(start, end)
        controller.seek(start)
        controller.setLoop(True)
        positions.clear()
        controller.togglePlay()
        threshold = round(end * 1000) - 120

        def wraps():
            return [(before, after) for before, after in zip(positions, positions[1:])
                    if before >= threshold and abs(after - start * 1000) < 30]

        yield f'{source} loop at {end:.3f}s', lambda: len(wraps()) >= loops and controller.state_playing()
        result['loops'].append(dict(source=source, visible=visible, end=end, wraps=wraps()))
        controller.togglePlay()
        assert player.playbackState() == playback.PausedState, player.playbackState()
        assert vocal_player.playbackState() != playback.PlayingState, vocal_player.playbackState()

    controller.setLoop(False)
    controller.seek(3.3)
    controller.togglePlay()
    yield 'natural finish', lambda: player.mediaStatus() == media.EndOfMedia and not controller.state_playing()
    assert vocal_player.playbackState() != playback.PlayingState
    result['natural_finish'] = True
    controller.togglePlay()
    yield 'replay and both tracks advance', lambda: (
        controller.state_playing() and 150 <= player.position() < 1000 and vocal_player.position() >= 150
    )
    controller.setSource('original')
    yield 'switch tracks without resetting playback', lambda: controller.state_playing() and player.position() >= 350
    result['replay_and_switch'] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', type=Path)
    parser.add_argument('data', type=Path)
    parser.add_argument('--loops', type=int, default=5)
    args = parser.parse_args()
    stage, data = args.stage.resolve(), args.data.resolve()
    data.mkdir(parents=True)
    seed_library(data / 'library')
    os.environ.update(VPL_DATA_DIR=str(data), QT_QUICK_BACKEND='software')
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    sys.path.insert(0, str(stage))

    from PySide6.QtCore import QTimer, QUrl
    from vocalpitchlab.ui.app import Controller, QGuiApplication, create_engine

    app = QGuiApplication([])
    controller = Controller(bootstrap=False)
    engine = create_engine(controller)
    assert engine.rootObjects(), 'QML window did not load'
    positions = []
    controller.player.positionChanged.connect(positions.append)
    result = dict(backend=os.environ.get('QT_MEDIA_BACKEND', 'auto'), loops=[])
    steps = exercise(controller, positions, result, args.loops)
    pending = None
    deadline = 0.
    errors = []
    timer = QTimer()

    def advance():
        nonlocal pending, deadline
        try:
            if pending is not None and not pending[1]():
                if time.monotonic() > deadline:
                    raise TimeoutError(f'{pending[0]} did not complete: {positions[-15:]}')
                return
            pending = next(steps)
            deadline = time.monotonic() + max(8, args.loops * 1.5)
        except StopIteration:
            timer.stop()
            app.quit()
        except Exception as error:
            errors.append(error)
            timer.stop()
            app.quit()

    # Use the same running event loop as the desktop app so audio threads can finish at EOF.
    timer.timeout.connect(advance)
    timer.start(10)
    app.exec()
    controller.shutdown()
    controller.player.setSource(QUrl())
    controller.vocal_player.setSource(QUrl())
    engine.rootObjects()[0].close()
    if errors:
        raise errors[0]
    (data / 'playback-end.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
