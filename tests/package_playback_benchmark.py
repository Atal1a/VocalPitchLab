"""Repeatable native playback benchmark with isolated data and optional CPU/WARP pressure."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def distribution(values):
    values = sorted(values)
    if not values:
        return dict(count=0, median_ms=None, p95_ms=None, max_ms=None, over_50_ms=0, over_100_ms=0)
    def percentile(fraction):
        position = (len(values)-1)*fraction
        lo, hi = math.floor(position), math.ceil(position)
        return values[lo]+(values[hi]-values[lo])*(position-lo)
    return dict(count=len(values), median_ms=round(percentile(.5), 3),
                p95_ms=round(percentile(.95), 3), max_ms=round(values[-1], 3),
                over_50_ms=sum(x > 50 for x in values), over_100_ms=sum(x > 100 for x in values))


def synthetic_library(folder, duration=240):
    import csv
    import wave
    import numpy as np
    from vocalpitchlab.analysis.game_notes import REFINEMENT_VERSION, RECONCILE_SETTINGS
    from vocalpitchlab.analysis.curve_reliability import NOTE_EVIDENCE_VERSION, VERSION
    from vocalpitchlab.analysis.main_notes import current_settings
    from vocalpitchlab.analysis.presentation_results import PRESENTATION_VERSION
    folder.mkdir(parents=True)
    audio = folder/'tone.wav'
    rate = 22050
    block = (np.sin(np.arange(rate)*2*np.pi*220/rate)*600).astype('<i2').tobytes()
    with wave.open(str(audio), 'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate)
        for _ in range(duration):
            stream.writeframesraw(block)
    times = np.arange(0, duration, .01)
    songs = []
    for index in range(2):
        values = 65+4*np.sin(times*2+index)+.2*np.sin(times*35)
        values[(times % 4) > 3.5] = np.nan
        curve = folder/f'curve-{index}.csv'
        with curve.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream);writer.writerow(['time_seconds', 'midi_float'])
            writer.writerows((f'{t:.4f}', f'{v:.6f}' if np.isfinite(v) else '') for t, v in zip(times, values))
        notes = [dict(start=float(t), end=float(t+.2), duration=.2, midi=round(65+4*np.sin(t*2+index)),
                      note='F4', note_id=i+1) for i,t in enumerate(np.arange(0, duration-.2, .3))]
        note_file = folder/f'notes-{index}.json'
        note_file.write_text(json.dumps(dict(notes=notes)), encoding='utf-8')
        evidence = folder/f'evidence-{index}.npz';loudness = folder/f'loudness-{index}.npz'
        np.savez_compressed(evidence, time=times, weight=.6+.4*np.cos(times))
        np.savez_compressed(loudness, time=times, level=.5+.4*np.sin(times))
        presentation = dict(version=PRESENTATION_VERSION, refinement=REFINEMENT_VERSION,
                            evidence_version=NOTE_EVIDENCE_VERSION, display_version=VERSION,
                            settings=RECONCILE_SETTINGS, fallback_settings=current_settings(),
                            primary='rmvpe_tracked', notes=str(note_file), evidence=str(evidence),
                            loudness=str(loudness), gain=1., game_available=False)
        songs.append(dict(name=f'Synthetic {index+1}', song_id=f'synthetic-{index}', duration=duration,
                          audio=dict(original=str(audio), vocals=str(audio)), curves=dict(rmvpe_tracked=str(curve)),
                          main_notes=str(note_file), presentation=presentation,
                          view=dict(position=30., span=20., low=48., high=84.)))
    return dict(songs=songs, settings={})


def worker(args):
    case = args.case_dir.resolve()
    data_root = case/'data'
    os.environ.update(VPL_DATA_DIR=str(data_root), VPL_MODEL_DIR=str(args.app_root/'models'),
                      QT_QPA_PLATFORM='windows', QSG_RHI_BACKEND='d3d11', QSG_INFO='1',
                      QT_SCALE_FACTOR=str(args.scale/args.native_dpr), QT_SCALE_FACTOR_ROUNDING_POLICY='PassThrough',
                      QSG_RHI_PREFER_SOFTWARE_RENDERER='1' if args.renderer == 'warp' else '0')
    os.environ.pop('QT_QUICK_BACKEND', None);os.environ.pop('QT_SCREEN_SCALE_FACTORS', None)
    sys.path.insert(0, str(ROOT/'installer'))
    from performance_limits import apply_worker_limits
    limits, job_handle = apply_worker_limits(args.cpu_cores, args.cpu_core_budget)
    sys.path.insert(0, str(args.app_root))
    import numpy as np
    import psutil
    from PySide6.QtCore import QObject, QPointF, QEventLoop, QTimer, Qt, qInstallMessageHandler
    from PySide6.QtGui import QGuiApplication, QFont, QFontDatabase, QImage, QWindow
    from vocalpitchlab.ui.app import Controller, PitchView, create_engine
    from vocalpitchlab.analysis.presentation_results import load
    source = json.loads(args.fixture.read_text(encoding='utf-8'))
    songs = source['songs']
    for song in songs:
        load(song['presentation'])  # Refuse background migration of source results.
    library = data_root/'library';library.mkdir(parents=True,exist_ok=True)
    settings = dict(source.get('settings', {}), volume=0., pianoVolume=0., theme='dark')
    (library/'index.json').write_text(json.dumps(dict(songs=songs, settings=settings)), encoding='utf-8')
    messages, warnings = [], []
    callback_errors = []
    original_excepthook = sys.excepthook
    def record_exception(kind, error, trace):
        import traceback
        callback_errors.append(''.join(traceback.format_exception(kind,error,trace)))
        original_excepthook(kind,error,trace)
    sys.excepthook = record_exception
    def capture(kind, context, text):
        messages.append(text)
        if '.qml:' in text or 'Traceback' in text:
            warnings.append(text)
    qInstallMessageHandler(capture)
    app = QGuiApplication([])
    for name in ['msyh.ttc', 'msyhbd.ttc']:
        QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
    app.setFont(QFont('Microsoft YaHei',10))
    paints = []
    original_paint = PitchView.paint
    def measured_paint(self, painter):
        start = time.perf_counter()
        try:
            return original_paint(self, painter)
        finally:
            paints.append((time.perf_counter()-start)*1000)
    PitchView.paint = measured_paint
    b = Controller(library, bootstrap=False)
    b.muted = True;b.apply_audio()
    engine = create_engine(b)
    if not engine.rootObjects():
        raise RuntimeError('QML window did not load')
    window = engine.rootObjects()[0]
    flags = Qt.WindowType.Tool|Qt.WindowType.WindowDoesNotAcceptFocus
    flags |= Qt.WindowType.WindowStaysOnTopHint if args.show_window else Qt.WindowType.WindowStaysOnBottomHint
    window.setFlags(flags)
    window.setWidth(args.width);window.setHeight(args.height);window.show()
    view = window.findChild(QObject, 'pitchView')
    def wait(ms):
        loop = QEventLoop();QTimer.singleShot(ms, loop.quit);loop.exec()
    def until(predicate, timeout=20):
        start = time.monotonic()
        while not predicate():
            if time.monotonic()-start > timeout:
                raise TimeoutError('Playback readiness timed out')
            wait(40)
    def screenshot(name):
        image = window.grabWindow()
        if image.isNull():
            raise RuntimeError('Empty native screenshot')
        image.save(str(case/name))
        return image
    try:
        until(lambda: b.pending is None)
        b.setSpan(args.span);b.seek(min(30., b.song['duration']*.25));wait(150)
        api = str(window.rendererInterface().graphicsApi())
        if 'Direct3D11' not in api:
            raise RuntimeError('Benchmark requires the complete Direct3D 11 interface')
        warp_used = any('Microsoft Basic Render Driver' in m and i+1 < len(messages) and
                        'using this adapter' in messages[i+1] for i,m in enumerate(messages))
        if args.renderer == 'warp' and not warp_used:
            raise RuntimeError('WARP was requested but not confirmed by the renderer')
        screenshot('initial.png')
        revision = [0];notified = [time.perf_counter()]
        def changed():
            revision[0] += 1;notified[0] = time.perf_counter()
        b.frameChanged.connect(changed)
        presented, latency, phase, responses, rss = [], [], [], [], []
        seen = [-1]
        def swapped():
            if seen[0] != revision[0]:
                now = time.perf_counter();seen[0] = revision[0]
                presented.append(now);latency.append((now-notified[0])*1000)
                phase.append((b.t-b.player.position()/1000-max(0,time.monotonic()-b.presentation.wall)*b.presentation.rate)*1000)
        window.frameSwapped.connect(swapped)
        probe = QTimer();probe.setInterval(20);probe.setTimerType(Qt.TimerType.PreciseTimer)
        due = [time.perf_counter()+.020]
        def responsive():
            now = time.perf_counter();responses.append(max(0,(now-due[0])*1000));due[0] = now+.020
            process = psutil.Process()
            processes = [process]+process.children(recursive=True)
            total = 0
            for p in processes:
                try:total += p.memory_info().rss
                except psutil.Error:pass
            rss.append(total)
        probe.timeout.connect(responsive)
        starting_song = b.song
        before_position = b.player.position();b.togglePlay()
        until(lambda: b.player.position() > before_position+200)
        if args.analysis_audio:
            import shutil
            analysis_input = case/('analysis-input'+args.analysis_audio.suffix)
            shutil.copy2(args.analysis_audio,analysis_input)
            b.enqueue(str(analysis_input))
            if not b.data['jobs']:
                raise RuntimeError('Background analysis did not start: '+b.message)
        wait(300)
        layers = getattr(view,'layers',None)
        cold_cache = layers.statistics() if layers is not None else {}
        if layers is not None:
            layers.sync_ms.clear();layers.tile_build_ms.clear()
        paints.clear();presented.clear();latency.clear();phase.clear();responses.clear();rss.clear()
        due[0] = time.perf_counter()+.020;probe.start()
        start_cpu = time.process_time();start = time.perf_counter();wait(round(args.seconds*1000))
        elapsed = time.perf_counter()-start;cpu = time.process_time()-start_cpu
        probe.stop();intervals = np.diff(presented)*1000
        if len(intervals) < 5:
            raise RuntimeError('Too few actual chart presentations; expose the test window and retry')
        results = dict(span_seconds=args.span, requested_scale=args.scale, effective_dpr=window.devicePixelRatio(),
                       window_size=[window.width(),window.height()], seconds=elapsed,
                       renderer=api, warp_confirmed=warp_used, limits=limits,
                       host=dict(logical_cpus=psutil.cpu_count(), ram_bytes=psutil.virtual_memory().total),
                       frame_intervals=distribution(intervals.tolist()), paint_cost=distribution(paints),
                       presentation_delay=distribution(latency), event_loop_delay=distribution(responses),
                       max_absolute_clock_phase_ms=round(max(map(abs,phase),default=0),3),
                       cpu_seconds=round(cpu,4), cpu_percent_one_core=round(100*cpu/elapsed,2),
                       peak_tree_rss_bytes=max(rss,default=0),
                       analysis_jobs=[dict(state=j['state'],message=j.get('message','')) for j in b.data['jobs']],
                       analysis_replaced_playback=b.song is not starting_song,
                       cache=getattr(layers,'statistics',lambda:{})(),cold_cache=cold_cache)
        results['app_source_sha256'] = {name:hashlib.sha256((args.app_root/name).read_bytes()).hexdigest()
                                        for name in ['vocalpitchlab/ui/app.py','vocalpitchlab/ui/plot_layers.py','qml/Main.qml'] if (args.app_root/name).exists()}
        results['validation_complete'] = False
        (case/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        if b.state_playing():b.togglePlay()
        if b.song is not starting_song:
            b.selectSong(0);until(lambda:b.pending is None)
        interactions = []
        def action(name, callback, predicate):
            swapped_at = []
            def done():swapped_at.append(time.perf_counter())
            window.frameSwapped.connect(done)
            try:
                start = time.perf_counter();callback();mutation = time.perf_counter()-start
                until(predicate);state_ready = time.perf_counter()-start
                until(lambda:bool(swapped_at))
                interactions.append(dict(action=name, mutation_ms=round(mutation*1000,3),
                                         state_ready_ms=round(state_ready*1000,3),
                                         first_presentation_ms=round((swapped_at[0]-start)*1000,3)))
                wait(40)
            finally:window.frameSwapped.disconnect(done)
        action('seek', lambda:b.seek(42.), lambda:abs(b.t-42.) < .05)
        zoom_span = 10. if b.span == 3 else 3.
        action('zoom', lambda:b.setSpan(zoom_span), lambda:abs(b.span-zoom_span) < .01)
        action('overview', b.toggleOverview, lambda:b.span == 0)
        b.setSpan(args.span);b.seek(30.);b.setLoopRange(30.,30.4);b.setLoop(True);b.togglePlay();wait(1000)
        if not 30. <= b.t < 30.55:
            raise RuntimeError('Loop did not remain within its bounds')
        b.setLoop(False);window.setVisibility(QWindow.Visibility.Minimized);wait(150)
        if b.timer.isActive():
            raise RuntimeError('Minimized window kept its presentation timer running')
        position = b.player.position();wait(250)
        if b.player.position() <= position:
            raise RuntimeError('Audio stopped while minimized')
        window.setVisibility(QWindow.Visibility.Windowed);wait(200)
        if not b.timer.isActive():
            raise RuntimeError('Presentation timer did not resume')
        b.togglePlay();b.setSource('original');b.setSource('vocals')
        if len(songs)>1:
            b.selectSong(1);until(lambda:b.pending is None);b.selectSong(0);until(lambda:b.pending is None)
        b.setSpan(args.span);b.seek(50.);wait(100)
        image = screenshot('final.png').convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        origin = view.mapToScene(QPointF(68,50));corner = view.mapToScene(QPointF(view.width()-12,view.height()-12))
        scale = image.width()/window.width()
        pixels = np.frombuffer(image.constBits(),np.uint8).reshape(image.height(),image.bytesPerLine()//4,4)
        plot = pixels[round(origin.y()*scale):round(corner.y()*scale),round(origin.x()*scale):round(corner.x()*scale)].astype(int)
        if ((plot[:,:,0]-plot[:,:,2]>20)&(plot[:,:,1]-plot[:,:,2]>10)).sum() < 100:
            raise RuntimeError('Pitch content missing from the native screenshot')
        if warnings or callback_errors:
            raise RuntimeError('UI errors: '+repr(warnings+callback_errors))
        results.update(interactions=interactions, loop_hide_restore_source_and_song_switch=True, qml_warnings=[],validation_complete=True)
        (case/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    finally:
        b.shutdown();window.close()
        (case/'renderer.log').write_text('\n'.join(messages),encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--app-root',type=Path,default=ROOT)
    parser.add_argument('--library',type=Path)
    parser.add_argument('--song-index',type=int,default=0)
    parser.add_argument('--seconds',type=float,default=5.)
    parser.add_argument('--spans',type=float,nargs='+',default=[20.])
    parser.add_argument('--scales',type=float,nargs='+',default=[1.])
    parser.add_argument('--renderer',choices=['native','warp'],default='native')
    parser.add_argument('--cpu-cores',type=int)
    parser.add_argument('--cpu-core-budget',type=float)
    parser.add_argument('--repeat',type=int,default=1)
    parser.add_argument('--width',type=int,default=1380)
    parser.add_argument('--height',type=int,default=900)
    parser.add_argument('--analysis-audio',type=Path)
    parser.add_argument('--show-window',action='store_true',help='Keep the test window above existing windows without taking keyboard focus')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--fixture',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--case-dir',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--span',type=float,help=argparse.SUPPRESS)
    parser.add_argument('--scale',type=float,help=argparse.SUPPRESS)
    parser.add_argument('--native-dpr',type=float,default=1.,help=argparse.SUPPRESS)
    args = parser.parse_args();args.app_root = args.app_root.resolve()
    if args.seconds < 1 or args.repeat < 1 or any(x < 0 for x in args.spans) or any(x <= 0 for x in args.scales):
        parser.error('Use at least one second, positive repeats/scales, and nonnegative spans')
    if args.worker:
        return worker(args)
    if os.name != 'nt':
        parser.error('Full interface benchmarks require native Windows Direct3D 11')
    if not args.output:
        parser.error('--output is required')
    output = args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(args.app_root))
    os.environ['VPL_DATA_DIR'] = str(output/'fixture-data')
    source_hash = None
    if args.library:
        library = args.library.resolve();source_hash = hashlib.sha256(library.read_bytes()).hexdigest()
        source = json.loads(library.read_text(encoding='utf-8'))
        songs = source['songs']
        if not 0 <= args.song_index < len(songs):
            parser.error('--song-index is outside the source library')
        source['songs'] = [songs[args.song_index]]+[song for i,song in enumerate(songs) if i != args.song_index][:1]
        source['jobs'] = []
    else:
        source = synthetic_library(output/'fixture')
    fixture = output/'fixture.json';fixture.write_text(json.dumps(source),encoding='utf-8')
    os.environ.pop('QT_SCALE_FACTOR',None);os.environ.pop('QT_SCREEN_SCALE_FACTORS',None)
    os.environ['QT_QPA_PLATFORM']='windows'
    from PySide6.QtGui import QGuiApplication
    probe = QGuiApplication([]);native_dpr = probe.primaryScreen().devicePixelRatio()
    records = []
    for scale in args.scales:
        for span in args.spans:
            for repeat in range(args.repeat):
                case = output/f'scale-{scale:g}-span-{span:g}-run-{repeat+1}';case.mkdir()
                command = [sys.executable,str(Path(__file__).resolve()),'--worker','--fixture',str(fixture),
                           '--case-dir',str(case),'--app-root',str(args.app_root),'--scale',str(scale),
                           '--span',str(span),'--seconds',str(args.seconds),'--renderer',args.renderer,
                           '--native-dpr',str(native_dpr),
                           '--width',str(args.width),'--height',str(args.height)]
                if args.show_window:command += ['--show-window']
                for flag,value in [('--cpu-cores',args.cpu_cores),('--cpu-core-budget',args.cpu_core_budget),('--analysis-audio',args.analysis_audio)]:
                    if value is not None:
                        command += [flag,str(value)]
                with (case/'worker.log').open('w',encoding='utf-8') as log:
                    completed = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=max(180,args.seconds*5+90))
                if completed.returncode:
                    raise RuntimeError(f'Benchmark failed; see {case / "worker.log"}')
                record = json.loads((case/'result.json').read_text(encoding='utf-8'))
                records.append(record)
                print(json.dumps(dict(scale=scale,span=span,run=repeat+1,frame_intervals=record['frame_intervals'],paint_cost=record['paint_cost'],cpu_percent_one_core=record['cpu_percent_one_core'])),flush=True)
    if args.library and hashlib.sha256(library.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError('The original library changed during the benchmark')
    (output/'summary.json').write_text(json.dumps(dict(
        context=dict(input='existing_library' if args.library else 'synthetic',
                     cpu_limits_are_pressure_not_old_cpu_emulation=True,ram_limit_applied=False,
                     frame_count='one presentation per unique playback notification; duplicate swaps excluded',
                     gpu_driver_and_vm_results_do_not_establish_minimum_hardware=True),runs=records),indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
