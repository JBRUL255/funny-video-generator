import os, json, time, random, sqlite3, threading
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_from_directory, Response
from apscheduler.schedulers.background import BackgroundScheduler
from worker import enqueue_job, get_job_status, start_worker_thread, list_videos_metadata

# Config
PORT = int(os.getenv("PORT", 10000))
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 5))
VIDEO_DIR = Path("static/videos")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")

# ensure worker is running once at app start
start_worker_thread()

@app.route("/")
def index():
    return render_template("index.html")

# start a generate job (non-blocking)
@app.route("/api/generate", methods=["POST"])
def api_generate():
    # daily limit check
    created_today = len([v for v in list_videos_metadata() if v.get("created_at","").startswith(time.strftime("%Y-%m-%d"))])
    if created_today >= DAILY_LIMIT:
        return jsonify({"error": f"Daily limit reached ({DAILY_LIMIT})"}), 429
    job_id = enqueue_job()
    return jsonify({"job_id": job_id})

# SSE events for job progress
@app.route("/events/<int:job_id>")
def events(job_id):
    def event_stream():
        last = ""
        while True:
            st = get_job_status(job_id)
            if not st:
                yield f'data: {json.dumps({"msg":"job not found","status":"error"})}\n\n'
                break
            # only send when changed or every 2s
            s = json.dumps(st)
            if s != last:
                last = s
                yield f'data: {s}\n\n'
            if st.get("status") in ("done","error"):
                break
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")

# list videos with metadata
@app.route("/api/videos")
def api_videos():
    return jsonify(list_videos_metadata())

# serve video files (local)
@app.route("/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(str(VIDEO_DIR), filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
