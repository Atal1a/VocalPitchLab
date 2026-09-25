"""Windows GM acoustic grand, equal temperament (A4=440 Hz)."""
import ctypes
import threading
from PySide6.QtCore import QObject,QTimer,Signal

class Piano(QObject):
    ready=Signal(bool);played=Signal(int);failed=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self.handle=ctypes.c_void_p();self.note=None;self.loading=False;self.pending=None;self.closed=False;self.lock=threading.Lock();self.volume=.65
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
        self.send(0xB0,0,0);self.send(0xB0,32,0);self.send(0xC0,0);self.send(0xE0,0,64)
        self.set_volume(self.volume)
        if self.pending:
            note,velocity=self.pending;self.pending=None;self.play(note,velocity)
    def send(self,status,a=0,b=0):
        result=self.api.midiOutShortMsg(self.handle,status|(int(a)<<8)|(int(b)<<16))
        if result:raise OSError(f'MIDI output error {result}')
    def play(self,note,velocity=110):
        if self.closed or self.volume<=0 or not 21<=note<=108:return
        if self.loading or not self.handle.value:
            self.pending=(note,velocity);self.warm();return
        self.release();self.send(0x90,note,max(1,min(127,velocity)));self.note=note;self.timer.start(850);self.played.emit(note)
    def set_volume(self,value):
        self.volume=max(0.,min(1.,float(value)))
        if self.handle.value and not self.loading:self.send(0xB0,7,round(127*self.volume))
        if self.volume==0:
            self.pending=None;self.release()
    def release(self):
        self.timer.stop()
        if self.handle.value and self.note is not None:self.send(0x80,self.note,0)
        self.note=None
    def close(self):
        self.timer.stop();self.pending=None
        with self.lock:
            self.closed=True
            if self.handle.value:self.api.midiOutReset(self.handle);self.api.midiOutClose(self.handle);self.handle=ctypes.c_void_p()
