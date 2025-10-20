import os
import random
import threading
import requests
from flask import Flask, render_template, jsonify, send_from_directory
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
VIDEO_DIR = "static/videos"
os.makedirs(VIDEO_DIR, exist_ok=True)

# Mock trending funny 360p videos (can replace with Pexels API)
MOCK_VIDEOS = [
    "https://sample-videos.com/video123/mp4/360/big_buck_bunny_360p_5mb.mp4",
    "https://sample-videos.com/video123/mp4/360/sample-5s.mp4",
    "https://sample-videos.com/video123/mp4/360/sample-10s.mp4",
    "https://sample-videos.com/video123/mp4/360/sample-15s.mp4",
]

# -----------------------------
# Utility: Download video safely
# -----------------------------
def download_video(url, filepath):
    try:
        r = requests.get(url, stream=True, timeout=25)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✅ Download complete: {filepath}")
    except Exception as e:
        print(f"❌ Error downloading {url}: {e}")

# -----------------------------
# Generate New Video Endpoint
# -----------------------------
@app.route("/generate")
def generate_video():
    try:
        url = random.choice(MOCK_VIDEOS)
        filename = f"funny_{random.randint(1000,9999)}.mp4"
        filepath = os.path.join(VIDEO_DIR, filename)

        # Run async download
        threading.Thread(target=download_video, args=(url, filepath)).start()

        return jsonify({
            "message": "🎬 Video download started in background!",
            "file": filename,
            "download_link": f"/videos/{filename}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------
# Serve Static Videos
# -----------------------------
@app.route("/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEO_DIR, filename)

# -----------------------------
# Homepage Route
# -----------------------------
@app.route("/")
def index():
    videos = [f for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4")]
    videos.sort(reverse=True)
    return render_template("index.html", videos=videos)

# -----------------------------
# Prefetch Scheduler
# -----------------------------
def prefetch_videos():
    print("🔁 Prefetching funny videos...")
    for _ in range(3):
        try:
            url = random.choice(MOCK_VIDEOS)
            filename = f"cached_{random.randint(1000,9999)}.mp4"
            filepath = os.path.join(VIDEO_DIR, filename)
            download_video(url, filepath)
        except Exception as e:
            print(f"Prefetch error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(prefetch_videos, "interval", hours=1)
scheduler.start()

# -----------------------------
# Run Flask
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
