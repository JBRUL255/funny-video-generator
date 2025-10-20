import os, time, json, threading, queue, random
from pathlib import Path
from generator import generate_final_video  # main generation function (sync)
# simple sqlite job store
DB = "jobs.db"
q = queue.Queue()
job_meta = {}   # in-memory quick status copy (id -> dict)
_lock = threading.Lock()
JOB_ID_SEQ = 0
VIDEO_DIR = Path("static/videos"); VIDEO_DIR.mkdir(exist_ok=True)

def _next_job_id():
    global JOB_ID_SEQ
    with _lock:
        JOB_ID_SEQ += 1
        return JOB_ID_SEQ

def enqueue_job():
    jid = _next_job_id()
    job_meta[jid] = {"job_id": jid, "status": "queued", "msg": "Queued", "filename": None, "cloud_url": None, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
    q.put(jid)
    return jid

def get_job_status(jid):
    return job_meta.get(jid)

def worker_loop():
    while True:
        jid = q.get()
        if jid is None:
            break
        job_meta[jid].update({"status":"started", "msg":"Starting generation"})
        try:
            # call main generator: returns dict with filename, local_path, cloud_url
            job_meta[jid].update({"msg":"generating..."} )
            result = generate_final_video(progress_cb=lambda m: job_meta[jid].update({"msg": m}))
            if not result:
                raise Exception("Generation returned nothing")
            job_meta[jid].update({
                "status":"done",
                "msg":"done",
                "filename": result.get("filename"),
                "cloud_url": result.get("cloud_url")
            })
        except Exception as e:
            job_meta[jid].update({"status":"error", "msg": str(e)})
        q.task_done()

_worker_thread = None
def start_worker_thread():
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_thread = threading.Thread(target=worker_loop, daemon=True)
    _worker_thread.start()

# helper used by API
def list_videos_metadata():
    # scan static/videos folder and return metadata list
    out=[]
    for p in sorted(VIDEO_DIR.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        out.append({
            "filename": p.name,
            "local_url": f"/videos/{p.name}",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime)),
            "status": "ready",
            "cloud_url": None
        })
    # append active/finished jobs info
    for mj in job_meta.values():
        if mj.get("filename"):
            # ensure unique
            found = any(x["filename"]==mj["filename"] for x in out)
            if not found:
                out.insert(0, {"filename": mj["filename"], "local_url": f"/videos/{mj['filename']}", "created_at": mj["created_at"], "status": mj["status"], "cloud_url": mj.get("cloud_url")})
    return out
