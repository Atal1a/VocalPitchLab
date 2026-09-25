pragma Singleton
import QtQuick
QtObject {
    property bool dark: backend.state.dark
    readonly property bool motion: true
    property color background: dark ? "#18191c" : "#f5f5f7"
    property color panel: dark ? "#202226" : "#ffffff"
    property color control: dark ? "#2c2e33" : "#f1f2f4"
    property color hover: dark ? "#383b41" : "#e7e9ed"
    property color text: dark ? "#f2f2f4" : "#1d1d1f"
    property color muted: dark ? "#a5a5ad" : "#6e6e73"
    property color line: dark ? "#3a3c42" : "#e2e3e7"
    property color accent: dark ? "#6badff" : "#0071e3"
    property color selected: dark ? "#303e50" : "#e5efff"
    property color glass: dark ? "#c9212328" : "#ccf5f5f7"
    property color selectedHover: dark ? "#37485e" : "#e0edff"
    property color songHover: dark ? "#3b4049" : "#e1e6ee"
    property color songSelected: dark ? "#293f59" : "#e5effd"
    property color songSelectedHover: dark ? "#3a587b" : "#cbdff8"
    property color songHoverBorder: dark ? "#687486" : "#bac6d6"
}
