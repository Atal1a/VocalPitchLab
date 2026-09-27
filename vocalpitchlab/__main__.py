"""Shared GUI and subprocess entry point."""
import runpy
import sys


def main():
    commands = {
        '--analysis-worker': 'vocalpitchlab.analysis.analysis_worker',
        '--analyze': 'vocalpitchlab.analysis.analyze_song',
        '--presentation': 'vocalpitchlab.analysis.presentation_results',
    }
    if len(sys.argv) > 1 and sys.argv[1] in ('--help', '-h'):
        print('VocalPitchLab: python main.py [--analyze FILE | --analysis-worker | --presentation]')
        return 0
    if len(sys.argv) > 1 and sys.argv[1] in commands:
        module = commands[sys.argv.pop(1)]
        runpy.run_module(module, run_name='__main__')
        return 0
    from vocalpitchlab.ui.app import main as gui_main
    return gui_main()


if __name__ == '__main__':
    raise SystemExit(main())
