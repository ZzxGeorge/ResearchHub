"""The only executable entry point packaged for desktop; credentials never enter argv."""
import asyncio
import json
import logging
import os
from pathlib import Path
import socket
import sys
import threading
from filelock import FileLock
import uvicorn

def run():
    root=Path(os.environ['RESEARCH_HUB_WORKSPACE']).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True)
    log_dir=Path(os.environ['RESEARCH_HUB_LOG_DIR']);log_dir.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=log_dir/'backend.log',encoding='utf-8',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    token=os.environ.get('RESEARCH_HUB_DESKTOP_TOKEN','')
    if len(token)<32: raise RuntimeError('Missing desktop session credential')
    with FileLock(str(root/'.server.lock'),timeout=0):
        from app.main import create_app
        application=create_app(root)
        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        sock.bind(('127.0.0.1',0));sock.listen(128)
        server=uvicorn.Server(uvicorn.Config(application,host='127.0.0.1',port=sock.getsockname()[1],log_config=None,access_log=False))
        def monitor():
            try: sys.stdin.buffer.readline()
            finally: server.should_exit=True
        threading.Thread(target=monitor,daemon=True).start()
        async def serve():
            serving=asyncio.create_task(server.serve(sockets=[sock]))
            while not server.started and not serving.done(): await asyncio.sleep(.05)
            if server.started:
                print(json.dumps({'event':'ready','port':sock.getsockname()[1],'instance':os.environ['RESEARCH_HUB_INSTANCE']}),flush=True)
            await serving
        try: asyncio.run(serve())
        finally: sock.close();application.state.workspace.engine.dispose()

if __name__=='__main__':
    try:run()
    except Exception:
        logging.exception('Desktop backend startup failed')
        raise
