"""Monophonic sampled piano on a warm, short-buffer Qt audio stream."""
import numpy as np
import soundfile as sf
from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices

from vocalpitchlab.audio.piano import DEFAULT_VELOCITY, DEFAULT_VOLUME
from vocalpitchlab.runtime.paths import APP_ROOT


SAMPLE_RATE = 48000
ANCHORS = (*range(21, 106, 6), 108)


class Voice:
    def __init__(self, sample, ratio, rate, velocity):
        self.sample = sample
        self.ratio = ratio
        self.rate = rate
        self.gain = min(127, max(1, velocity)) / (32768 * DEFAULT_VELOCITY)
        self.frame = 0
        self.release_at = None
        self.release_length = max(1, rate // 12)
        self.done = False

    def release(self):
        if self.release_at is None:
            # A quick click can end before the audio thread has read the attack.
            self.release_at = max(self.frame, self.rate // 25)

    def read(self, positions):
        frames = self.frame + positions
        index = frames * self.ratio
        base = np.minimum(index.astype(np.intp), len(self.sample)-2)
        frac = np.minimum(index - base, 1.)
        lo = self.sample[base].astype(np.float32)
        hi = self.sample[base+1].astype(np.float32)
        output = ((lo + frac*(hi-lo))*self.gain).astype(np.float32)
        output[index >= len(self.sample)] = 0.
        if self.release_at is not None:
            output *= np.clip(1 - (frames-self.release_at)/self.release_length, 0., 1.)
        self.frame += len(positions)
        self.done = (self.frame*self.ratio >= len(self.sample)-1 or
                     (self.release_at is not None and self.frame >= self.release_at+self.release_length))
        return output


class SamplePiano(QObject):
    played = Signal(int)
    failed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.volume = DEFAULT_VOLUME
        self.closed = False
        self.samples = {}
        self.voice = None
        self.tail = None
        self.sink = self.writer = None
        self.pending_pcm = b''
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self.output_changed)
        self.feed_timer = QTimer(self, timerType=Qt.TimerType.PreciseTimer, interval=10)
        self.feed_timer.timeout.connect(self.feed)
        self.release_timer = QTimer(self, singleShot=True, interval=850)
        self.release_timer.timeout.connect(self.release)

    def warm(self):
        if self.closed or self.sink is not None:
            return
        if not self.samples:
            bank = {}
            for midi in ANCHORS:
                path = APP_ROOT/'assets'/'piano'/f'{midi}.flac'
                if not path.is_file():
                    raise OSError('Missing piano sample')
                sample, rate = sf.read(path, dtype='int16')
                if sample.ndim != 1 or rate != SAMPLE_RATE or len(sample) < 2:
                    raise OSError('Invalid piano sample format')
                bank[midi] = sample
            self.samples = bank
        device = self.devices.defaultAudioOutput()
        if device.isNull():
            raise OSError('No audio output device')
        fmt = device.preferredFormat()
        self.rate = fmt.sampleRate()
        self.channels = fmt.channelCount()
        self.sample_format = fmt.sampleFormat()
        if not fmt.isValid() or self.sample_format == QAudioFormat.SampleFormat.Unknown:
            raise OSError('Unsupported piano output format')
        sink = QAudioSink(device, fmt, self)
        sink.setBufferSize(fmt.bytesForDuration(30_000))
        sink.setVolume(self.volume**2)
        writer = sink.start()
        if writer is None or sink.error() != QAudio.Error.NoError:
            sink.deleteLater()
            raise OSError('Unable to open piano audio stream')
        chunk = max(1, min(self.rate//100, sink.bufferSize()//fmt.bytesPerFrame()))
        self.positions = np.arange(chunk, dtype=np.float64)
        self.crossfade = np.clip(1 - self.positions/max(1, self.rate//200), 0., 1.).astype(np.float32)
        silent_byte = 128 if self.sample_format == QAudioFormat.SampleFormat.UInt8 else 0
        self.silence = bytes([silent_byte]) * (chunk*fmt.bytesPerFrame())
        self.device_id = device.id()
        self.sink, self.writer = sink, writer
        sink.stateChanged.connect(self.stream_state_changed)
        self.feed()
        if self.sink is None:
            raise OSError('Unable to write to piano audio stream')
        self.feed_timer.start()

    def play(self, note, velocity=DEFAULT_VELOCITY, *, hold=False):
        if self.closed or self.volume <= 0 or not 21 <= note <= 108:
            return
        self.warm()
        self.release_timer.stop()
        anchor = min(ANCHORS, key=lambda midi: abs(midi-note))
        if self.voice is not None and self.voice.frame:
            self.tail = self.voice
        ratio = (SAMPLE_RATE/self.rate) * 2**((note-anchor)/12)
        self.voice = Voice(self.samples[anchor], ratio, self.rate, velocity)
        self.feed()
        if self.sink is None:
            return
        if not hold:
            self.release_timer.start()
        self.played.emit(note)

    def render(self):
        if self.voice is None:
            return self.silence
        output = self.voice.read(self.positions)
        if self.tail is not None:
            output = output*(1-self.crossfade) + self.tail.read(self.positions)*self.crossfade
            self.tail = None
        if self.voice.done:
            self.voice = None
        output = np.clip(output, -1., 1.)
        channels = np.zeros((len(output), self.channels), dtype=np.float32)
        channels[:, :2] = output[:, None]
        if self.sample_format == QAudioFormat.SampleFormat.Int16:
            channels = (channels*32767).astype(np.int16)
        elif self.sample_format == QAudioFormat.SampleFormat.Int32:
            channels = (channels.astype(np.float64)*2147483647).astype(np.int32)
        elif self.sample_format == QAudioFormat.SampleFormat.UInt8:
            channels = (channels*127+128).astype(np.uint8)
        return channels.tobytes()

    def feed(self):
        if self.sink is None:
            return
        for _ in range(self.sink.bytesFree()//len(self.silence)):
            payload = self.pending_pcm or self.render()
            written = self.writer.write(payload)
            if written < 0:
                self.stream_failed()
                return
            self.pending_pcm = payload[written:]
            if self.pending_pcm:
                return

    def set_volume(self, value):
        self.volume = max(0., min(1., float(value)))
        if self.sink is not None:
            self.sink.setVolume(self.volume**2)
        if self.volume == 0:
            self.release_timer.stop()
            self.voice = self.tail = None
            self.pending_pcm = b''

    def release(self):
        self.release_timer.stop()
        if self.voice is not None:
            self.voice.release()

    def stream_state_changed(self, state):
        if self.sink is not None and state == QAudio.State.StoppedState:
            # Avoid destroying the writer from inside its own state callback.
            QTimer.singleShot(0, self.check_stream)

    def check_stream(self):
        if self.sink is not None and self.sink.state() == QAudio.State.StoppedState:
            self.stream_failed()

    def stream_failed(self):
        self.stop_stream()
        self.failed.emit()

    def output_changed(self):
        if self.sink is not None and self.devices.defaultAudioOutput().id() != self.device_id:
            self.stop_stream()

    def stop_stream(self):
        self.feed_timer.stop()
        self.release_timer.stop()
        self.voice = self.tail = None
        self.pending_pcm = b''
        sink = self.sink
        self.sink = self.writer = None
        if sink is not None:
            sink.reset()
            sink.deleteLater()

    def close(self):
        self.closed = True
        self.stop_stream()
