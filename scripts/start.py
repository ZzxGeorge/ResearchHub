"""Cross-platform local launcher. No data files are stored beside application code."""
import argparse
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Start Research Hub on localhost')
    parser.add_argument('--workspace',type=Path,help='Independent data directory; default ~/.research-hub/workspace')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    if not (ROOT/'frontend/dist/index.html').exists():
        parser.error('Frontend build missing. Run npm ci and npm run build from frontend first.')
    if args.workspace:
        source=ROOT.resolve(); target=args.workspace.expanduser().resolve()
        if target==source or target.is_relative_to(source):
            parser.error('User workspace must be outside the application source directory.')
        os.environ['RESEARCH_HUB_WORKSPACE']=str(target)
    import uvicorn
    print(f'Research Hub: http://127.0.0.1:{args.port}')
    uvicorn.run('app.main:create_app',factory=True,host='127.0.0.1',port=args.port)
