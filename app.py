from flask import Flask, jsonify, render_template, request
from worker import enqueue_job, start_worker_thread, list_videos_metadata
import random

app = Flask(__name__)

start_worker_thread()

JOKES = [
    "Why did the cat sit on the computer? To keep an eye on the mouse!",
    "What did one ocean say to the other? Nothing, they just waved!",
    "Why don’t skeletons fight each other? They don’t have the guts.",
    "What did the traffic light say to the car? Don’t look, I’m changing!",
    "Why was the math book sad? It had too many problems!"
]

@app.route("/")
def index():
    videos = list_videos_metadata()
    return render_template("index.html", videos=videos)

@app.route("/generate", methods=["POST"])
def generate():
    joke = random.choice(JOKES)
    enqueue_job(joke)
    return jsonify({"message": "Video generation started", "joke": joke})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
