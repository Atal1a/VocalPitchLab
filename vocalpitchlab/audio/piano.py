"""Windows GM acoustic grand, equal temperament (A4=440 Hz)."""
import ctypes
import threading
from PySide6.QtCore import QObject,QTimer,Signal

DEFAULT_VOLUME = .65
DEFAULT_VELOCITY = 110
MAX_BOOST_VOLUME = 90

class Piano(QObject):
    ready=Signal(bool);played=Signal(int);failed=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.handle=ctypes.c_void_p();self.note=None;self.loading=False;self.pending=None;self.closed=False;self.lock=threading.Lock();self.volume=DEFAULT_VOLUME
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.release)
        self.api=ctypes.WinDLL('winmm')
        self.api.midiOutOpen.argtypes=[ctypes.POINTER(ctypes.c_void_p),ctypes.c_uint,ctypes.c_size_t,ctypes.c_size_t,ctypes.c_uint]
        self.api.midiOutShortMsg.argtypes=[ctypes.c_void_p,ctypes.c_uint]
        self.api.midiOutReset.argtypes=[ctypes.c_void_p];self.api.midiOutClose.argtypes=[ctypes.c_void_p]
        self.ready.connect(self.opened)
    def warm(self):
        if self.loading or self.handle.value or self.closed:return
        self.loading=True;threading.Thread(target=self.open_device,daemon=True).start()
    def open_device(self):
        handle=ctypes.c_void_p();result=self.api.midiOutOpen(ctypes.byref(handle),0xffffffff,0,0,0)
        with self.lock:
            if self.closed:
                if not result:self.api.midiOutClose(handle)
                return
            if not result:self.handle=handle
        self.ready.emit(not result)
    def opened(self,ok):
        self.loading=False
        if self.closed:return
        if not ok:self.pending=None;self.failed.emit();return
        for channel in (0, 1):
            self.send(0xB0 | channel,0,0);self.send(0xB0 | channel,32,0)
            self.send(0xC0 | channel,0);self.send(0xE0 | channel,0,64)
        self.set_volume(self.volume)
        if self.pending:
            note,velocity,hold=self.pending;self.pending=None;self.play(note,velocity,hold=hold)
    def send(self,status,a=0,b=0):
        result=self.api.midiOutShortMsg(self.handle,status|(int(a)<<8)|(int(b)<<16))
        if result:raise OSError(f'MIDI output error {result}')
    def boost_fraction(self):
        return max(0., (self.volume - DEFAULT_VOLUME) / (1 - DEFAULT_VOLUME))
    def play(self,note,velocity=DEFAULT_VELOCITY,*,hold=False):
        if self.closed or self.volume<=0 or not 21<=note<=108:return
        if self.loading or not self.handle.value:
            self.pending=(note,velocity,hold);self.warm();return
        # Use the remaining MIDI velocity headroom above the default volume.
        velocity = round(velocity * (1 + self.boost_fraction() * (127 / DEFAULT_VELOCITY - 1)))
        velocity = max(1, min(127, velocity))
        self.release()
        self.send(0x90,note,velocity);self.note=note
        try:self.send(0x91,note,velocity)
        except OSError:
            self.release()
            raise
        if not hold:self.timer.start(850)
        self.played.emit(note)
    def set_volume(self,value):
        self.volume=max(0.,min(1.,float(value)))
        if self.handle.value and not self.loading:
            self.send(0xB0,7,round(127*self.volume))
            # A second voice on the same pitch adds gain above the main channel's ceiling.
            self.send(0xB1,7,round(MAX_BOOST_VOLUME*self.boost_fraction()))
        if self.volume==0:
            self.release()
    def release(self):
        self.timer.stop();self.pending=None
        note=self.note;self.note=None
        if self.handle.value and note is not None:
            try:self.send(0x80,note,0)
            finally:self.send(0x81,note,0)
    def close(self):
        self.timer.stop();self.pending=None
        with self.lock:
            self.closed=True
            if self.handle.value:self.api.midiOutReset(self.handle);self.api.midiOutClose(self.handle);self.handle=ctypes.c_void_p()
