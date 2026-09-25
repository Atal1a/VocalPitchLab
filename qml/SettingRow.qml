import QtQuick
import QtQuick.Controls.Basic
Item {
    id: row
    property string title: ""
    property string detail: ""
    property bool checked: false
    signal toggled(bool value)
    implicitHeight: detail.length ? 62 : 50
    Column { anchors.left: parent.left; anchors.right: toggle.left; anchors.rightMargin: 20; anchors.verticalCenter: parent.verticalCenter; spacing: 4
        Text { text: row.title; font.pixelSize: 13; color: Theme.text }
        Text { visible: row.detail.length > 0; text: row.detail; font.pixelSize: 11; color: Theme.muted }
    }
    Switch {
        id: toggle; objectName: row.objectName + "Switch"; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; checked: row.checked; onClicked: row.toggled(checked); padding: 0
        indicator: Rectangle { implicitWidth: 40; implicitHeight: 24; radius: 12; color: toggle.checked ? Theme.accent : Theme.line
            Behavior on color { ColorAnimation { duration: 130 } }
            Rectangle { width: 18; height: 18; radius: 9; x: toggle.checked ? 19 : 3; y: 3; color: "white"; Behavior on x { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } } }
        }
    }
}
