import threading, time, uuid
from generator import generate_final_video, VIDEO_DIR

jobs = {}
lock = threading.Lock()

def enqueue_job():
    job_id = str(uuid.uuid4())
    with lock:
        jobs[job_id] = {"status": "queued", "filename": None, "cloudinary_url": None}
    threading.Thread(target=process_job, args=(job_id,)).start()
    return job_id

def process_job(job_id):
    with lock:
        jobs[job_id]["status"] = "processing"
    try:
        filename, cloud_url = generate_final_video()
        with lock:
            jobs[job_id]["status"] = "done"
            jobs[job_id]["filename"] = filename
            jobs[job_id]["cloudinary_url"] = cloud_url
    except Exception as e:
        with lock:
            jobs[job_id]["status"] = f"error: {e}"

def get_job_status(job_id):
    return jobs.get(job_id, {"status": "unknown"})

def list_videos_metadata():
    return [f for f in VIDEO_DIR.glob("*.mp4")]

def start_worker_thread():
    print("✅ Worker thread ready.")
