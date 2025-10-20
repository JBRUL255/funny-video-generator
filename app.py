import os
from flask import Flask, render_template, jsonify, send_from_directory
from worker import enqueue_job, get_job_status, start_worker_thread, list_videos_metadata

app = Flask(__name__)
start_worker_thread()  # start background thread on boot

@app.route('/')
def home():
    videos = list_videos_metadata()
    return render_template("index.html", videos=videos)

@app.route('/generate', methods=['GET'])
def generate_video():
    job_id = enqueue_job()
    return jsonify({"message": "🎬 Video generation started!", "job_id": job_id})

@app.route('/status/<job_id>')
def job_status(job_id):
    return jsonify(get_job_status(job_id))

@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_from_directory("static/videos", filename)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
