from flask import Flask, render_template, request, send_from_directory, jsonify
import os
import random
import shutil

app = Flask(__name__)

# Folder where videos will be stored
VIDEO_DIR = os.path.join('static', 'videos')
os.makedirs(VIDEO_DIR, exist_ok=True)

# Mock trending funny video URLs (replace later with scrapers if you like)
MOCK_VIDEOS = [
    "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4",
    "https://sample-videos.com/video123/mp4/720/sample-5s.mp4",
    "https://sample-videos.com/video123/mp4/720/sample-10s.mp4",
    "https://sample-videos.com/video123/mp4/720/sample-15s.mp4"
]

@app.route('/')
def home():
    """Homepage that lists all downloaded videos"""
    files = [f for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4")]
    files.sort(reverse=True)
    return render_template('index.html', videos=files)

@app.route('/generate', methods=['GET'])
def generate_video():
    """Fake video fetcher — simulates scraping a random trending video"""
    # Pick a random mock video
    url = random.choice(MOCK_VIDEOS)
    filename = f"funny_{random.randint(1000,9999)}.mp4"
    filepath = os.path.join(VIDEO_DIR, filename)
    
    # Download the video file
    import requests
    r = requests.get(url, stream=True)
    with open(filepath, 'wb') as f:
        shutil.copyfileobj(r.raw, f)

    return jsonify({
        "message": "Funny video downloaded successfully!",
        "file": filename,
        "download_url": f"/static/videos/{filename}"
    })

@app.route('/videos/<path:filename>')
def serve_video(filename):
    """Serve video files"""
    return send_from_directory(VIDEO_DIR, filename)

@app.route('/api/list', methods=['GET'])
def list_videos():
    """Return list of all videos in JSON"""
    files = [f"/static/videos/{f}" for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4")]
    return jsonify(files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
