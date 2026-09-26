"""Prepare versioned GAME caches without changing the live library index."""
import json,time
import soundfile as sf
from game_notes import GameNotes,cache_path,ROOT,VERSION,gate_silent_notes

def prepare(song,model=None):
    path=cache_path(song)
    if path.exists():return path
    audio,sr=sf.read(song['audio']['vocals'],dtype='float32',always_2d=True)
    notes=(model or GameNotes()).transcribe(audio,sr)
    assert all(0<=n['start']<n['end']<=len(audio)/sr+.001 for n in notes)
    assert all(a['end']<=b['start'] for a,b in zip(notes,notes[1:]))
    path.parent.mkdir(exist_ok=True,parents=True);temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(version=VERSION,notes=notes),ensure_ascii=False,indent=2),encoding='utf8');temporary.replace(path)
    return path

if __name__=='__main__':
    model=GameNotes();songs=json.loads((ROOT/'library/index.json').read_text(encoding='utf8'))['songs']
    for song in sorted(songs,key=lambda s:'rise' not in s['name'].lower()):
        start=time.perf_counter();p=prepare(song,model);print(song['name'],round(time.perf_counter()-start,1),len(json.loads(p.read_text(encoding='utf8'))['notes']),flush=True)
