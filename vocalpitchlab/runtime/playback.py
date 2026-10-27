"""Select the saved playback mode before Qt initializes its media backend."""
import json
import os
import sys
from pathlib import Path


def configure_backend(data_root, environ=None, platform=None):
    env=os.environ if environ is None else environ
    platform=sys.platform if platform is None else platform
    if platform!='win32' or env.get('QT_MEDIA_BACKEND'):
        return env.get('QT_MEDIA_BACKEND','')
    try:
        data=json.loads((Path(data_root)/'library/index.json').read_text(encoding='utf-8-sig'))
        compatible=data.get('settings',{}).get('compatiblePlayback') is True
    except (OSError,ValueError,AttributeError):
        compatible=False
    if compatible:env['QT_MEDIA_BACKEND']='windows'
    return env.get('QT_MEDIA_BACKEND','')
