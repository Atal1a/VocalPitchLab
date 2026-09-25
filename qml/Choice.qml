import QtQuick
import QtQuick.Controls.Basic
ComboBox {
    id: control
    implicitWidth: 130; implicitHeight: 36
    contentItem: Text { text: control.displayText; leftPadding: 12; rightPadding: 28; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight; color: Theme.text; font.pixelSize: 13 }
    indicator: Item { x: control.width - 24; anchors.verticalCenter: parent.verticalCenter; width: 12; height: 8
        Rectangle { x: 1; y: 3; width: 7; height: 1.5; rotation: 45; color: Theme.muted }
        Rectangle { x: 5; y: 3; width: 7; height: 1.5; rotation: -45; color: Theme.muted }
    }
    background: Rectangle { radius: 10; color: Theme.control; border.color: control.activeFocus ? Theme.accent : "transparent" }
    delegate: ItemDelegate { width: control.width; text: control.textRole ? modelData[control.textRole] : modelData; highlighted: control.highlightedIndex === index; contentItem: Text { text: parent.text; color: Theme.text; font.pixelSize: 13; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter } background: Rectangle { radius: 7; color: parent.highlighted ? Theme.selected : Theme.panel } }
    popup: Popup { popupType: Popup.Item; y: control.height + 5; width: control.width; padding: 6; implicitHeight: Math.min(contentItem.implicitHeight + 12, 280); background: Rectangle { color: Theme.panel; radius: 12; border.color: Theme.line } contentItem: ListView { clip: true; implicitHeight: contentHeight; model: control.popup.visible ? control.delegateModel : null; currentIndex: control.highlightedIndex; ScrollBar.vertical: ScrollBar {} } }
}
