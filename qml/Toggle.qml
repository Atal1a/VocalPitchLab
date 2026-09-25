import QtQuick
import QtQuick.Controls.Basic
CheckBox {
    id: control
    property color ink: Theme.text
    implicitHeight: 32; spacing: 7
    indicator: Rectangle { x: 0; anchors.verticalCenter: parent.verticalCenter; width: 17; height: 17; radius: 5; color: control.checked ? Theme.accent : Theme.panel; border.color: control.checked ? Theme.accent : Theme.muted
        Rectangle { visible: control.checked; x: 3; y: 9; width: 5; height: 1.6; rotation: 45; color: "white" }
        Rectangle { visible: control.checked; x: 6; y: 7; width: 8; height: 1.6; rotation: -45; color: "white" }
    }
    contentItem: Text { text: control.text; leftPadding: 24; verticalAlignment: Text.AlignVCenter; color: control.ink; font.pixelSize: 12 }
}
