import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Effects
import VocalPitch 1.0

ApplicationWindow {
    id: win
    width: 1380; height: 900; minimumWidth: 1060; minimumHeight: 720
    visible: true; title: "VocalPitchLab"; color: Theme.background
    property var s: backend.state
    property bool managing: false
    property var selectedSongs: []
    property int selectionAnchor: -1
    property bool loopEditor: false
    property real loopViewStart: 0
    property real loopViewEnd: 20
    property bool loopOverview: false
    function pitchLabel(value) {
        const key=Math.round(value)
        const cents=Math.round((value-key)*100)
        return ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"][((key%12)+12)%12]+(Math.floor(key/12)-1)+(cents ? " " + (cents>0 ? "+" : "") + cents + "¢" : "")
    }
    font.family: "Microsoft YaHei"
    function focusLoop() {
        loopOverview = false
        loopViewStart = Math.max(0, s.loopA - 2)
        loopViewEnd = Math.min(s.duration, s.loopB + 2)
        loopRange.setValues(s.loopA, s.loopB)
    }
    function chooseSong(index, modifiers) {
        if (managing || (modifiers & Qt.ControlModifier) || (modifiers & Qt.ShiftModifier)) {
            managing = true
            let next = selectedSongs.slice()
            if ((modifiers & Qt.ShiftModifier) && selectionAnchor >= 0) {
                for (let i = Math.min(index,selectionAnchor); i <= Math.max(index,selectionAnchor); i++) if (next.indexOf(i) < 0) next.push(i)
            } else {
                let p = next.indexOf(index)
                if (p >= 0) next.splice(p,1); else next.push(index)
            }
            selectedSongs = next; selectionAnchor = index
        } else backend.selectSong(index)
    }
    FileDialog { id: audioDialog; title: "导入歌曲"; currentFolder: backend.inputUrl; fileMode: FileDialog.OpenFiles; nameFilters: ["音频 (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma *.aiff)"]; onAccepted: { for (let f of selectedFiles) backend.enqueue(f.toString()) } }
    Item {
        id: backdrop; anchors.fill: parent
        Rectangle { anchors.fill: parent; color: Theme.background; Behavior on color { ColorAnimation { duration: Theme.motion ? 180 : 0 } } }
        Rectangle { x: -180; y: -170; width: 520; height: 630; radius: 260; color: Theme.dark ? "#1c3553" : "#dfebfb"; opacity: .24 }
        Rectangle { x: -160; y: win.height-400; width: 420; height: 450; radius: 210; color: Theme.dark ? "#28233f" : "#eee5f6"; opacity: .18 }
    }
    DropArea { anchors.fill: parent; onDropped: function(drop) { if (drop.hasUrls) { for (let u of drop.urls) backend.enqueue(u.toString()); drop.acceptProposedAction() } } }
    RowLayout {
        anchors.fill: parent; spacing: 0
        Item {
            Layout.preferredWidth: 226; Layout.fillHeight: true; clip: true
            ShaderEffectSource { id: glassSource; sourceItem: backdrop; sourceRect: Qt.rect(0,0,226,win.height); width: 226; height: win.height; visible: false }
            MultiEffect { anchors.fill: parent; source: glassSource; blurEnabled: true; blurMax: 48; blur: 1; autoPaddingEnabled: false }
            Rectangle { anchors.fill: parent; color: Theme.glass }
            Rectangle { anchors.right: parent.right; height: parent.height; width: 1; color: Theme.line; opacity: .5 }
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 18; spacing: 14
                RowLayout { Layout.topMargin: 16; Layout.bottomMargin: 15; spacing: 9
                    Image { objectName: "brandLogo"; property bool ready: status === Image.Ready; source: "../assets/vocalpitch-logo.svg"; Layout.preferredWidth: 34; Layout.preferredHeight: 34; sourceSize.width: 102; sourceSize.height: 102 }
                    Text { text: "VocalPitchLab"; color: Theme.text; font.pixelSize: 18; font.bold: true }
                }
                AppButton { objectName: "importButton"; text: "＋ 导入歌曲"; primary: true; Layout.fillWidth: true; onClicked: audioDialog.open() }
                RowLayout {
                    Layout.topMargin: 14
                    Text { text: "歌曲库"; color: Theme.muted; font.pixelSize: 12; Layout.fillWidth: true }
                    AppButton { objectName: "manageButton"; text: managing ? "完成" : "批量管理"; onClicked: { managing = !managing; selectedSongs = [] } }
                }
                RowLayout { visible: managing
                    AppButton { text: "全选"; onClicked: { let a=[]; for(let i=0;i<backend.songs.length;i++) a.push(i); selectedSongs=a } }
                    AppButton { objectName: "deleteButton"; text: "移除 " + selectedSongs.length; enabled: selectedSongs.length > 0; tip: "只移出歌曲库，保留原文件"; onClicked: { backend.deleteSongs(selectedSongs); selectedSongs=[] } }
                }
                ListView {
                    id: songList; objectName: "songList"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 6; model: backend.songs
                    boundsBehavior: Flickable.StopAtBounds
                    delegate: Rectangle {
                        id: songRow
                        required property var modelData
                        objectName: "songRow" + modelData.index
                        property bool current: s.selected === modelData.index
                        property bool chosen: managing && selectedSongs.indexOf(modelData.index)>=0
                        property bool hovered: songHover.hovered || songMouse.containsMouse
                        width: ListView.view.width; height: 64; radius: 12
                        color: (chosen || current) ? (hovered ? Theme.songSelectedHover : Theme.songSelected) : (hovered ? Theme.songHover : "transparent")
                        border.color: hovered ? Theme.songHoverBorder : "transparent"; border.width: 1
                        Rectangle { visible: songRow.current; anchors.left: parent.left; anchors.leftMargin: 1; anchors.verticalCenter: parent.verticalCenter; width: 3; height: 24; radius: 1.5; color: Theme.accent }
                        Rectangle { visible: managing; x: 9; anchors.verticalCenter: parent.verticalCenter; width: 13; height: 13; radius: 4; color: selectedSongs.indexOf(modelData.index)>=0 ? Theme.accent : "transparent"; border.color: Theme.muted }
                        Column { anchors.left: parent.left; anchors.leftMargin: managing ? 31 : 12; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; spacing: 5
                            Text { width: parent.width; text: modelData.name; elide: Text.ElideRight; color: Theme.text; font.pixelSize: 14; font.bold: s.selected === modelData.index }
                            Text { text: modelData.duration; color: Theme.muted; font.pixelSize: 11 }
                        }
                        HoverHandler { id: songHover; cursorShape: Qt.PointingHandCursor }
                        MouseArea { id: songMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onClicked: function(mouse) {
                                if (mouse.button === Qt.RightButton) { let p=songRow.mapToItem(win.contentItem,mouse.x,mouse.y); songContext.targetIndex=modelData.index; songContext.x=p.x; songContext.y=p.y; songContext.open() }
                                else chooseSong(modelData.index,mouse.modifiers)
                            }
                        }
                    }
                    ScrollBar.vertical: ScrollBar { visible: songList.contentHeight > songList.height; contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Theme.muted; opacity: .5 } }
                }
                ListView {
                    Layout.fillWidth: true; Layout.preferredHeight: Math.min(contentHeight,100); model: backend.jobs; clip: true
                    delegate: ItemDelegate { required property var modelData; width: ListView.view.width; height: 48; onClicked: backend.viewJob(modelData.id)
                        contentItem: RowLayout {
                            Text { text: modelData.name + "\n" + modelData.message; elide: Text.ElideRight; color: Theme.muted; font.pixelSize: 10; Layout.fillWidth: true }
                            AppButton { objectName: "removeJob_" + modelData.id; text: "删除"; tip: modelData.state === "running" ? "取消分析并删除任务" : "删除任务记录"; onClicked: backend.removeJob(modelData.id) }
                        }
                    }
                }
                AppButton { visible: managing && s.canUndo; text: "撤销移除"; Layout.fillWidth: true; onClicked: { backend.undoDelete(); selectedSongs=[] } }
                AppButton { objectName: "settingsButton"; text: "设置"; Layout.fillWidth: true; onClicked: settingsPopup.open() }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.margins: 24; spacing: 18
            RowLayout {
                Layout.topMargin: 7; Layout.bottomMargin: 5
                Text { text: s.loaded ? s.title : "歌曲库"; color: Theme.text; font.pixelSize: 27; font.bold: true; elide: Text.ElideRight; Layout.fillWidth: true }
                Rectangle {
                    objectName: "viewControlsPanel"
                    Layout.preferredWidth: 340; implicitHeight: 82; radius: 15
                    gradient: Gradient {
                        GradientStop { position: 0; color: Theme.dark ? "#ed303238" : "#faffffff" }
                        GradientStop { position: 1; color: Theme.dark ? "#ed26282d" : "#eaf7f8fa" }
                    }
                    border.color: Theme.dark ? "#474a51" : "#e0e3e9"; border.width: .7
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 6; spacing: 2
                        RowLayout {
                            spacing: 2
                            ViewControl { objectName: "timeControl"; enabled: s.loaded; label: "时间"; valueText: s.span===0 ? "整首" : Number(s.span.toFixed(1))+" 秒"; onAdjusted: function(steps) { backend.adjustView("time",steps) } }
                            Rectangle { implicitWidth: 1; implicitHeight: 24; color: Theme.line }
                        ViewControl { objectName: "pitchWidthControl"; enabled: s.loaded; label: "音域跨度"; valueText: Math.abs((s.high-s.low)%12)<.001 ? Math.round((s.high-s.low)/12)+" 八度" : Number((s.high-s.low).toFixed(1))+" 半音"; onAdjusted: function(steps) { backend.adjustView("width",steps) } }
                            Rectangle { implicitWidth: 1; implicitHeight: 24; color: Theme.line }
                        ViewControl { objectName: "pitchCenterControl"; enabled: s.loaded; label: "音域中心"; valueText: win.pitchLabel((s.low+s.high)/2); onAdjusted: function(steps) { backend.adjustView("center",steps) } }
                        }
                        RowLayout {
                            Layout.fillWidth: true; Layout.leftMargin: 6; Layout.rightMargin: 8
                            Button {
                                objectName: "overviewButton"; enabled: s.loaded; text: "整首"; implicitWidth: 48; implicitHeight: 22; hoverEnabled: true
                                onClicked: backend.toggleOverview()
                                ToolTip.visible: hovered; ToolTip.delay: 650; ToolTip.text: s.span===0 ? "恢复时间跨度" : "显示整首"
                                contentItem: Text { text: parent.text; color: s.span===0 ? Theme.accent : Theme.muted; font.pixelSize: 10; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                background: Rectangle { radius: 6; color: s.span===0 ? Theme.selected : parent.hovered ? Theme.hover : "transparent"; Behavior on color { ColorAnimation { duration: 140 } } }
                            }
                            Item { Layout.fillWidth: true }
                            AppButton { objectName: "adaptPitchButton"; enabled: s.loaded; text: "自适应"; implicitHeight: 22; onClicked: backend.adaptPitchRange() }
                            Text { text: s.loaded ? win.pitchLabel(s.low)+" – "+win.pitchLabel(s.high) : "—"; color: Theme.muted; font.pixelSize: 10 }
                        }
                    }
                }
            }
            Rectangle {
                objectName: "analysisCard"; visible: s.running || s.canRetry; Layout.fillWidth: true; implicitHeight: 92; color: Theme.panel; radius: 16; border.color: Theme.line; border.width: .6
                RowLayout { anchors.fill: parent; anchors.margins: 16; spacing: 18
                    ColumnLayout { Layout.fillWidth: true; spacing: 10
                        RowLayout { Layout.fillWidth: true
                            Text { text: s.jobName; font.pixelSize: 13; font.weight: Font.DemiBold; color: Theme.text; Layout.fillWidth: true; elide: Text.ElideRight }
                            Text { text: s.running ? Math.round(s.jobProgress) + "%" : "待重试"; font.pixelSize: 12; color: Theme.muted }
                        }
                        Rectangle { Layout.fillWidth: true; implicitHeight: 5; radius: 2.5; color: Theme.control
                            Rectangle { objectName: "analysisProgressFill"; height: parent.height; width: parent.width * Math.max(0, Math.min(1, s.jobProgress/100)); radius: 2.5; color: Theme.accent
                            }
                        }
                        Text { text: s.jobText; font.pixelSize: 11; color: Theme.muted; Layout.fillWidth: true; elide: Text.ElideRight
                            HoverHandler { id: jobStatusHover }
                            ToolTip.visible: jobStatusHover.hovered
                            ToolTip.text: s.jobText
                            ToolTip.delay: 400
                        }
                    }
                    AppButton { visible: s.running; text: "取消"; onClicked: backend.cancel() }
                    AppButton { visible: s.canRetry; text: "重试"; onClicked: backend.retry() }
                    AppButton { objectName: "removeDisplayedJob"; text: "删除"; tip: s.running ? "取消分析并删除任务" : "删除任务记录"; onClicked: backend.removeDisplayedJob() }
                }
            }
            Rectangle {
                id: chartPanel; Layout.fillWidth: true; Layout.fillHeight: true; radius: 18; color: Theme.panel; border.color: Theme.line; border.width: .5
                layer.enabled: true
                layer.effect: MultiEffect { shadowEnabled: true; shadowColor: Theme.dark ? "#24000000" : "#10000000"; shadowVerticalOffset: 4; shadowBlur: .35 }
                PitchView { objectName: "pitchView"; controller: backend; anchors.fill: parent; anchors.margins: 18; visible: s.loaded }
                Column { visible: !s.loaded; anchors.centerIn: parent; spacing: 18
                    Text { text: "拖入一首歌"; font.pixelSize: 27; font.bold: true; color: Theme.text }
                    AppButton { text: "选择音频"; primary: true; onClicked: audioDialog.open() }
                }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: loopEditor && s.loaded ? 202 : 114; radius: 18; color: Theme.dark ? "#ef24262b" : "#edffffff"; border.color: Theme.line; border.width: .5
                Behavior on implicitHeight { NumberAnimation { duration: Theme.motion ? 170 : 0; easing.type: Easing.OutCubic } }
                ColumnLayout { anchors.fill: parent; anchors.margins: 18; spacing: 10; enabled: s.loaded
                    RowLayout {
                        AppButton { objectName: "playButton"; text: s.playing ? "暂停" : "播放"; primary: true; tip: "空格"; onClicked: backend.togglePlay() }
                        AppButton { text: "−5s"; onClicked: backend.seek(s.position - 5) }
                        AppButton { text: "+5s"; onClicked: backend.seek(s.position + 5) }
                        TrackSlider { id: seekBar; objectName: "seekBar"; Layout.fillWidth: true; from: 0; to: s.duration; value: s.position; onMoved: backend.seek(value)
                            HoverHandler { id: seekHover }
                            readonly property real previewFraction: Math.max(0, Math.min(1, (seekHover.point.position.x - leftPadding - handle.width / 2) / Math.max(1, availableWidth - handle.width)))
                            readonly property real previewSeconds: from + previewFraction * (to - from)
                            ToolTip {
                                id: seekPreview
                                objectName: "seekPreview"
                                visible: seekHover.hovered && s.loaded && seekBar.to > 0
                                x: Math.max(0, Math.min(seekBar.width - width, seekHover.point.position.x - width / 2))
                                y: -height - 6
                                text: {
                                    const seconds = Math.floor(seekBar.previewSeconds)
                                    return Math.floor(seconds / 60).toString().padStart(2, "0") + ":" + (seconds % 60).toString().padStart(2, "0")
                                }
                                contentItem: Text { text: seekPreview.text; color: Theme.text; font.pixelSize: 12 }
                                background: Rectangle { radius: 8; color: Theme.panel; border.color: Theme.line }
                            }
                            WheelHandler { onWheel: function(event) { backend.wheel(event.angleDelta.y / 120, event.modifiers); event.accepted = true } }
                        }
                        Text { text: s.time + " / " + s.total; color: Theme.muted; font.pixelSize: 12 }
                    }
                    RowLayout {
                        AppButton { objectName: "audioSourceChoice"; text: s.source === "vocals" ? "分离人声" : "原曲"; onClicked: backend.setSource(s.source === "vocals" ? "original" : "vocals") }
                        AppButton {
                            id: songHarmony; objectName: "songHarmonyChoice"
                            enabled: s.loaded && !s.songSeparationBusy
                            text: s.songSeparationBusy ? "和声分离 · 处理中" : (s.activeSeparation === "mel_bs" ? "和声分离：开" : "和声分离：关")
                            onClicked: backend.setSongHarmony(s.activeSeparation !== "mel_bs")
                        }
                        AppButton { objectName: "loopButton"; text: s.loop ? "循环中" : "循环"; primary: s.loop; onClicked: { if (!loopEditor) { backend.prepareLoop(); focusLoop() } loopEditor = !loopEditor } }
                        Item { Layout.fillWidth: true }
                        AppButton { objectName: "muteButton"; text: s.muted ? "静音" : "音量"; tip: "歌曲音量与静音；钢琴试听独立播放"; onClicked: backend.toggleMute() }
                        TrackSlider { objectName: "volumeBar"; Layout.preferredWidth: 110; from: 0; to: 1; value: s.muted ? 0 : s.volume; onMoved: backend.setVolume(value) }
                        Text { text: s.muted ? "0%" : Math.round(s.volume * 100) + "%"; color: Theme.muted; font.pixelSize: 11; Layout.preferredWidth: 32 }
                    }
                    ColumnLayout {
                        visible: loopEditor && s.loaded; Layout.fillWidth: true; spacing: 4
                        RowLayout {
                            AppButton { text: "A  " + s.loopAText; tip: "将当前位置设为循环起点"; onClicked: { backend.markLoop("a"); focusLoop() } }
                            AppButton { text: "B  " + s.loopBText; tip: "将当前位置设为循环终点"; onClicked: { backend.markLoop("b"); focusLoop() } }
                            Item { Layout.fillWidth: true }
                            AppButton { text: loopOverview ? "精调" : "整首范围"; tip: "精调模式放大 A–B 附近，方便拖动边界"; onClicked: { if (loopOverview) focusLoop(); else { loopOverview=true; loopViewStart=0; loopViewEnd=s.duration; loopRange.setValues(s.loopA,s.loopB) } } }
                            AppButton { objectName: "loopToggle"; text: s.loop ? "停止循环" : "开始循环"; primary: s.loop; onClicked: backend.setLoop(!s.loop) }
                        }
                        RangeSlider {
                            id: loopRange; objectName: "loopRange"; Layout.fillWidth: true; from: loopViewStart; to: Math.max(loopViewStart+.25,loopViewEnd); first.value: s.loopA; second.value: s.loopB; stepSize: .05; snapMode: RangeSlider.SnapOnRelease
                            first.onMoved: backend.setLoopRange(first.value,second.value)
                            second.onMoved: backend.setLoopRange(first.value,second.value)
                            background: Rectangle { x: loopRange.leftPadding; y: loopRange.topPadding + loopRange.availableHeight/2 - 2; width: loopRange.availableWidth; height: 4; radius: 2; color: Theme.line
                                Rectangle { x: loopRange.first.visualPosition * parent.width; width: (loopRange.second.visualPosition-loopRange.first.visualPosition)*parent.width; height: 4; radius: 2; color: Theme.accent }
                            }
                            first.handle: Rectangle { objectName: "loopStartHandle"; x: loopRange.leftPadding + loopRange.first.visualPosition*(loopRange.availableWidth-width); y: loopRange.topPadding+loopRange.availableHeight/2-height/2; width: 17; height: 22; radius: 6; color: Theme.accent; Text { anchors.centerIn: parent; text: "A"; font.pixelSize: 10; color: Theme.dark ? "#10263e" : "white" } }
                            second.handle: Rectangle { objectName: "loopEndHandle"; x: loopRange.leftPadding + loopRange.second.visualPosition*(loopRange.availableWidth-width); y: loopRange.topPadding+loopRange.availableHeight/2-height/2; width: 17; height: 22; radius: 6; color: Theme.accent; Text { anchors.centerIn: parent; text: "B"; font.pixelSize: 10; color: Theme.dark ? "#10263e" : "white" } }
                        }
                    }
                }
            }
        }
    }
    Popup {
        id: settingsPopup; objectName: "settingsPopup"; anchors.centerIn: parent; width: 530; height: Math.min(650,win.height-40); padding: 24; modal: true; popupType: Popup.Item
        background: Rectangle { radius: 24; color: Theme.panel; border.color: Theme.line
            layer.enabled: true
            layer.effect: MultiEffect { shadowEnabled: true; shadowColor: "#40071122"; shadowVerticalOffset: 12; shadowBlur: .7 }
            Rectangle { anchors.fill: parent; anchors.margins: 1; radius: 23; color: "transparent"; border.color: Theme.dark ? "#18ffffff" : "#ddffffff" }
        }
        Overlay.modal: Rectangle { color: Theme.dark ? "#88060b13" : "#330f213b" }
        onAboutToShow: { opacity = 1; scale = 1 }
        enter: Transition { NumberAnimation { property: "scale"; from: .97; to: 1; duration: 190; easing.type: Easing.OutCubic } }
        ColumnLayout { anchors.fill: parent; spacing: 16
            RowLayout { Text { text: "设置"; color: Theme.text; font.pixelSize: 24; font.bold: true } Item { Layout.fillWidth: true } AppButton { text: "完成"; onClicked: settingsPopup.close() } }
            ScrollView {
                id: settingsScroll; objectName: "settingsScroll"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                contentWidth: availableWidth; contentHeight: settingsContent.implicitHeight
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ColumnLayout { id: settingsContent; objectName: "settingsContent"; width: settingsScroll.availableWidth; spacing: 16
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: 90; radius: 16; color: Theme.control
                        ColumnLayout { anchors.fill: parent; anchors.margins: 16; spacing: 12
                            Text { text: "钢琴试听音量"; color: Theme.text; font.pixelSize: 13 }
                            RowLayout { Layout.fillWidth: true
                                TrackSlider { objectName: "pianoVolume"; Layout.fillWidth: true; from: 0; to: 1; value: s.settings.pianoVolume; onMoved: backend.setPianoVolume(value) }
                                Text { text: Math.round(s.settings.pianoVolume*100) + "%"; color: Theme.muted; font.pixelSize: 12; Layout.preferredWidth: 36 }
                            }
                        }
                    }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 84; radius: 16; color: Theme.control
                ColumnLayout { anchors.fill: parent; anchors.margins: 14; spacing: 10
                    Text { text: "外观"; color: Theme.muted; font.pixelSize: 11 }
                    RowLayout { spacing: 5; Layout.fillWidth: true
                        Repeater { model: [{label:"随系统",key:"system"},{label:"浅色",key:"light"},{label:"深色",key:"dark"}]
                            delegate: AppButton { required property var modelData; Layout.fillWidth: true; text: modelData.label; primary: s.settings.theme === modelData.key; onClicked: backend.setting("theme",modelData.key) }
                        }
                    }
                }
            }
            Rectangle {
                objectName: "pitchHintsCard"; Layout.fillWidth: true; implicitHeight: pitchHintsContent.implicitHeight + 32; radius: 16; color: Theme.control
                ColumnLayout { id: pitchHintsContent; anchors.fill: parent; anchors.margins: 16; spacing: 0
                    Text { text: "功能选项"; color: Theme.muted; font.pixelSize: 11 }
                    SettingRow { objectName: "harmonySeparation"; Layout.fillWidth: true; title: "默认分离和声"; checked: s.settings.separationModel === "mel_bs"; onToggled: function(value) { backend.setting("separationModel",value ? "mel_bs" : "mel_roformer") } }
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                    SettingRow { Layout.fillWidth: true; title: "主要音符"; checked: s.settings.blocks; onToggled: function(value) { backend.setting("blocks",value) } }
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                    SettingRow { Layout.fillWidth: true; title: "细节曲线"; checked: s.settings.curve; onToggled: function(value) { backend.setting("curve",value) } }
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                    SettingRow { Layout.fillWidth: true; title: "弱化不可靠曲线"; checked: s.settings.cleanCurve; onToggled: function(value) { backend.setting("cleanCurve",value) } }
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                    SettingRow { objectName: "hoverToggle"; Layout.fillWidth: true; title: "悬浮高亮与对齐线"; checked: s.settings.hoverNotes; onToggled: function(value) { backend.setting("hoverNotes",value) } }
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                    SettingRow { objectName: "liveNotesToggle"; Layout.fillWidth: true; title: "播放线旁的主音高"; checked: s.settings.liveNotes; onToggled: function(value) { backend.setting("liveNotes",value) } }
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.line }
                    SettingRow { objectName: "liveCurveToggle"; Layout.fillWidth: true; title: "播放线旁的曲线音高"; checked: s.settings.liveCurve; onToggled: function(value) { backend.setting("liveCurve",value) } }
                }
            }
            Text { objectName: "settingsHelp"; Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "空格 播放 / 暂停 · 滚轮 定位\n拖动图表 框选循环 · 点击左侧音名 钢琴试听\nShift + 滚轮 上下移动音域\nCtrl + 滚轮 缩放时间 · Alt + 滚轮 缩放音域"; color: Theme.muted; font.pixelSize: 11; lineHeight: 1.5 }
                }
            }
        }
    }
    Rectangle {
        id: toast; anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 26; width: Math.min(win.width-80,toastRow.implicitWidth+32); height: 48; radius: 14; color: Theme.panel; border.color: Theme.line; visible: toastTimer.running; z: 10
        RowLayout { id: toastRow; anchors.centerIn: parent; spacing: 16
            Text { text: s.message; color: Theme.text; font.pixelSize: 12 }
            AppButton { visible: s.canUndo; text: "撤销"; onClicked: { backend.undoDelete(); selectedSongs=[] } }
        }
        Timer { id: toastTimer; interval: 6500 }
        Connections { target: backend; function onChanged() { if (win.lastMessage !== s.message) { win.lastMessage=s.message; if(s.message.length) toastTimer.restart() } } }
    }
    property string lastMessage: ""
    Menu {
        id: songContext; objectName: "songContext"; property int targetIndex: -1; popupType: Popup.Item; width: 180; padding: 6
        background: Rectangle { radius: 12; color: Theme.panel; border.color: Theme.line }
        MenuItem { objectName: "removeSongAction"; text: "从歌曲库移除"; onTriggered: backend.deleteSongs([songContext.targetIndex]); contentItem: Text { text: parent.text; color: Theme.dark ? "#ff9d9d" : "#bc3445"; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter } background: Rectangle { radius: 7; color: parent.highlighted ? Theme.hover : "transparent" } }
        MenuItem { text: "批量管理"; onTriggered: { managing=true; selectedSongs=[songContext.targetIndex] } contentItem: Text { text: parent.text; color: Theme.text; font.pixelSize: 13; verticalAlignment: Text.AlignVCenter } background: Rectangle { radius: 7; color: parent.highlighted ? Theme.hover : "transparent" } }
    }
    Connections { target: backend; function onContentChanged() { selectedSongs=[]; Qt.callLater(function() { if (s.loaded) focusLoop() }) } }
}
