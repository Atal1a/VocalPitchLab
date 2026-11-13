"""English translations for the desktop interface and worker messages."""
from PySide6.QtCore import QCoreApplication, QTranslator, Slot
from PySide6.QtQml import QQmlApplicationEngine


LANGUAGES = ('zh-CN', 'en')

ENGLISH = {
    '界面语言': 'Language',
    '导入歌曲': 'Import songs',
    '音频或视频 (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma *.aiff *.mp4 *.mov *.m4v)':
        'Audio or video files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma *.aiff *.mp4 *.mov *.m4v)',
    '＋ 导入歌曲': '+ Import songs',
    '歌曲库': 'Song library',
    '完成': 'Done',
    '批量管理': 'Manage',
    '全选': 'Select all',
    '移除 %1': 'Remove %1',
    '只移出歌曲库，保留原文件': 'Remove from the library and keep the original files',
    '删除': 'Delete',
    '取消分析并删除任务': 'Cancel analysis and delete the task',
    '删除任务记录': 'Delete the task from the list',
    '撤销移除': 'Undo removal',
    '设置': 'Settings',
    '时间': 'Time',
    '整首': 'Whole song',
    '%1 秒': '%1 s',
    '音域跨度': 'Pitch span',
    '%1 八度': '%1 oct',
    '%1 半音': '%1 st',
    '音域中心': 'Pitch center',
    '恢复时间跨度': 'Restore the previous time span',
    '显示整首': 'Show the whole song',
    '自适应': 'Fit pitch',
    '待重试': 'Ready to retry',
    '排队中': 'Queued',
    '取消': 'Cancel',
    '重试': 'Retry',
    '拖入一首歌': 'Drop a song here',
    '选择音频或视频': 'Choose audio or video',
    '暂停': 'Pause',
    '播放': 'Play',
    '空格': 'Space',
    '分离人声': 'Isolated vocals',
    '原曲': 'Original',
    '导出音轨': 'Export tracks',
    '正在导出…': 'Exporting…',
    '保存音轨': 'Save track',
    'WAV 音频 (*.wav)': 'WAV audio (*.wav)',
    '人声': 'Vocals',
    '主唱': 'Lead vocals',
    '伴奏': 'Instrumental',
    '和声': 'Backing vocals',
    '和声与伴奏': 'Backing vocals and instrumental',
    '和声分离 · 处理中': 'Separating backing vocals…',
    '和声分离：开': 'Harmony separation on',
    '和声分离：关': 'Harmony separation off',
    '循环中': 'Looping',
    '循环': 'Loop',
    '静音': 'Muted',
    '音量': 'Volume',
    '将当前位置设为循环起点': 'Set the loop start to the current position',
    '将当前位置设为循环终点': 'Set the loop end to the current position',
    '精调': 'Fine tune',
    '整首范围': 'Full song range',
    '精调模式放大 A–B 附近，方便拖动边界': 'Zoom in around A and B to adjust the loop boundaries',
    '停止循环': 'Stop loop',
    '开始循环': 'Start loop',
    '钢琴试听音量': 'Piano preview volume',
    '兼容播放': 'Playback compatibility',
    '歌曲无声时可开启，重启软件后生效。': 'Enable if songs play without sound. Restart to apply.',
    '外观': 'Appearance',
    '随系统': 'System',
    '浅色': 'Light',
    '深色': 'Dark',
    '降低运行负载': 'Reduce graphics load',
    '关闭界面模糊和阴影，即时生效。': 'Turn off blur and shadows immediately.',
    '功能选项': 'Analysis and display',
    '音频分离': 'Audio separation',
    '人声分离': 'Vocal separation',
    '和声分离': 'Harmony separation',
    '此设置用于新导入的歌曲。电脑性能较低时，可关闭两项，直接用原曲分析音高。这样更快，但准确率可能下降。': (
        'These settings apply to new imports. On slower computers, turn both off to analyze pitch '
        'from the original mix. Analysis will be faster, and pitch detection may be less accurate.'
    ),
    '主要音符': 'Main notes',
    '细节曲线': 'Detailed pitch curve',
    '弱化不可靠曲线': 'Dim low-confidence pitch',
    '悬浮高亮与对齐线': 'Highlight notes and show guides on hover',
    '播放线旁的主音高': 'Show main note at the playhead',
    '播放线旁的曲线音高': 'Show pitch curve value at the playhead',
    '空格 播放 / 暂停 · 滚轮 定位\n拖动图表 框选循环 · 按住左侧音名 钢琴试听\nShift + 滚轮 上下移动音域\nCtrl + 滚轮 缩放时间 · Alt + 滚轮 缩放音域': (
        'Space to play or pause. Scroll to seek.\n'
        'Drag on the chart to select a loop. Hold a note label to hear it.\n'
        'Shift + scroll moves the pitch range up or down.\n'
        'Ctrl + scroll zooms time. Alt + scroll zooms pitch.'
    ),
    '撤销': 'Undo',
    '从歌曲库移除': 'Remove from library',
    '滚轮微调 · 左右拖动调整 · Shift 拖动精调': 'Scroll or drag to adjust. Hold Shift while dragging for finer control.',
    '主音': 'Main note',
    '曲线': 'Pitch curve',
    '{cents:+d} 音分': '{cents:+d} cents',
    'CREPE 完整版': 'CREPE Full',
    'CREPE 轻量版': 'CREPE Tiny',
    '调参候选': 'Tuned candidate',
    'RMVPE 连续': 'RMVPE tracked',
    '上次分析已中断，可重试': 'The last analysis was interrupted. You can retry it.',
    '选择或拖入歌曲，开始分析。': 'Choose or drop a song to start analysis.',
    '音频无法播放，请检查结果文件是否仍在原位置。': 'Unable to play the audio. Check that the result files are still in place.',
    '你的歌声工作台': 'Vocal workspace',
    '系统钢琴音源不可用，请检查 Windows 音频设备。': 'Piano preview is unavailable. Check your Windows audio device.',
    '兼容播放设置已保存，重启软件后生效。': 'Playback compatibility saved. Restart VocalPitchLab to apply it.',
    '人声模型尚未安装。': 'The vocal separation model is missing.',
    '和声分离模型尚未安装。': 'The harmony separation model is missing.',
    '这首歌曲还没有此模型的结果。': 'This song has no results for this model yet.',
    '已移除 {count} 首歌曲，原文件保留。': 'Removed songs from the library ({count}). The original files are still in place.',
    '已恢复歌曲。': 'Restored songs to the library.',
    '这份结果的文件不完整，请选择其他歌曲或重新分析。': 'Some result files are missing. Choose another song or run the analysis again.',
    '音符整理未完成，暂时显示原有结果。': 'Note processing could not finish. The previous results are still shown.',
    '音符列表已导出。': 'Note list exported.',
    '导出失败，请选择可写入的文件位置。': 'Export failed. Choose a location you can write to.',
    '音轨已导出。': 'Track exported.',
    '没有可导出的分离音轨。': 'No separated tracks are available to export.',
    '歌曲已切换，请重新选择音轨。': 'The song changed. Choose a track again.',
    '请使用 .wav 文件扩展名。': 'Use the .wav file extension.',
    '请选择其他文件名，以保留原音频和分离结果。': 'Choose a different filename to keep the original audio and separation results.',
    '无法导出音轨，请检查音频和保存位置。': 'Unable to export the track. Check the audio files and save location.',
    '已保存此刻的试听备注。': 'Listening note saved at the current position.',
    '无法打开结果，请保留 index.json 引用的音频及分析文件。': 'Unable to open the result. Check the audio and analysis files listed in index.json.',
    '请选择支持的音频或视频文件。': 'Choose a supported audio or video file.',
    '这个文件没有音轨，请换一个文件。': 'This file has no audio track. Choose another file.',
    '这个文件包含多段音轨，将分析默认音轨。': 'This file has several audio tracks. The default track will be analyzed.',
    '无法读取音频文件，请检查权限或文件是否仍存在。': 'Unable to read the audio file. Check that it exists and that you have access.',
    '这首歌已在分析队列中。': 'This song is already in the analysis queue.',
    '这首歌已有分析结果，请在歌曲库中打开。': 'This song has already been analyzed. Open it from the library.',
    '这首歌已在歌曲库中。': 'This song is already in the library.',
    '等待分析': 'Waiting for analysis',
    '已切换人声分离结果。': 'Switched vocal separation results.',
    '原音频已不存在，请重新导入。': 'The original audio is missing. Import it again.',
    '等待重新分析': 'Waiting to analyze again',
    '已移出队列，可重试': 'Removed from the queue. You can retry it.',
    '准备分析': 'Preparing analysis',
    '已取消，可重试': 'Canceled. You can retry it.',
    '分析完成，已保存': 'Analysis complete and saved',
    '歌曲已移除，未恢复到歌曲库': 'The song was removed from the library',
    '结果未完整保存，请重试': 'Could not save all results. Try again.',
    '音频读取或分析失败，可重新导入或重试': 'Unable to read or analyze the audio. Import it again or retry.',
    '显存或内存不足，关闭其他占用较大的程序后重试': 'GPU or system memory is low. Close other apps and retry.',
    '文件访问受限，请检查文件权限后重试': 'File access denied. Check permissions and retry.',
    '磁盘空间不足，清理后重试': 'Disk space is low. Free up space and retry.',
    '音频或模型文件缺失，请检查后重试': 'An audio or model file is missing. Check the files and retry.',
    '正在取消': 'Canceling',
    '等待重试': 'Waiting to retry',
    '分析已中断，可重试': 'Analysis interrupted. You can retry it.',
    '等待任务已中断，可重试': 'Queued analysis interrupted. You can retry it.',
    '分析完成，结果已保存': 'Analysis complete and saved',
    '读取音频': 'Reading audio',
    '提取人声': 'Extracting vocals',
    '提取高质量人声': 'Extracting high-quality vocals',
    '分离和声': 'Separating backing vocals',
    '识别人声音高': 'Detecting vocal pitch',
    '整理连续音高': 'Refining the pitch curve',
    '识别音符边界': 'Detecting note boundaries',
    '音符模型暂不可用，使用连续曲线整理音符': 'Note model unavailable. Estimating notes from the pitch curve.',
    '整理主要音符': 'Refining main notes',
    '显存不足，部分阶段使用 CPU，分析较慢': 'GPU memory is low. Some analysis stages will run more slowly on the CPU.',
    'GPU 加速': 'GPU acceleration',
    '已指定使用 CPU': 'CPU mode selected',
    '未检测到可用的 NVIDIA GPU 加速，请检查显卡和驱动': 'NVIDIA GPU acceleration is unavailable. Check your GPU and driver.',
    'GPU 运算自检通过': 'GPU check passed',
    'GPU 运算自检未通过，请检查驱动或显卡兼容性': 'GPU check failed. Check driver and GPU compatibility.',
    '当前安装包的 GPU 运行库不支持此显卡，请安装新版完整包': 'This GPU is unsupported by the installed runtime. Install a newer full package.',
    'GPU 自检时显存不足，暂用 CPU，请关闭占用显存的程序后重试': 'GPU memory ran out during the check. Close apps using the GPU and retry.',
    '显卡驱动版本过旧，请更新 NVIDIA 驱动后重试': 'Update your NVIDIA driver and retry.',
}


def localized(language, source):
    return ENGLISH.get(source, source) if language == 'en' else source


def compute_status(language, source):
    # Worker output and saved jobs use the original text regardless of UI language.
    prefix = 'CPU 分析较慢：'
    if language == 'en' and source and source.startswith(prefix):
        return 'Slower CPU analysis. ' + localized(language, source[len(prefix):])
    return localized(language, source)


class InterfaceTranslator(QTranslator):
    def isEmpty(self):
        return False

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        if context in ('Main', 'ViewControl'):
            return ENGLISH.get(sourceText)
        return None


class LocalizedEngine(QQmlApplicationEngine):
    def __init__(self):
        super().__init__()
        self.translator = InterfaceTranslator(self)

    @Slot(str)
    def set_language(self, language):
        app = QCoreApplication.instance()
        if language == 'en':
            app.installTranslator(self.translator)
        else:
            app.removeTranslator(self.translator)
        self.retranslate()
