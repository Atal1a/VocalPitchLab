"""Qt Quick frontend bridge. Analysis stays in the existing Python worker."""
import csv,json,sys,uuid,subprocess,math,os,time
from plot_support import PresentationClock,lod_stride,stable_envelope,vocal_loudness,melody_outline,vocal_gain
# Python paint callbacks must share the GUI thread; a threaded scene graph can
# deadlock synchronous window grabs while the GUI thread holds Python's GIL.
os.environ.setdefault('QSG_RENDER_LOOP','basic')
from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject,Signal,Slot,Property,Qt,QEvent,QUrl,QTimer,QProcess,QProcessEnvironment,QLockFile,QRectF,QElapsedTimer
from PySide6.QtGui import QGuiApplication,QColor,QPen,QPainterPath,QFont,QFontDatabase,QImage,QPainter,QLinearGradient,QIcon
from PySide6.QtQml import QQmlApplicationEngine,qmlRegisterType
from PySide6.QtQuick import QQuickPaintedItem
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput

from app_paths import APP_ROOT,DATA_ROOT,prepare,worker_python
ROOT=APP_ROOT
prepare()
FORMATS={'.mp3','.wav','.flac','.m4a','.aac','.ogg','.wma','.aiff'}
LABELS={'crepe_full':'CREPE 完整版','crepe_tiny':'CREPE 轻量版','rmvpe_vocals':'RMVPE','tuned_vocals':'调参候选'}
COLORS={'crepe_full':'#0072b2','crepe_tiny':'#b45309','rmvpe_vocals':'#b01874','tuned_vocals':'#111827'}
PITCH_MODES={'fusion':'tuned_vocals','crepe':'crepe_full','rmvpe':'rmvpe_vocals','tracked':'rmvpe_tracked','fcpe':'fcpe'}
LABELS.update(rmvpe_tracked='RMVPE 连续',fcpe='FCPE');COLORS.update(rmvpe_tracked='#0072b2',fcpe='#b01874')
def clock(t):return f'{int(t)//60:02d}:{t%60:05.2f}'
def note(m):
    if not np.isfinite(m):return '—'
    n=int(round(m));return ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][n%12]+str(n//12-1)
def write_json(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
def local_path(value):return Path(QUrl(value).toLocalFile()) if str(value).startswith('file:') else Path(value)

class Controller(QObject):
    changed=Signal();contentChanged=Signal();libraryChanged=Signal()
    def __init__(self,folder=None,bootstrap=True,worker=None):
        super().__init__();self.folder=Path(folder or DATA_ROOT/'library');self.folder.mkdir(parents=True,exist_ok=True);self.path=self.folder/'index.json'
        if self.path.exists():self.data=json.loads(self.path.read_text(encoding='utf-8'))
        else:
            choices=sorted((DATA_ROOT/'results').glob('rmvpe-*/index.json')) if bootstrap else []
            self.data=json.loads(choices[-1].read_text(encoding='utf-8')) if choices else {'songs':[]}
        self.data.setdefault('jobs',[])
        self.settings=dict(theme='system',hoverNotes=True,liveNotes=True,liveCurve=True,blocks=True,curve=True,volume=.65,pianoVolume=.65,pitchModel='tracked',noteMode='game',separationModel='mel_bs')
        self.settings.update(self.data.get('settings',{}));self.trash=[]
        self.settings.update(pitchModel='tracked',noteMode='game')
        if self.settings.get('pipelineVersion')!='lead-default-v1':
            self.settings.update(separationModel='mel_bs',pipelineVersion='lead-default-v1')
        self.settings.pop('motion',None)
        from vocal_separator import available
        self.high_quality_available=available()
        for song in self.data['songs']:song.setdefault('song_id',uuid.uuid4().hex)
        for job in self.data['jobs']:
            if job['state'] in ['running','queued']:job.update(state='interrupted',message='上次分析已中断，可重试')
        self.presentation_process=None;self.presentation_queue=[];self.presentation_active=None;self.closing=False
        self.process=None;self.active=None;self.display_job=None;self.buffer='';self.worker=Path(worker or ROOT/'analyze_song.py');self.reusable_worker=self.worker.resolve()==(ROOT/'analyze_song.py').resolve();self.worker_closing=False
        self.settings.setdefault('cleanCurve',True)
        self.curve_reliability={}
        self.song=None;self.selected=-1;self.series={};self.loudness=(np.array([0.]),np.array([.5]));self.notes=[];self.compare=set();self.message='选择或拖入歌曲，开始分析。'
        self.t=0.;self.span=20.;self.low=48.;self.high=72.;self.auto=False;self.show_curve=True;self.show_blocks=True
        self.source='vocals';self.window_index=0;self.loop=False;self.pending=None;self.resume=False;self.changing=False;self.revision=0;self.buffer_seek=None
        self.loop_a=0.;self.loop_b=10.;self.loop_initialized=False;self.muted=False
        self.show_blocks=self.settings['blocks'];self.show_curve=self.settings['curve']
        self.clock_anchor=QElapsedTimer();self.clock_anchor.start();self.anchor_t=0.;self.presentation=PresentationClock();self.presentation.reset(0,time.monotonic());self.presentation_pending=False
        self.player=QMediaPlayer(self);self.output=QAudioOutput(self);self.output.setVolume(self.settings['volume']);self.player.setAudioOutput(self.output)
        self.vocal_player=QMediaPlayer(self);self.vocal_output=QAudioOutput(self);self.vocal_player.setAudioOutput(self.vocal_output);self.vocal_output.setMuted(True)
        self.vocal_pending=False;self.vocal_player.mediaStatusChanged.connect(self.vocal_ready)
        self.audio_song=None;self.vocal_boost=1.;self.piano=None;self.preview_note=None;self.preview_until=0.;self.readout_time=-1.;self.readout_pitch='—';self.drag_view=None
        self.player.positionChanged.connect(self.position);self.player.mediaStatusChanged.connect(self.media)
        self.player.playbackStateChanged.connect(self.playback_changed)
        self.player.errorOccurred.connect(lambda *args:self.feedback('音频无法播放，请检查结果文件是否仍在原位置。'))
        self.timer=QTimer(self);self.timer.setTimerType(Qt.TimerType.PreciseTimer);self.timer.setInterval(8);self.timer.timeout.connect(self.tick);self.timer.start()
        self.memory_timer=QTimer(self);self.memory_timer.setInterval(3000);self.memory_timer.timeout.connect(self.persist_view);self.memory_timer.start()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _:self.changed.emit())
        if self.data['songs']:self.selectSong(min(self.data.get('last_song',0),len(self.data['songs'])-1))
        self.save()

    def save(self):
        self.data['settings']=self.settings;write_json(self.path,self.data)
        # Do not rebuild song delegates on selection, playback or job updates.
        signature=tuple((s['name'],s['duration'],s.get('baseline')) for s in self.data['songs'])
        if signature!=getattr(self,'library_signature',None):
            self.library_signature=signature;self.libraryChanged.emit()
    def remember_view(self):
        if self.song:self.song['view']=dict(position=self.t,span=self.span,low=self.low,high=self.high,source=self.source,detailSpan=getattr(self,'detail_span',20.))
    def persist_view(self):
        if self.song:
            before=self.song.get('view');self.remember_view()
            if before!=self.song['view']:self.save()
    def feedback(self,text):self.message=text;self.changed.emit()
    @Property('QVariantList',notify=libraryChanged)
    def songs(self):return [dict(index=i,name=s['name'].replace('+-+',' · '),duration=clock(s['duration'])) for i,s in enumerate(self.data['songs'])]
    @Property('QVariantList',notify=contentChanged)
    def jobs(self):return [dict(id=j['id'],name=Path(j['source']).stem,state=j['state'],message=j.get('message','')) for j in self.data['jobs'] if j['state'] not in ['complete','retried']]
    @Property('QVariantList',notify=contentChanged)
    def noteRows(self):return self.notes
    @Property('QVariantList',notify=contentChanged)
    def windows(self):return [dict(label=w['label']+'  '+clock(w['start']),start=w['start'],end=w['end']) for w in self.song.get('review_windows',[])] if self.song else []
    @Property('QVariantList',notify=contentChanged)
    def models(self):return [dict(key=k,label=LABELS[k],color=COLORS[k]) for k in self.series]
    @Property(str,constant=True)
    def inputUrl(self):return QUrl.fromLocalFile(str(DATA_ROOT/'input')).toString()
    @Property('QVariantMap',notify=changed)
    def state(self):
        active=next((n for n in self.notes if n['start']<=self.t<n['end']),None)
        job=self.active or self.display_job
        pitch='—'
        if self.series and (abs(self.t-self.readout_time)>=.12 or not self.state_playing()):
            times,values=self.series[self.primary];i=int(np.clip(np.searchsorted(times,self.t,side='right')-1,0,len(values)-1));v=values[i]
            if np.isfinite(v):
                tail=values[max(0,i-7):i+1];tail=tail[np.isfinite(tail)]
                # Do not smooth over a real semitone transition or fill a gap.
                nearby=tail[abs(tail-v)<.5];v=float(np.median(nearby)) if len(nearby) else v
                pitch=note(v)+f' {round((v-round(v))*100/5)*5:+d} 音分'
            self.readout_pitch=pitch;self.readout_time=self.t
        elif self.series:pitch=self.readout_pitch
        return dict(loaded=bool(self.song),selected=self.selected,title=self.song['name'].replace('+-+',' · ') if self.song else '你的歌声工作台',
          duration=self.song['duration'] if self.song else 0,position=self.t,time=clock(self.t),total=clock(self.song['duration']) if self.song else '00:00',
          playing=self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState,autoRange=self.auto,span=self.span,low=self.low,high=self.high,
          blocks=self.show_blocks,curve=self.show_curve,source=self.source,loop=self.loop,windowIndex=self.window_index,count=len(self.notes),pitch=pitch,
          mainNote=active['note'] if active else '—',message=self.message,settings=self.settings,
          availablePitchModels=[k for k,v in PITCH_MODES.items() if v in self.series],
          gameNotesAvailable=bool(getattr(self,'game_notes_available',False)),
          highQualityAvailable=self.high_quality_available,
          activeSeparation=self.song.get('algorithm',{}).get('separation','htdemucs') if self.song else '',
          separationCached=bool(self.song and self.settings['separationModel'] in self.song.get('analysis_versions',{})),
          songSeparationBusy=bool(self.song and any(j.get('target_id')==self.song.get('song_id') and j['state'] in ['queued','running'] for j in self.data['jobs'])),
          activeNoteMode='game' if self.settings['noteMode']=='game' and getattr(self,'game_notes_available',False) else 'classic',
          activePitchModel=next((k for k,v in PITCH_MODES.items() if v==getattr(self,'primary',None)),self.settings['pitchModel']),
          dark=self.settings['theme']=='dark' or (self.settings['theme']=='system' and QGuiApplication.styleHints().colorScheme()==Qt.ColorScheme.Dark),
          volume=self.settings['volume'],muted=self.muted,loopA=self.loop_a,loopB=self.loop_b,loopAText=clock(self.loop_a),loopBText=clock(self.loop_b),canUndo=bool(self.trash),
          job=bool(job),jobName=Path(job['source']).name if job else '',jobText=(' · '.join(filter(None,[job.get('message',''),job.get('computeStatus','')])) if job else ''),jobProgress=job.get('progress',0) if job else 0,
          running=bool(self.active),canRetry=bool(job and job['state'] in ['failed','cancelled','interrupted']))

    def state_playing(self):return self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState
    def apply_audio(self):
        self.output.setVolume(self.settings['volume']);self.vocal_output.setVolume(min(1,self.settings['volume']*self.vocal_boost))
        self.output.setMuted(self.muted or self.source!='original');self.vocal_output.setMuted(self.muted or self.source!='vocals')
    def vocal_ready(self,status):
        if status==QMediaPlayer.MediaStatus.BufferedMedia and getattr(self,'vocal_buffer_pending',False):
            self.vocal_buffer_pending=False;song=self.audio_song
            QTimer.singleShot(50,lambda:self.vocal_player.setPosition(self.player.position()) if not self.closing and self.audio_song is song else None)
        if not self.changing and self.vocal_pending and status in [QMediaPlayer.MediaStatus.LoadedMedia,QMediaPlayer.MediaStatus.BufferedMedia]:
            self.vocal_pending=False
            song=self.audio_song
            def start():
                if self.closing or self.audio_song is not song:return
                self.vocal_player.setPosition(self.player.position())
                if self.state_playing():self.vocal_player.play()
            QTimer.singleShot(0,start)
    @Slot(int)
    def previewPiano(self,midi):
        if not 21<=midi<=108:return
        try:
            if self.piano is None:self.preparePiano()
            if self.settings['pianoVolume']<=0:return
            self.piano.play(midi,110);self.preview_note=midi;self.preview_until=time.monotonic()+.85;self.changed.emit()
            QTimer.singleShot(860,self.changed.emit)
        except OSError:self.feedback('系统钢琴音源不可用，请检查 Windows 音频设备。')
    def preparePiano(self):
        if self.piano is None:
            from piano import Piano
            self.piano=Piano(self)
            self.piano.set_volume(self.settings['pianoVolume'])
            self.piano.failed.connect(lambda:self.feedback('系统钢琴音源不可用，请检查 Windows 音频设备。'))
            self.piano.played.connect(self.piano_highlight);self.piano.warm()
    @Slot(int)
    def piano_highlight(self,midi):
        self.preview_note=midi;self.preview_until=time.monotonic()+.85;self.changed.emit();QTimer.singleShot(860,self.changed.emit)

    def eventFilter(self,obj,event):
        if event.type() in [QEvent.Type.ShortcutOverride,QEvent.Type.KeyPress,QEvent.Type.KeyRelease] and event.key()==Qt.Key.Key_Space:
            if event.type()==QEvent.Type.KeyPress and not event.isAutoRepeat():self.togglePlay()
            event.accept();return True
        return False

    @Slot(str,'QVariant')
    def setting(self,key,value):
        if key not in self.settings:return
        if key in ['pitchModel','noteMode','pipelineVersion']:return
        if key=='separationModel':
            if value not in ['mel_bs','mel_roformer']:return
            if not self.high_quality_available:self.feedback('人声模型尚未安装。');return
        if key=='noteMode':
            if value not in ['game','classic']:return
            if value=='game' and self.song and not self.game_notes_available:return
            self.settings[key]=value
            if self.series:self.apply_pitch_model()
            self.save();self.changed.emit();return
        if key=='pitchModel':
            if value not in PITCH_MODES:return
            if self.series and PITCH_MODES[value] not in self.series:
                self.feedback('这首歌曲还没有此模型的结果。');return
            self.settings[key]=value
            if self.series:self.apply_pitch_model()
            self.save();self.changed.emit();return
        if key=='theme' and value not in ['system','light','dark']:return
        self.settings[key]=value;self.show_blocks=self.settings['blocks'];self.show_curve=self.settings['curve'];self.save();self.changed.emit()
    @Slot(float)
    def setVolume(self,value):
        self.settings['volume']=float(np.clip(value,0,1))
        if self.settings['volume']>0:self.muted=False
        self.apply_audio();self.save();self.changed.emit()
    @Slot(float)
    def setPianoVolume(self,value):
        self.settings['pianoVolume']=float(np.clip(value,0,1))
        if self.piano:self.piano.set_volume(self.settings['pianoVolume'])
        self.save();self.changed.emit()
    @Slot()
    def toggleMute(self):self.muted=not self.muted;self.apply_audio();self.changed.emit()
    @Slot('QVariantList')
    def deleteSongs(self,indices):
        targets=sorted(set(int(i) for i in indices if 0<=int(i)<len(self.data['songs'])))
        if not targets:return
        current=self.song;self.trash=[(i,self.data['songs'][i]) for i in targets]
        self.data['songs']=[s for i,s in enumerate(self.data['songs']) if i not in targets]
        if self.selected in targets:
            self.changing=True;self.player.stop();self.vocal_player.stop();self.player.setSource(QUrl());self.vocal_player.setSource(QUrl());self.audio_song=None;self.changing=False
            self.song=None;self.series={};self.notes=[];self.selected=-1;self.t=0.;self.loop=False;self.pending=None;self.buffer_seek=None;self.resume=False
            if self.data['songs']:self.selectSong(min(targets[0],len(self.data['songs'])-1))
        elif current:self.selected=next(i for i,s in enumerate(self.data['songs']) if s is current)
        self.data['last_song']=max(0,self.selected);self.save();self.contentChanged.emit();self.feedback(f'已移除 {len(targets)} 首歌曲，原文件保留。')
    @Slot()
    def undoDelete(self):
        if not self.trash:return
        current=self.song
        for i,s in self.trash:self.data['songs'].insert(min(i,len(self.data['songs'])),s)
        self.trash=[]
        if current:self.selected=next(i for i,s in enumerate(self.data['songs']) if s is current)
        else:self.selectSong(0)
        self.data['last_song']=max(0,self.selected);self.save();self.contentChanged.emit();self.feedback('已恢复歌曲。')
    @Slot(float,float)
    def setLoopRange(self,a,b):
        if not self.song:return
        duration=self.song['duration'];self.loop_a=float(np.clip(a,0,max(0,duration-.25)));self.loop_b=float(np.clip(b,self.loop_a+.25,duration));self.loop_initialized=True;self.changed.emit()
    @Slot()
    def prepareLoop(self):
        if self.song and not self.loop_initialized:self.setLoopRange(self.t,self.t+10)
    @Slot(str)
    def markLoop(self,edge):
        if edge=='a':self.setLoopRange(self.t,max(self.t+1,self.loop_b))
        else:self.setLoopRange(min(self.loop_a,max(0,self.t-1)),self.t)
    def tick(self):
        if not self.song or self.changing or self.player.playbackState()!=QMediaPlayer.PlaybackState.PlayingState:return
        if self.presentation_pending:return
        if self.player.mediaStatus() in [QMediaPlayer.MediaStatus.StalledMedia,QMediaPlayer.MediaStatus.InvalidMedia,QMediaPlayer.MediaStatus.NoMedia,QMediaPlayer.MediaStatus.EndOfMedia]:return
        self.t=min(self.song['duration'],self.presentation.value(time.monotonic()))
        if self.loop and self.t>=self.loop_b:self.seek(self.loop_a)
        else:self.changed.emit()
    def playback_changed(self,state):
        if state==QMediaPlayer.PlaybackState.PlayingState:
            self.vocal_player.setPosition(self.player.position());self.vocal_player.play()
        elif state==QMediaPlayer.PlaybackState.PausedState:self.vocal_player.pause()
        else:self.vocal_player.stop()
        if not self.changing:
            self.presentation.reset(self.player.position()/1000,time.monotonic())
            self.t=self.player.position()/1000
            self.presentation_pending=state==QMediaPlayer.PlaybackState.PlayingState
        self.changed.emit()

    @Slot(int)
    def selectSong(self,index):
        if not 0<=index<len(self.data['songs']):return
        if self.song is self.data['songs'][index]:return
        self.remember_view()
        if not getattr(self,'analysis_swap',False):
            self.changing=True;self.player.stop();self.vocal_player.stop();self.changing=False
        song=self.data['songs'][index]
        try:
            series={}
            curves=dict(song['curves'])
            from pitch_experiments import result_folder
            experiment=result_folder(song)
            for k in ['rmvpe_tracked','fcpe']:
                if k not in curves and (experiment/'report.json').is_file() and (experiment/(k+'.csv')).is_file():curves[k]=str(experiment/(k+'.csv'))
            for p in song['audio'].values():
                if not Path(p).is_file():raise FileNotFoundError(p)
            primary=next(k for k in ['rmvpe_tracked','rmvpe_vocals','tuned_vocals','crepe_full'] if k in curves and Path(curves[k]).is_file())
            from presentation_results import read_curve
            times,values,_=read_curve(curves[primary])
            if not len(times):raise ValueError('Empty pitch timeline')
            series[primary]=(times,values)
            notes=[]
            if song.get('main_notes') and Path(song['main_notes']).is_file():
                notes=json.loads(Path(song['main_notes']).read_text(encoding='utf-8'))['notes']
        except Exception:
            self.feedback('这份结果的文件不完整，请选择其他歌曲或重新分析。');return
        self.song=song;self.selected=index;self.series=series;self.curve_paths=curves;self.primary=primary;self.notes=notes;self.compare=set();self.t=0.;self.loop=False;self.window_index=0
        self.curve_reliability={};self.mode_notes={primary:notes};self.note_onsets=None
        self.game_notes_available=False;self.game_notes=[];self.game_mode_notes={};self.prepared_primary=None
        self.loudness=(np.array([0.]),np.array([.5]));refresh=False
        try:
            self.install_presentation(song.get('presentation',{}))
        except (OSError,ValueError,KeyError,TypeError):
            refresh=True
            # Retain the old cached blocks while a separate worker refreshes.
            from game_notes import display_cache_path
            try:
                path=display_cache_path(song)
                if path.is_file():
                    self.game_notes=json.loads(path.read_text(encoding='utf-8'))['notes']
                    self.game_notes_available=True
                    self.game_mode_notes[primary]=self.game_notes
            except (OSError,ValueError,KeyError):pass
        self.apply_pitch_model()
        if refresh:self.queue_presentation(dict(song,curves=curves),song['curves'].get('rmvpe_tracked'))
        self.loop_a=0.;self.loop_b=min(10,song['duration']);self.loop_initialized=False;self.anchor_t=0.;self.clock_anchor.restart()
        self.data['last_song']=index;self.save();self.contentChanged.emit()
        self.message=''
        view=song.get('view',{})
        self.span=float(np.clip(view.get('span',20),0,300));self.t=float(np.clip(view.get('position',0),0,song['duration']))
        self.detail_span=self.clamp_span(view.get('detailSpan',self.span or 20))
        if self.span:self.span=self.clamp_span(self.span)
        self.source=view.get('source','vocals') if view.get('source','vocals') in song['audio'] else 'vocals'
        self.fitRange()
        if view.get('high',0)>view.get('low',0):self.low=float(view['low']);self.high=float(view['high'])
        self.setPitchWidth(self.high-self.low)
        self.readout_time=-1.;self.readout_pitch='—';self.preview_note=None
        self.presentation.reset(self.t,time.monotonic());self.setSource(self.source);self.changed.emit()

    def install_presentation(self,value):
        from presentation_results import load
        notes,evidence,loudness=load(value)
        primary=value['primary']
        if primary not in self.series:raise ValueError('Missing primary curve')
        if len(evidence[0])!=len(self.series[primary][0]) or not np.allclose(evidence[0],self.series[primary][0],atol=1e-6):
            raise ValueError('Presentation no longer matches curve')
        self.prepared_primary=primary;self.mode_notes[primary]=notes
        self.curve_reliability[primary]=evidence;self.loudness=loudness
        self.game_notes_available=value.get('game_available',False)
        self.game_mode_notes[primary]=notes
        self.vocal_boost=float(value.get('gain',1.))

    def queue_presentation(self,song,native_curve):
        token=(song['song_id'],song['audio']['vocals'],native_curve)
        if self.presentation_active and self.presentation_active[0]==token:return
        if any(t==token for t,_ in self.presentation_queue):return
        self.presentation_queue.append((token,json.loads(json.dumps(song))))
        self.start_presentation()

    def start_presentation(self):
        if self.closing or self.presentation_process or not self.presentation_queue:return
        token,song=self.presentation_queue.pop(0);self.presentation_active=(token,song)
        folder=DATA_ROOT/'work'/'presentation-jobs';folder.mkdir(parents=True,exist_ok=True)
        job=uuid.uuid4().hex;source=folder/(job+'-input.json');target=folder/(job+'-result.json')
        write_json(source,song)
        process=QProcess(self);self.presentation_process=process
        process.setWorkingDirectory(str(ROOT))
        process.setStandardOutputFile(str(folder/(job+'.log')))
        process.setStandardErrorFile(str(folder/(job+'-error.log')))
        process.finished.connect(lambda code,*args:self.presentation_finished(process,token,target,code))
        process.errorOccurred.connect(lambda e:self.presentation_finished(process,token,target,-1) if e==QProcess.ProcessError.FailedToStart else None)
        process.start(worker_python(),['-u',str(ROOT/'presentation_results.py'),'--song-file',str(source),'--result-file',str(target)])

    def presentation_finished(self,process,token,target,code):
        if self.presentation_process is not process:return
        self.presentation_process=None;self.presentation_active=None;process.deleteLater()
        if not self.closing and code==0:
            song=next((s for s in self.data['songs'] if
                       (s['song_id'],s['audio']['vocals'],s['curves'].get('rmvpe_tracked'))==token),None)
            if song:
                try:
                    from presentation_results import load
                    value=json.loads(target.read_text(encoding='utf-8'));load(value)
                    if self.song is song:
                        self.install_presentation(value);self.apply_pitch_model();self.apply_audio()
                    song['presentation']=value;song['main_notes']=value['notes']
                    self.save()
                except (OSError,ValueError,KeyError,TypeError):
                    if self.song is song:self.feedback('音符整理未完成，暂时显示原有结果。')
        elif not self.closing and self.song and self.song['song_id']==token[0]:
            self.feedback('音符整理未完成，暂时显示原有结果。')
        self.start_presentation()

    def ensure_series(self,key):
        if key not in self.series and key in getattr(self,'curve_paths',{}):
            from presentation_results import read_curve
            times,values,_=read_curve(self.curve_paths[key])
            self.series[key]=(times,values)

    def apply_pitch_model(self):
        key=PITCH_MODES.get(self.settings['pitchModel'],'rmvpe_tracked')
        self.ensure_series(key)
        if key not in self.series:key=next(k for k in ['rmvpe_tracked','rmvpe_vocals','tuned_vocals','crepe_full'] if k in self.series)
        if key not in self.mode_notes:
            # Only explicit legacy/experimental modes compute on demand.
            from main_notes import extract
            self.mode_notes[key]=extract(*self.series[key],onset_times=self.note_onsets)
        self.primary=key;self.notes=self.mode_notes[key];self.compare=set()
        if self.settings['noteMode']=='game' and key in self.game_mode_notes:
            self.notes=self.game_mode_notes[key]
        self.readout_time=-1.;self.readout_pitch='—';self.revision+=1
        self.contentChanged.emit();self.changed.emit()

    def x_range(self):
        if self.drag_view is not None:return self.drag_view
        duration=self.song['duration'] if self.song else 20
        width=duration if self.span==0 else min(self.span,duration)
        left=max(0,min(self.t-width*.3,duration-width));return left,left+max(.01,width)
    @Slot()
    def fitRange(self):
        if not self.song:return
        a,b=self.x_range();times,values=self.series[self.primary];v=values[(times>=a)&(times<=b)];v=v[np.isfinite(v)]
        if not len(v):v=values[np.isfinite(values)]
        if len(v):
            self.low=math.floor(float(v.min()))-2;self.high=math.ceil(float(v.max()))+2
            if self.high-self.low<12:
                middle=(self.high+self.low)/2;self.low=middle-6;self.high=middle+6
        self.changed.emit()
    @Slot(bool)
    def setAutoRange(self,on):self.auto=on;self.fitRange() if on else self.changed.emit()
    @Slot(float)
    def pitchZoom(self,factor):
        self.setPitchWidth((self.high-self.low)*factor)
    @Slot(float)
    def pitchMove(self,delta):self.setPitchCenter((self.low+self.high)/2+delta)
    @Slot(float)
    def setPitchWidth(self,width):
        center=float(np.clip((self.low+self.high)/2,4,123))
        width=float(np.clip(width,8,min(60,2*center,2*(127-center))))
        self.auto=False;self.low=center-width/2;self.high=center+width/2;self.changed.emit()
    @Slot(float)
    def setPitchCenter(self,center):
        width=float(np.clip(self.high-self.low,8,60));center=float(np.clip(center,width/2,127-width/2))
        self.auto=False;self.low=center-width/2;self.high=center+width/2;self.changed.emit()
    def clamp_span(self,value):
        maximum=min(300.,self.song['duration']) if self.song else 300.
        return float(np.clip(value,min(3.,maximum),maximum))
    @Slot(float)
    def setSpan(self,value):
        self.auto=False
        if value==0:
            if self.span:self.detail_span=self.span
            self.span=0.
        else:self.span=self.clamp_span(value);self.detail_span=self.span
        self.changed.emit()
    @Slot()
    def adaptPitchRange(self):
        if not self.song or not self.series:return
        times,values=self.series[self.primary]
        mask=(times>=self.t)&np.isfinite(values)&(values>=0)&(values<=127)
        # Use most of the remaining performance, rather than a transient frame.
        pitches=values[mask]
        if len(pitches)<30:pitches=values[np.isfinite(values)&(values>=0)&(values<=127)]
        if not len(pitches):return
        low,high=np.quantile(pitches,[.05,.95])
        width=float(np.clip(np.ceil(high+2)-np.floor(low-2),12,60))
        center=float(np.clip((np.floor(low-2)+np.ceil(high+2))/2,width/2,127-width/2))
        self.auto=False;self.low=center-width/2;self.high=center+width/2;self.changed.emit()
    @Slot()
    def toggleOverview(self):self.setSpan(getattr(self,'detail_span',20.) if self.span==0 else 0.)
    @Slot(str,int)
    def adjustView(self,kind,steps):
        if not self.song:return
        if kind=='time':
            value=self.span or min(300.,self.song['duration'])
            for _ in range(abs(steps)):
                step=.5 if value<=10 else 1. if value<=30 else 5.
                value=self.clamp_span(value+step*(1 if steps>0 else -1))
            self.setSpan(value)
        elif kind=='width':self.setPitchWidth(self.high-self.low+steps)
        elif kind=='center':self.pitchMove(steps)
    @Slot(bool)
    def showBlocks(self,on):self.show_blocks=on;self.changed.emit()
    @Slot(bool)
    def showCurve(self,on):self.show_curve=on;self.changed.emit()
    @Slot(str,bool)
    def compareModel(self,key,on):
        if on:self.ensure_series(key)
        if key in self.series:self.compare.add(key) if on else self.compare.discard(key)
        self.changed.emit()
    @Slot(float,int)
    def wheel(self,steps,modifiers):
        mods=Qt.KeyboardModifier(modifiers)
        if mods & Qt.KeyboardModifier.ControlModifier:
            self.setSpan(float(np.clip((self.span or (self.song['duration'] if self.song else 20))*1.2**(-steps),3,300)))
        elif mods & Qt.KeyboardModifier.AltModifier:self.pitchZoom(1.15**(-steps))
        elif mods & Qt.KeyboardModifier.ShiftModifier:self.pitchMove(steps*2)
        else:self.loop=False;self.seek(self.t-steps*.5)

    @Slot()
    def togglePlay(self):
        if not self.song:return
        if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:self.player.pause()
        else:
            if self.loop and not self.loop_a<=self.t<self.loop_b:self.seek(self.loop_a)
            self.presentation.reset(self.t,time.monotonic());self.player.play()
    @Slot(float)
    def seek(self,seconds):
        if not self.song:return
        value=round(float(np.clip(seconds,0,self.song['duration']))*1000);self.revision+=1
        if self.pending is not None:self.pending=value
        if self.buffer_seek is not None:self.buffer_seek=value
        self.player.setPosition(value);self.position(value,True)
        self.vocal_player.setPosition(value);self.readout_time=-1.
    def position(self,ms,force=False):
        if self.changing:return
        audio_t=ms/1000
        if force or self.player.playbackState()!=QMediaPlayer.PlaybackState.PlayingState:
            self.presentation.reset(audio_t,time.monotonic());self.t=audio_t
        elif self.presentation_pending:
            self.presentation.reset(audio_t,time.monotonic());self.t=audio_t;self.presentation_pending=False
        else:self.t=self.presentation.feed(audio_t,time.monotonic())
        if self.song and self.loop and self.state['playing'] and self.t>=self.loop_b:self.seek(self.loop_a);return
        if self.auto:self.fitRange()
        else:self.changed.emit()
    @Slot(str)
    def setSource(self,source):
        if source not in ['original','vocals']:return
        self.source=source
        if not self.song:return
        if self.audio_song is self.song:
            self.apply_audio();self.changed.emit();return
        self.audio_song=self.song
        try:self.vocal_boost=float(self.song.get('presentation',{}).get('gain',1.))
        except (OSError,ValueError,RuntimeError):self.vocal_boost=1.
        if getattr(self,'analysis_swap',False):
            self.t=self.player.position()/1000
            self.presentation.reset(self.t,time.monotonic())
            self.swap_vocal_source(self.song['audio']['vocals'])
            self.apply_audio();self.changed.emit();return
        self.revision+=1;self.pending=round(self.t*1000);self.buffer_seek=self.pending;self.resume=self.state['playing'];self.changing=True
        self.player.stop();self.vocal_player.stop();self.vocal_pending=True;self.vocal_player.setSource(QUrl.fromLocalFile(self.song['audio']['vocals']));self.player.setSource(QUrl.fromLocalFile(self.song['audio']['original']));self.apply_audio();self.changing=False;self.changed.emit()
        self.media(self.player.mediaStatus())
        self.vocal_ready(self.vocal_player.mediaStatus())
    def swap_vocal_source(self,path):
        # Keep the original player as the uninterrupted transport clock.
        # Reload only the vocal source; vocal_ready rejoins the live position.
        self.vocal_pending=True
        self.vocal_buffer_pending=True
        self.vocal_player.stop()
        self.vocal_player.setSource(QUrl.fromLocalFile(path))
        self.vocal_ready(self.vocal_player.mediaStatus())
    def media(self,status):
        if self.changing:return
        if status in [QMediaPlayer.MediaStatus.LoadedMedia,QMediaPlayer.MediaStatus.BufferedMedia] and self.pending is not None:
            position=self.pending;self.pending=None;self.player.setPosition(position);self.vocal_player.setPosition(position)
            if self.resume:self.player.play()
        if status==QMediaPlayer.MediaStatus.BufferedMedia and self.buffer_seek is not None:
            pos=self.buffer_seek;self.buffer_seek=None;revision=self.revision
            QTimer.singleShot(50,lambda:self.player.setPosition(pos) if revision==self.revision else None)
    @Slot(int)
    def selectWindow(self,index):self.window_index=index;self.changed.emit()
    @Slot()
    def jumpWindow(self):
        if self.windows:self.seek(self.windows[self.window_index]['start'])
    @Slot(bool)
    def setLoop(self,on):
        self.loop=on
        if on and self.song and not self.loop_a<=self.t<self.loop_b:self.seek(self.loop_a)
        self.changed.emit()
    @Slot(str)
    def exportNotes(self,url):
        if not self.song:return
        try:
            from main_notes import export_notes
            export_notes(local_path(url),self.notes);self.feedback('音符列表已导出。')
        except Exception:self.feedback('导出失败，请选择可写入的文件位置。')
    @Slot(str)
    def saveRemark(self,text):
        if not self.song:return
        p=self.folder/'listening-notes.json';rows=json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
        rows.append(dict(song=self.song['name'],seconds=self.t,audio=self.source,comment=text));write_json(p,rows);self.feedback('已保存此刻的试听备注。')
    @Slot(str)
    def importSaved(self,url):
        try:
            songs=json.loads(local_path(url).read_text(encoding='utf-8'))['songs']
            for s in songs:
                for p in list(s['audio'].values())+list(s['curves'].values()):
                    if not Path(p).is_file():raise ValueError('missing')
            known={s['audio']['original'] for s in self.data['songs']}
            for s in songs:
                if s['audio']['original'] not in known:self.data['songs'].append(s);known.add(s['audio']['original'])
            self.save();self.contentChanged.emit()
            if self.data['songs']:self.selectSong(len(self.data['songs'])-1)
        except Exception:self.feedback('无法打开结果，请保留 index.json 引用的音频及分析文件。')

    @Slot(str)
    def enqueue(self,url):
        path=local_path(url).resolve()
        if not path.is_file() or path.suffix.lower() not in FORMATS:self.feedback('请选择有效的音频文件。');return
        try:stat=path.stat();signature=[stat.st_size,stat.st_mtime_ns]
        except OSError:self.feedback('无法读取音频文件，请检查权限或文件是否仍存在。');return
        matching=lambda p:os.path.normcase(str(Path(p).resolve()))==os.path.normcase(str(path))
        for j in self.data['jobs']:
            if matching(j['source']) and j['state'] in ['queued','running']:
                self.feedback('这首歌已在分析队列中。');return
            if matching(j['source']) and j['state']=='complete' and j.get('signature')==signature:
                if any(matching(s.get('source','')) for s in self.data['songs']):self.feedback('这首歌已有分析结果，请在歌曲库中打开。');return
        for s in self.data['songs']:
            if s.get('source') and matching(s['source']) and not any(matching(j['source']) for j in self.data['jobs']):
                self.feedback('这首歌已在歌曲库中。');return
        self.data['jobs'].append(dict(id=uuid.uuid4().hex,source=str(path),signature=signature,separation=self.settings['separationModel'],state='queued',progress=0,message='等待分析'))
        self.save();self.contentChanged.emit();self.start_next()
    def install_analysis(self,song,target_id):
        index=next((i for i,s in enumerate(self.data['songs']) if s.get('song_id')==target_id),None)
        if index is None:return False
        old=self.data['songs'][index]
        if self.song is old:self.remember_view()
        versions=dict(old.get('analysis_versions',{}))
        snapshot=lambda s:{k:v for k,v in s.items() if k not in ['analysis_versions','view']}
        versions[old.get('algorithm',{}).get('separation','htdemucs')]=snapshot(old)
        versions[song.get('algorithm',{}).get('separation','htdemucs')]=snapshot(song)
        current=self.song is old
        new=dict(song,song_id=target_id,view=dict(old.get('view',{})),analysis_versions=versions)
        self.data['songs'][index]=new
        if current:
            loop_state=(self.loop,self.loop_a,self.loop_b,self.loop_initialized)
            self.analysis_swap=True
            try:self.song=None;self.selectSong(index)
            finally:self.analysis_swap=False
            self.loop,self.loop_a,self.loop_b,self.loop_initialized=loop_state
        self.save();return True
    @Slot()
    def applySeparation(self):
        self.apply_song_separation(self.settings['separationModel'])
    @Slot(bool)
    def setSongHarmony(self,enabled):
        self.apply_song_separation('mel_bs' if enabled else 'mel_roformer')
    def apply_song_separation(self,mode):
        if not self.song:return
        target=self.song['song_id']
        if mode==self.song.get('algorithm',{}).get('separation','htdemucs'):return
        if any(j.get('target_id')==target and j['state'] in ['running','queued'] for j in self.data['jobs']):
            self.feedback('这首歌已在分析队列中。');return
        cached=self.song.get('analysis_versions',{}).get(mode)
        if cached and all(Path(p).is_file() for p in list(cached['audio'].values())+list(cached['curves'].values())+[cached['main_notes']]):
            self.install_analysis(cached,target);self.feedback('已切换人声分离结果。');return
        if not self.high_quality_available:self.feedback('人声模型尚未安装。');return
        source=Path(self.song.get('source',''))
        if not source.is_file():source=Path(self.song['audio']['original'])
        if not source.is_file():self.feedback('原音频已不存在，请重新导入。');return
        self.data['jobs'].append(dict(id=uuid.uuid4().hex,source=str(source),target_id=target,
            separation=mode,state='queued',progress=0,message='等待重新分析'))
        self.save();self.contentChanged.emit();self.start_next();self.changed.emit()
    @Slot(str)
    def cancelQueued(self,key):
        job=next((j for j in self.data['jobs'] if j['id']==key and j['state']=='queued'),None)
        if job:job.update(state='cancelled',message='已移出队列，可重试');self.save();self.contentChanged.emit();self.changed.emit()
    @Slot(str)
    def removeJob(self,key):
        job=next((j for j in self.data['jobs'] if j['id']==key),None)
        if not job:return
        if job is self.active:
            job['remove_after_stop']=True;self.cancel();return
        self.data['jobs'].remove(job)
        if self.display_job is job:self.display_job=None
        self.save();self.contentChanged.emit();self.changed.emit()
    @Slot()
    def removeDisplayedJob(self):
        job=self.active or self.display_job
        if job:self.removeJob(job['id'])
    def start_next(self):
        if self.closing or self.active or (self.process and (not self.reusable_worker or self.worker_closing)):return
        job=next((j for j in self.data['jobs'] if j['state']=='queued'),None)
        if not job:
            if self.process and self.reusable_worker and not self.worker_closing:
                self.worker_closing=True;self.process.closeWriteChannel()
            return
        self.active=job;self.display_job=job;job.update(state='running',message='准备分析');self.save();self.buffer=''
        self.result_file=self.folder/(job['id']+'-result.json');self.log_file=self.folder/(job['id']+'.log')
        if self.process is None:
            p=QProcess(self);self.process=p;self.worker_closing=False
            env=QProcessEnvironment.systemEnvironment();env.insert('PYTHONIOENCODING','utf-8');env.insert('PYTHONUNBUFFERED','1');p.setProcessEnvironment(env)
            p.setWorkingDirectory(str(ROOT));p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            p.readyReadStandardOutput.connect(lambda proc=p:self.read_progress() if self.process is proc else None)
            p.finished.connect(lambda code,*args,proc=p:self.worker_exited(proc,code))
            p.errorOccurred.connect(lambda e,proc=p:self.worker_exited(proc,-1) if e==QProcess.ProcessError.FailedToStart else None)
            if self.reusable_worker:p.start(worker_python(),['-u',str(ROOT/'analysis_worker.py')])
            else:p.start(worker_python(),['-u',str(self.worker),job['source'],'--standalone','--result-file',str(self.result_file),'--separation',job.get('separation','htdemucs')])
        if self.reusable_worker:
            request=dict(id=job['id'],source=job['source'],result_file=str(self.result_file),separation=job.get('separation','htdemucs'))
            self.process.write((json.dumps(request)+'\n').encode('utf-8'))
        self.contentChanged.emit();self.changed.emit()

    def worker_exited(self,process,code):
        if self.process is not process:return
        self.read_progress()
        if self.active:self.finished(code)
        else:
            self.process=None;self.worker_closing=False;process.deleteLater();QTimer.singleShot(0,self.start_next)

    def read_progress(self):
        if not self.process:return
        text=bytes(self.process.readAllStandardOutput()).decode('utf-8',errors='replace')
        with self.log_file.open('a',encoding='utf-8') as f:f.write(text)
        self.buffer+=text
        while '\n' in self.buffer:
            line,self.buffer=self.buffer.split('\n',1)
            if line.startswith('VPL_JOB_DONE ') and self.reusable_worker and self.active:
                try:
                    done=json.loads(line[13:])
                    if done.get('id')==self.active['id']:self.finished(int(done['code']),job_done=True)
                except (ValueError,TypeError,KeyError):pass
            elif line.startswith('VPL_EVENT ') and self.active:
                try:self.active.update(json.loads(line[10:]));self.changed.emit()
                except (ValueError,TypeError):pass
    def finished(self,code,*args,job_done=False):
        if not self.process or not self.active:return
        if not job_done:self.read_progress()
        if not self.active:return
        p=self.process;job=self.active;self.active=None
        if not job_done:self.process=None
        if job['state']=='cancelled':job['message']='已取消，可重试'
        elif code==0 and self.result_file.exists():
            try:
                song=json.loads(self.result_file.read_text(encoding='utf-8'))['song']
                for path in list(song['audio'].values())+list(song['curves'].values())+[song['main_notes']]:
                    if not Path(path).exists():raise ValueError('missing')
                if job.get('target_id'):
                    target=next((s for s in self.data['songs'] if s.get('song_id')==job['target_id']),None)
                    if target:song['name']=target['name'];song['source']=target.get('source',job['source'])
                    installed=self.install_analysis(song,job['target_id'])
                    job.update(state='complete',message='分析完成，已保存' if installed else '歌曲已移除，未恢复到歌曲库',progress=100)
                else:
                    song['song_id']=uuid.uuid4().hex;self.data['songs'].append(song);job.update(state='complete',message='分析完成，已保存',progress=100);self.selectSong(len(self.data['songs'])-1)
            except Exception:job.update(state='failed',message='结果未完整保存，请重试')
        else:
            log=self.log_file.read_text(encoding='utf-8',errors='replace')[-12000:] if self.log_file.exists() else ''
            reason='音频读取或分析失败，可重新导入或重试'
            if 'out of memory' in log.lower():reason='显存或内存不足，关闭其他占用较大的程序后重试'
            elif 'PermissionError' in log:reason='文件访问受限，请检查文件权限后重试'
            elif 'No space left' in log or 'disk full' in log.lower():reason='磁盘空间不足，清理后重试'
            elif 'FileNotFoundError' in log:reason='音频或模型文件缺失，请检查后重试'
            job.update(state='failed',message=reason)
        if job.get('remove_after_stop'):
            self.data['jobs']=[j for j in self.data['jobs'] if j is not job]
            if self.display_job is job:self.display_job=None
        self.save();self.contentChanged.emit();self.changed.emit()
        if job_done:
            if code!=0 or not any(j['state']=='queued' for j in self.data['jobs']):
                self.worker_closing=True;p.closeWriteChannel()
        else:
            self.worker_closing=False;p.deleteLater()
        QTimer.singleShot(0,self.start_next)
    def stop_worker(self):
        if not self.process:return
        pid=int(self.process.processId())
        if sys.platform=='win32' and pid:
            try:subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],creationflags=subprocess.CREATE_NO_WINDOW,capture_output=True,timeout=5)
            except (OSError,subprocess.TimeoutExpired):pass
        if self.process.state()!=QProcess.ProcessState.NotRunning:self.process.kill()
    @Slot()
    def cancel(self):
        if self.active:self.active.update(state='cancelled',message='正在取消');self.save();self.contentChanged.emit();self.changed.emit();self.stop_worker()
    @Slot(str)
    def viewJob(self,key):
        if not self.active:self.display_job=next((j for j in self.data['jobs'] if j['id']==key),None);self.changed.emit()
    @Slot()
    def retry(self):
        job=self.display_job
        if job and job['state'] in ['failed','cancelled','interrupted']:
            if not Path(job['source']).is_file():self.feedback('原音频已不存在，请重新导入。');return
            replacement={k:v for k,v in job.items() if k not in ['id','state','message','progress','remove_after_stop']}
            replacement.update(id=uuid.uuid4().hex,state='queued',message='等待重试',progress=0)
            job['state']='retried';self.data['jobs'].append(replacement);self.save();self.contentChanged.emit();self.start_next()
    @Slot()
    def shutdown(self):
        self.closing=True;self.presentation_queue.clear()
        if self.presentation_process:
            self.presentation_process.blockSignals(True);self.presentation_process.kill();self.presentation_process.waitForFinished(3000);self.presentation_process=None
        self.remember_view();self.memory_timer.stop();self.changing=True;self.player.stop();self.changing=False
        self.vocal_player.stop()
        if self.piano:self.piano.close()
        if self.process:
            if self.active:self.active.update(state='interrupted',message='分析已中断，可重试')
            self.process.blockSignals(True);self.stop_worker();self.process.waitForFinished(3000);self.process=None
        for j in self.data['jobs']:
            if j['state']=='queued':j.update(state='interrupted',message='等待任务已中断，可重试')
        self.save()

class PitchView(QQuickPaintedItem):
    controllerChanged=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self._controller=None;self.setAntialiasing(True);self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton);self.setAcceptHoverEvents(True);self.hover_point=None;self.curve_cache={};self.cache_song=None;self.drag=None
    @Property(QObject,notify=controllerChanged)
    def controller(self):return self._controller
    @controller.setter
    def controller(self,value):
        self._controller=value
        if value:value.changed.connect(self.update);value.contentChanged.connect(self.update)
        self.controllerChanged.emit();self.update()
    def geometry_values(self):
        return 68,50,max(1,self.width()-80),max(1,self.height()-62)
    def curve_samples(self,key,span,pixels):
        b=self._controller;times,values=b.series[key]
        step=(times[-1]-times[0])/max(1,len(times)-1) if len(times)>1 else .01
        stride=lod_stride(span,pixels,step)
        overview=span>=40
        if overview:stride=max(stride,int(span/max(1,pixels)/step*3))
        cache_key=(id(values),stride,overview)
        if cache_key not in self.curve_cache:
            # At most a handful of fixed levels for the selected recording.
            if self.cache_song is not b.song:self.curve_cache.clear();self.cache_song=b.song
            self.curve_cache[cache_key]=(melody_outline if overview else stable_envelope)(times,values,stride)
        return self.curve_cache[cache_key]
    def draw_curve(self,p,times,values,x,y,dark):
        b=self._controller
        levels=np.interp(times,*b.loudness)
        reliability=b.curve_reliability.get(b.primary)
        emphasis=np.interp(times,*reliability) if b.settings.get('cleanCurve',True) and reliability is not None else np.ones(len(times))
        buckets=[[] for _ in range(64)];previous=None;previous_level=.5;previous_emphasis=1.
        for t,v,level,weight in zip(times,values,levels,emphasis):
            if not np.isfinite(v):previous=None;continue
            point=QPointF(x(t),y(v))
            if previous is not None:
                bucket=min(15,int((level+previous_level)*.5*16))
                category=min(3,max(0,int(round(((weight+previous_emphasis)*.5-.35)/.65*3))))
                buckets[category*16+bucket].append(QLineF(previous,point))
            previous=point;previous_level=level;previous_emphasis=weight
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i,lines in enumerate(buckets):
            level=(i%16)/15;weight=.35+.65*(i//16)/3
            color=QColor('#8bc4ff' if dark else '#175b9f');color.setAlphaF((.68+.30*level)*weight)
            span=b.span or b.song['duration'];scale=1 if span<40 else .72
            pen=QPen(color,(1.2+3.2*level)*scale*(.65+.35*weight));pen.setCapStyle(Qt.PenCapStyle.RoundCap);p.setPen(pen);p.drawLines(lines)
    def draw_block(self,p,rect,dark,selected=False):
        fill=QLinearGradient(rect.topLeft(),rect.bottomLeft())
        fill.setColorAt(0,QColor(('#485d73' if selected else '#354455') if dark else ('#d2e4f5' if selected else '#e3ecf5')))
        fill.setColorAt(1,QColor(('#40556c' if selected else '#303e4e') if dark else ('#c9def2' if selected else '#dce7f1')))
        p.setBrush(fill);p.setPen(QPen(QColor(('#657e98' if selected else '#485b70') if dark else ('#9db9d4' if selected else '#bdcfdf')),.65))
        radius=min(4,rect.height()/2);p.drawRoundedRect(rect,radius,radius)
    def long_curve_layer(self,span,w,h,color):
        b=self._controller;dpr=self.window().devicePixelRatio() if self.window() else 1.
        dark=b.state['dark'];key=(id(b.series[b.primary][1]),span,w,h,b.low,b.high,dpr,b.show_blocks,b.show_curve,dark,b.settings.get('cleanCurve',True))
        if getattr(self,'layer_key',None)==key:return self.layer
        width=math.ceil(b.song['duration']/span*w)+2
        layer=QImage(math.ceil(width*dpr),math.ceil((h+2)*dpr),QImage.Format.Format_ARGB32_Premultiplied);layer.setDevicePixelRatio(dpr);layer.fill(0)
        painter=QPainter(layer);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if b.show_blocks:
            for n in b.notes:
                nh=max(3,min(20,h*.64/(b.high-b.low)))
                self.draw_block(painter,QRectF(n['start']/span*w,(b.high-n['midi'])/(b.high-b.low)*h-nh/2,max(1.5,n['duration']/span*w),nh),dark)
        if b.show_curve:
            times,values=self.curve_samples(b.primary,span,w)
            self.draw_curve(painter,times,values,lambda t:t/span*w,lambda v:(b.high-v)/(b.high-b.low)*h,dark)
        painter.end();self.layer_key=key;self.layer=layer
        return layer
    def paint(self,p):
        b=self._controller
        if not b or not b.song:return
        state=b.state;dark=state['dark'];fg='#e0e7f4' if dark else '#344761';muted='#9eaec5' if dark else '#72809a';grid='#2b2e34' if dark else '#edf0f3';band='#23262c' if dark else '#f7f8fa';bg='#202226' if dark else '#ffffff'
        x0,y0,w,h=self.geometry_values();left,right=b.x_range();span=min(b.span or b.song['duration'],b.song['duration'])
        x=lambda t:x0+(t-left)/span*w;y=lambda m:y0+(b.high-m)/(b.high-b.low)*h
        p.fillRect(self.boundingRect(),QColor(bg));p.setFont(QFont('Microsoft YaHei',9))
        visible=[n for n in b.notes if n['end']>=left and n['start']<=right]
        active=next((n for n in visible if n['start']<=b.t<n['end']),None)
        hovered=None
        if self.hover_point and b.settings['hoverNotes'] and b.show_blocks:
            hx,hy=self.hover_point
            if x0<=hx<=x0+w and y0<=hy<=y0+h:
                hovered=next((n for n in visible if x(n['start'])-2<=hx<=x(n['end'])+2 and abs(hy-y(n['midi']))<=max(6,h*.4/(b.high-b.low))),None)
        highlighted=hovered or (active if b.settings['liveNotes'] else None)
        p.save();p.setClipRect(QRectF(0,y0,self.width(),h))
        for midi in range(math.floor(b.low),math.ceil(b.high)+1):
            row=QRectF(x0,y(midi+.5),w,h/(b.high-b.low))
            if midi%12 in [1,3,6,8,10]:p.fillRect(row,QColor(band))
            p.setPen(QPen(QColor(grid),.5));p.drawLine(QPointF(x0,y(midi)),QPointF(x0+w,y(midi)))
            key_color=('#29364c' if dark else '#eaf0f8') if midi%12 in [1,3,6,8,10] else bg
            p.fillRect(QRectF(3,y(midi+.5)+.5,55,h/(b.high-b.low)-1),QColor(key_color))
            selected=(highlighted and midi==highlighted['midi']) or (b.preview_note==midi and time.monotonic()<b.preview_until)
            if selected:p.fillRect(QRectF(3,y(midi+.5),55,h/(b.high-b.low)),QColor('#3c6795' if dark else '#d0e5ff'))
            step=max(1,math.ceil((b.high-b.low)*13/h))
            if (midi%step==0 or selected) and y0+8<=y(midi)<=y0+h-8:
                p.setPen(QColor('#91c6ff' if dark else '#0069d2') if selected else QColor(muted));p.drawText(QRectF(3,y(midi)-9,50,18),Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter,note(midi))
        # A fixed grid anchored to recording time, no variable edge labels.
        raw=span/8;spacing=10**math.floor(math.log10(max(raw,.001)))
        spacing*=next(v for v in [1,2,5,10] if v*spacing>=raw)
        for tick in range(math.floor(left/spacing),math.ceil(right/spacing)+1):
            p.setPen(QPen(QColor(grid),.5));p.drawLine(QPointF(x(tick*spacing),y0),QPointF(x(tick*spacing),y0+h))
        p.restore();p.save();p.setClipRect(QRectF(x0,y0,w,h))
        if b.loop:p.fillRect(QRectF(x(b.loop_a),y0,x(b.loop_b)-x(b.loop_a),h),QColor('#124c97ff'))
        color=QColor(fg)
        cached_layer=span>=40 and b.song['duration']/span*w<16000
        if cached_layer:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,True)
            p.drawImage(QPointF(x0-left/span*w,y0),self.long_curve_layer(span,w,h,color))
        else:
            if b.show_blocks:
                for n in visible:
                    nh=max(3,min(20,h*.64/(b.high-b.low)))
                    rect=QRectF(x(n['start']),y(n['midi'])-nh/2,max(1.5,x(n['end'])-x(n['start'])),nh)
                    self.draw_block(p,rect,dark,n is hovered or n is active)
            if b.show_curve:
                times,values=self.curve_samples(b.primary,span,w);a,c=np.searchsorted(times,[left,right])
                self.draw_curve(p,times[max(0,a-1):c+1],values[max(0,a-1):c+1],x,y,dark)
        if hovered:
            pen=QPen(QColor('#77b8ff' if dark else '#318ce8'),1);pen.setStyle(Qt.PenStyle.DashLine);p.setPen(pen)
            p.drawLine(QPointF(x0,y(hovered['midi'])),QPointF(x(hovered['start']),y(hovered['midi'])))
        if b.loop:
            for edge,label in [(b.loop_a,'A'),(b.loop_b,'B')]:
                p.setPen(QPen(QColor('#6badff' if dark else '#0071e3'),1.3));p.drawLine(QPointF(x(edge),y0),QPointF(x(edge),y0+h))
                p.setBrush(QColor('#6badff' if dark else '#0071e3'));p.drawRoundedRect(QRectF(x(edge)-8,y0,16,20),4,4)
                p.setPen(QColor('#101834' if dark else '#ffffff'));p.drawText(QRectF(x(edge)-8,y0,16,20),Qt.AlignmentFlag.AlignCenter,label)
        p.setPen(QPen(QColor('#60aaff' if dark else '#0071e3'),1.3));p.drawLine(QPointF(x(b.t),y0),QPointF(x(b.t),y0+h));p.restore()
        labels=[]
        if b.settings['liveNotes']:labels.append(('主音',state['mainNote'],''))
        if b.settings['liveCurve']:
            parts=state['pitch'].split(' ',1);labels.append(('曲线',parts[0],parts[1] if len(parts)>1 else ''))
        if labels:
            box_w=116*len(labels);box_h=48
            bx=max(x0,min(x(b.t)-box_w/2,x0+w-box_w));by=max(2,y0-box_h-8)
            p.setPen(QPen(QColor('#4b5665' if dark else '#d4dee8'),.8));p.setBrush(QColor('#ed29333f' if dark else '#f4f4f8fc'));p.drawRoundedRect(QRectF(bx,by,box_w,box_h),14,14)
            for i,(caption,value,detail) in enumerate(labels):
                cx=bx+i*116+12
                font=QFont('Microsoft YaHei');font.setPixelSize(11);p.setFont(font);p.setPen(QColor(muted))
                p.drawText(QRectF(cx,by+5,94,14),Qt.AlignmentFlag.AlignVCenter,caption)
                font.setPixelSize(18);font.setBold(True);p.setFont(font);p.setPen(QColor('#b3d7ff' if dark else '#174c82'))
                p.drawText(QRectF(cx,by+20,52,24),Qt.AlignmentFlag.AlignVCenter,value)
                font.setPixelSize(11);font.setBold(False);p.setFont(font);p.setPen(QColor(muted))
                p.drawText(QRectF(cx+50,by+20,50,24),Qt.AlignmentFlag.AlignVCenter,detail)
                if i:
                    p.setPen(QPen(QColor('#46505c' if dark else '#dae2eb'),.7));p.drawLine(QPointF(cx-12,by+10),QPointF(cx-12,by+box_h-10))
    def mousePressEvent(self,event):
        b=self._controller
        if b and b.song:
            a,c=b.x_range();x0,y0,w,h=self.geometry_values();px,py=event.position().x(),event.position().y()
            if 0<=px<x0 and y0<=py<=y0+h:
                b.previewPiano(int(round(b.high-(py-y0)/h*(b.high-b.low))));event.accept();return
            if not (x0<=px<=x0+w and y0<=py<=y0+h):event.ignore();return
            position=float(np.clip(a+(px-x0)/w*(c-a),0,b.song['duration']))
            mode='new'
            if b.loop:
                for edge,name in [(b.loop_a,'a'),(b.loop_b,'b')]:
                    if abs(x0+(edge-a)/(c-a)*w-px)<8:mode=name;break
            self.drag=dict(x=px,start=position,end=position,mode=mode,moved=False,resume=b.state_playing())
            b.drag_view=(a,c)
            if b.state_playing():b.player.pause()
            event.accept()
    def mouseDoubleClickEvent(self,event):
        self.mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if not self.drag:return
        b=self._controller;a,c=b.x_range();x0,y0,w,h=self.geometry_values();px=event.position().x()
        self.drag['end']=float(np.clip(a+(px-x0)/w*(c-a),0,b.song['duration']))
        if abs(px-self.drag['x'])>=6:self.drag['moved']=True
        if self.drag['moved']:
            t=self.drag['end'];mode=self.drag['mode']
            if mode=='a':b.setLoopRange(min(t,b.loop_b-.25),b.loop_b)
            elif mode=='b':b.setLoopRange(b.loop_a,max(t,b.loop_a+.25))
            else:b.setLoopRange(min(t,self.drag['start']),max(t,self.drag['start']))
            b.loop=True;b.changed.emit()
        event.accept()
    def mouseReleaseEvent(self,event):
        if not self.drag:return
        b=self._controller;drag=self.drag;self.drag=None;b.drag_view=None
        if drag['moved']:b.setLoop(True);b.seek(b.loop_a)
        else:b.seek(drag['start'])
        if drag['resume']:b.player.play()
        b.changed.emit();event.accept()
    def hoverMoveEvent(self,event):
        self.hover_point=(event.position().x(),event.position().y())
        self.setCursor(Qt.CursorShape.PointingHandCursor if event.position().x()<self.geometry_values()[0] else Qt.CursorShape.CrossCursor);self.update()
    def hoverLeaveEvent(self,event):self.hover_point=None;self.update()
    def wheelEvent(self,event):
        steps=(event.angleDelta().y() or event.angleDelta().x())/120
        if not steps:steps=(event.pixelDelta().y() or event.pixelDelta().x())/40
        if self._controller:self._controller.wheel(steps,event.modifiers().value)
        event.accept()

from PySide6.QtCore import QPointF,QLineF
def create_engine(controller):
    qmlRegisterType(PitchView,'VocalPitch',1,0,'PitchView')
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('backend',controller)
    engine.load(QUrl.fromLocalFile(str(ROOT/'qml/Main.qml')));return engine
def main():
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('VocalPitchLab.Desktop')
    app=QGuiApplication(sys.argv);app.setOrganizationName('VocalPitchLab');app.setApplicationName('VocalPitchLab')
    app.setWindowIcon(QIcon(str(ROOT/'assets/vocalpitch.ico')))
    for name in ['msyh.ttc','msyhbd.ttc']:QFontDatabase.addApplicationFont(str((Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts')/name))
    app.setFont(QFont('Microsoft YaHei',10));folder=DATA_ROOT/'library';folder.mkdir(exist_ok=True)
    lock=QLockFile(str(folder/'app.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(0):return 0
    controller=Controller();app.installEventFilter(controller);engine=create_engine(controller)
    QTimer.singleShot(500,controller.preparePiano)
    if not engine.rootObjects():return 1
    app.aboutToQuit.connect(controller.shutdown);return app.exec()
if __name__=='__main__':sys.exit(main())
