"""Expose only explicitly configured scoped telemetry paths, never CtrlZ control APIs."""
import argparse,json
from pathlib import Path
import httpx,uvicorn
from fastapi import FastAPI,Request
from fastapi.responses import Response


def create_gateway(target,paths):
    from urllib.parse import urlsplit
    url=urlsplit(target)
    if url.scheme!='http' or url.hostname not in {'127.0.0.1','localhost'} or url.path not in {'','/'}:raise ValueError('Loopback CtrlZ target required')
    if not paths or any(not p.startswith('/telemetry/') or '?' in p for p in paths):raise ValueError('Explicit telemetry paths required')
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    @app.api_route('/{path:path}',methods=['GET','POST','PUT','DELETE','PATCH','OPTIONS'])
    async def proxy(path:str,request:Request):
        route='/'+path
        if route not in paths or request.method not in {'GET','POST'}:return Response(status_code=404)
        if request.method=='GET' and request.query_params.get('transport')!='long_poll':return Response(status_code=400)
        raw=b''
        async for chunk in request.stream():
            raw+=chunk
            if len(raw)>262144:return Response(status_code=413)
        headers={'Authorization':request.headers.get('authorization',''),'Content-Type':'application/json'}
        async with httpx.AsyncClient(timeout=35,follow_redirects=False) as c:
            try:r=await c.request(request.method,target+route,params={'transport':'long_poll'} if request.method=='GET' else None,content=raw,headers=headers)
            except httpx.HTTPError:return Response(status_code=502)
        return Response(r.content,status_code=r.status_code,media_type='application/json',headers={'Cache-Control':'no-store'})
    return app


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',default='http://127.0.0.1:18070');p.add_argument('--paths-file',required=True);p.add_argument('--port',type=int,default=18073);a=p.parse_args()
    uvicorn.run(create_gateway(a.target,json.loads(Path(a.paths_file).read_text())),host='127.0.0.1',port=a.port,access_log=False)
