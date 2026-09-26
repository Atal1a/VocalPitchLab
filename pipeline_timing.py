"""Wall-clock spans; overlapping work is counted once in the busy union."""
import time
from threading import Lock
from contextlib import contextmanager

class Timeline:
    def __init__(self):
        self.origin=time.perf_counter();self.spans=[];self.lock=Lock()
    @contextmanager
    def span(self,name):
        start=time.perf_counter()
        try:yield
        finally:
            end=time.perf_counter()
            with self.lock:self.spans.append(dict(name=name,start=start-self.origin,end=end-self.origin))
    def report(self):
        total=time.perf_counter()-self.origin
        with self.lock:spans=sorted((dict(s) for s in self.spans),key=lambda s:s['start'])
        covered=0.;end=0.
        for s in spans:
            covered+=max(0.,s['end']-max(end,s['start']));end=max(end,s['end'])
            s['seconds']=s['end']-s['start']
        return dict(version=1,total_seconds=total,busy_union_seconds=covered,
                    other_seconds=max(0.,total-covered),spans=spans)
