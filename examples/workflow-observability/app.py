"""Business HTTP service and background queue; loopback/container demo only."""
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from jobs import submit,process

pending=queue.Queue(maxsize=2000)


def worker():
    while True:
        job_id=pending.get()
        try:process(job_id)
        finally:pending.task_done()


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,data):
        body=json.dumps(data).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path=='/health':self.reply(200,{'status':'healthy'})
        else:self.reply(404,{'error':'Not found'})
    def do_POST(self):
        if self.path!='/documents':self.reply(404,{'error':'Not found'});return
        size=int(self.headers.get('Content-Length','0'))
        if not 0<size<=2048:self.reply(413,{'error':'Bounded JSON required'});return
        data=json.loads(self.rfile.read(size))
        if set(data)!={'resource_id','user_id'}:self.reply(400,{'error':'Expected resource_id/user_id'});return
        job=submit(data['resource_id'],data['user_id']);pending.put_nowait(job['id'])
        self.reply(202,{'job_id':job['id'],'resource_id':job['resource_id'],'status':job['status']})


if __name__=='__main__':
    threading.Thread(target=worker,daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',18061),Handler).serve_forever()
