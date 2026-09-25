"""Full local analysis of one song, then add its result to the existing library."""
import argparse,json,time
from pathlib import Path
import numpy as np
import librosa,soundfile as sf,torch
from lab import ROOT,run,write_track
from rmvpe_adapter import PitchEstimator
from benchmark_vocadito import predict,OUT,save
from main_notes import extract,audio_onsets,current_settings,export_notes

def main():
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--result-file');p.add_argument('--standalone',action='store_true');p.add_argument('--separation',choices=['htdemucs','mel_roformer','mel_bs'],default='mel_bs');args=p.parse_args()
    def progress(value,message):
        print('VPL_EVENT '+json.dumps(dict(progress=value,message=message),ensure_ascii=False),flush=True)
    source=Path(args.file).resolve()
    previous=sorted((ROOT/'results').glob('rmvpe-*/index.json'))
    old=json.loads(previous[-1].read_text(encoding='utf-8')) if previous and not args.standalone else dict(songs=[])
    baseline=run(argparse.Namespace(file=str(source),start=0,seconds=0,methods=['tiny','full'],no_separate=False,separation=args.separation),progress)
    prefix='analysis-' if args.standalone else 'rmvpe-'
    folder=ROOT/'results'/(time.strftime(prefix+'%Y%m%d-%H%M%S')+'-'+str(time.time_ns())[-6:]);folder.mkdir()
    audio,sr=sf.read(baseline/'vocals.wav',dtype='float32',always_2d=True)
    from resource_policy import device as select_device
    device=select_device()
    import csv
    crepe=list(csv.DictReader((baseline/'full.csv').open(encoding='utf-8-sig')))
    progress(78,'核对音高结果')
    rmvpe,salience,rms=PitchEstimator(device).track(audio,sr,return_salience=True);write_track(folder/'rmvpe-vocals.csv',rmvpe)
    from pitch_experiments import continuous_pitch
    tracked,tracked_score=continuous_pitch(salience,rms,rmvpe[4])
    write_track(folder/'rmvpe-tracked.csv',(rmvpe[0],tracked.copy(),tracked,tracked_score,np.isfinite(tracked)))
    path=folder/'rmvpe-vocals.csv';path.write_text(path.read_text(encoding='utf-8-sig').replace('periodicity_or_probability','rmvpe_max_salience',1),encoding='utf-8-sig')
    y=librosa.resample(audio.mean(axis=1),orig_sr=sr,target_sr=16000)
    d=dict(crepe_raw=np.array([float(r['raw_hz']) for r in crepe]),crepe_score=np.array([float(r['periodicity_or_probability']) for r in crepe]),rmvpe_raw=rmvpe[1],rmvpe_score=rmvpe[3],rms=librosa.feature.rms(y=y,frame_length=1024,hop_length=160)[0])
    n=min(map(len,d.values()));d={k:v[:n] for k,v in d.items()}
    from app_paths import APP_ROOT
    pc=json.loads((APP_ROOT/'resources/pitch-config.json').read_text(encoding='utf-8'));midi=predict(d,pc)
    from benchmark_vocadito import single
    from pitch_modes import recover_gaps
    midi=recover_gaps(midi,single(d,'crepe',.5,3),single(d,'rmvpe',.03,3),d['crepe_score'],d['rmvpe_score'])
    pc=dict(pc,gap_recovery='agreement-v1')
    times=np.arange(n)*.01;hz=440*2**((midi-69)/12)
    write_track(folder/'candidate.csv',(times,hz,hz,np.zeros(n),np.isfinite(hz)))
    progress(90,'整理主要音符')
    settings=current_settings();onsets=audio_onsets(audio,sr,settings['onset_prominence_db']) if settings.get('onset_prominence_db') else None
    notes=extract(times,midi,onset_times=onsets);npth=folder/'main-notes.json'
    save(npth,dict(settings=settings,source='tuned_vocals',notes=notes));export_notes(npth.with_suffix('.csv'),notes)
    duration=len(audio)/sr
    windows=[dict(start=s,end=min(s+20,duration),label=label) for s,label in [(max(0,notes[0]['start']-2) if notes else 0,'第一段演唱'),(max(0,duration*.5-10),'歌曲中段'),(max(0,duration-30),'歌曲末段')]]
    song=dict(name=source.stem,duration=duration,baseline=str(baseline),audio={kind:str(baseline/(kind+'.wav')) for kind in ['original','vocals']},curves=dict(crepe_full=str(baseline/'full.csv'),crepe_tiny=str(baseline/'tiny.csv'),rmvpe_vocals=str(folder/'rmvpe-vocals.csv'),tuned_vocals=str(folder/'candidate.csv')),main_notes=str(npth),review_windows=windows)
    song.update(source=str(source),algorithm=dict(pitch=pc,notes=settings),created=time.strftime('%Y-%m-%d %H:%M:%S'))
    song['algorithm']['separation']=args.separation
    if args.separation in ['mel_roformer','mel_bs']:
        from vocal_separator import VERSION as separation_version
        song['algorithm']['separation_version']=separation_version
    song['algorithm'].update(pipeline='lead-default-v1',display_pitch='rmvpe_tracked',harmony_separation=args.separation=='mel_bs')
    if args.separation=='mel_bs':song['algorithm']['lead_separation_version']='bs-frazer-becruily-eb90ee24-overlap4-v1'
    song['curves']['rmvpe_tracked']=str(folder/'rmvpe-tracked.csv')
    progress(94,'识别音符边界')
    from prepare_game_notes import prepare
    from game_notes import VERSION
    from game_notes import REFINEMENT_VERSION
    prepare(song);song['algorithm']['note_events']=VERSION+'+'+REFINEMENT_VERSION
    metrics=dict(device=device)
    if device=='cuda':metrics.update(cuda_peak_allocated_mib=torch.cuda.max_memory_allocated()/2**20,cuda_peak_reserved_mib=torch.cuda.max_memory_reserved()/2**20)
    save(folder/'resource-metrics.json',metrics)
    old['songs']=[s for s in old['songs'] if s['name']!=song['name']]+[song]
    old.update(created=time.strftime('%Y-%m-%d %H:%M:%S'),candidate_config=pc,note_settings=settings)
    save(folder/'index.json',old)
    if args.result_file:
        target=Path(args.result_file);temporary=target.with_suffix('.tmp')
        save(temporary,dict(song=song,index=str(folder/'index.json')));temporary.replace(target)
    progress(100,'分析完成，结果已保存')
    print(json.dumps(dict(index=str(folder/'index.json'),song=song['name'],duration=duration,notes=len(notes)),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
