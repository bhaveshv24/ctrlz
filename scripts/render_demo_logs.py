"""Read only CampusPass Render metadata/logs. No token is printed."""
import json,sys
from pathlib import Path
import httpx
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from ctrlz.render_readonly import RenderReadOnly
from ten_purchase_demo import DATA,HOST,save

def main():
    key=dotenv_values(ROOT/'.env').get('RENDER_API_KEY')
    with httpx.Client() as c:
        reader=RenderReadOnly(c,key);service=reader.service(HOST)
        file=DATA/'hosted-run.json';run=json.loads(file.read_text()) if file.exists() else None
        order=run['orders'][4] if run and len(run.get('orders',[]))==10 else None
        path=DATA/'render-log-evidence.json';old=json.loads(path.read_text()) if path.exists() else {}
        previous=old.get('logs',[]) if old.get('affected_order')==order else []
        logs,truncated=reader.logs(service,order,[x['id'] for x in previous])
        result={'service':service,'deployment':reader.deployment(service),'affected_order':order,'logs':(previous+logs)[-2000:],'truncated':truncated}
        save(path,result)
        print(json.dumps({'service_id':service['id'],'deployed_revision':result['deployment']['commit'],'affected_order':order,'matching_retained_logs':len(result['logs']),'new_logs':len(logs),'bounded_query_truncated':truncated,'evidence_file':str(path)},indent=2))
if __name__=='__main__':main()
