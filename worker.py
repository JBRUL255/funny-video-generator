from generator import generate_final_video
import threading
import queue

job_queue = queue.Queue()
video_metadata = []  # store video URLs and status

def worker_loop():
    while True:
        joke = job_queue.get()
        if joke is None:
            break
        print("[Worker] Generating:", joke)
        url = generate_final_video(joke)
        if url:
            video_metadata.append({"joke": joke, "url": url})
        job_queue.task_done()


def enqueue_job(joke_text):
    job_queue.put(joke_text)


def list_videos_metadata():
    return video_metadata


def start_worker_thread():
    threading.Thread(target=worker_loop, daemon=True).start()
