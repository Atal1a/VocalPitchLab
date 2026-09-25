import QtQuick
import QtQuick.Controls.Basic
Slider {
    id: control
    implicitHeight: 30
    background: Rectangle { x: control.leftPadding; y: control.topPadding + control.availableHeight / 2 - 2; width: control.availableWidth; height: 4; radius: 2; color: Theme.line
        Rectangle { width: control.visualPosition * parent.width; height: 4; radius: 2; color: Theme.accent }
    }
    handle: Rectangle { x: control.leftPadding + control.visualPosition * (control.availableWidth - width); y: control.topPadding + control.availableHeight / 2 - height / 2; width: control.pressed ? 16 : 12; height: width; radius: width/2; color: Theme.accent
        Behavior on width { NumberAnimation { duration: Theme.motion ? 100 : 0 } }
    }
}
