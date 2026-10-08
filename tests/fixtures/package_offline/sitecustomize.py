import os,sys
from pathlib import Path
def no_network(event,args):
    if event in ('socket.connect','socket.getaddrinfo'):
        path=os.environ.get('VPL_NETWORK_AUDIT')
        if path:
            with open(path,'a',encoding='utf-8') as f:f.write(event+'\n')
        raise OSError('Network disabled for offline package validation')
sys.addaudithook(no_network)
