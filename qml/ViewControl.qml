import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: control
    property string label: ""
    property string valueText: ""
    signal adjusted(int steps)
    implicitWidth: 106
    implicitHeight: 46
    radius: 10
    color: interaction.pressed ? Theme.selected : interaction.containsMouse ? Theme.hover : "transparent"
    border.color: interaction.pressed ? Qt.alpha(Theme.accent,.45) : "transparent"
    border.width: .7
    opacity: enabled ? 1 : .4
    Behavior on color { ColorAnimation { duration: 140 } }
    Column {
        anchors.centerIn: parent; spacing: 4
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: control.label; color: Theme.muted; font.pixelSize: 10 }
        Text { anchors.horizontalCenter: parent.horizontalCenter; text: control.valueText; color: interaction.pressed ? Theme.accent : Theme.text; font.pixelSize: 14; font.weight: Font.DemiBold; Behavior on color { ColorAnimation { duration: 120 } } }
    }
    Text { anchors.left: parent.left; anchors.leftMargin: 5; anchors.verticalCenter: parent.verticalCenter; text: "‹"; color: Theme.muted; font.pixelSize: 14; opacity: interaction.containsMouse ? .7 : 0; Behavior on opacity { NumberAnimation { duration: 140 } } }
    Text { anchors.right: parent.right; anchors.rightMargin: 5; anchors.verticalCenter: parent.verticalCenter; text: "›"; color: Theme.muted; font.pixelSize: 14; opacity: interaction.containsMouse ? .7 : 0; Behavior on opacity { NumberAnimation { duration: 140 } } }
    ToolTip.visible: interaction.containsMouse && !interaction.pressed
    ToolTip.delay: 800
    ToolTip.text: "滚轮微调 · 左右拖动调整 · Shift 拖动精调"
    MouseArea {
        id: interaction
        anchors.fill: parent
        hoverEnabled: true; preventStealing: true
        cursorShape: Qt.SizeHorCursor
        property real originX: 0
        property real lastX: 0
        property real remainder: 0
        property real wheelRemainder: 0
        property bool dragging: false
        onPressed: function(mouse) { originX=mouse.x; lastX=mouse.x; remainder=0; dragging=false }
        onPositionChanged: function(mouse) {
            if (!pressed) return
            if (!dragging && Math.abs(mouse.x-originX)<=4) return
            dragging=true
            remainder+=(mouse.x-lastX)/((mouse.modifiers & Qt.ShiftModifier) ? 48 : 12)
            lastX=mouse.x
            const steps=Math.trunc(remainder)
            if (steps) { remainder-=steps; control.adjusted(steps) }
        }
        onReleased: { dragging=false; remainder=0 }
        onCanceled: { dragging=false; remainder=0 }
        onWheel: function(wheel) {
            wheelRemainder+=(wheel.angleDelta.y || wheel.angleDelta.x)/120
            const steps=Math.trunc(wheelRemainder)
            if (steps) { wheelRemainder-=steps; control.adjusted(steps) }
            wheel.accepted=true
        }
    }
}
