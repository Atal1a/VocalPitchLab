import QtQuick
import QtQuick.Controls.Basic
Button {
    id: control
    property bool primary: false
    property string tip: ""
    implicitHeight: 36
    implicitWidth: Math.max(36, label.implicitWidth + 24)
    hoverEnabled: true
    ToolTip.visible: hovered && tip.length > 0
    ToolTip.text: tip
    ToolTip.delay: 650
    scale: down ? .97 : 1
    Behavior on scale { NumberAnimation { duration: Theme.motion ? 100 : 0 } }
    contentItem: Text { id: label; text: control.text; color: control.primary ? (Theme.dark ? "#10263e" : "white") : Theme.text; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
    background: Rectangle { radius: 10; color: control.primary ? Theme.accent : (control.hovered ? Theme.hover : Theme.control); border.color: control.activeFocus ? Theme.accent : Theme.line; border.width: control.primary ? 0 : .6; opacity: control.enabled ? 1 : .4; Behavior on color { ColorAnimation { duration: 120 } } }
}
