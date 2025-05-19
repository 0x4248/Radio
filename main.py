import os
import time
import threading
import subprocess
import random
from flask import Flask, send_from_directory

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CHANNEL_DIR = os.path.join(BASE_DIR, "channels")
SILENCE_FILE = os.path.join(BASE_DIR, "silence.wav")
STREAM_DIR = os.path.join(BASE_DIR, "streams")
INFO_FILE = os.path.join(BASE_DIR, "info.txt")

CHANNELS = ["ch1", "ch2"]
QUALITIES = {
    "hq": {"bitrate": "256k", "samplerate": "44100"},
    "lq": {"bitrate": "64k", "samplerate": "22050"},
}

def load_titles():
    try:
        with open(INFO_FILE, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        return ["Channel 1", "Channel 2"]

TITLES = load_titles()

def build_looping_stream_command(input_file, out_dir, quality, title):
    return [
        'ffmpeg',
        '-re',
        '-stream_loop', '-1', '-i', input_file,  # Main audio
        '-stream_loop', '-1', '-i', SILENCE_FILE,  # Static overlay
        '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=3,volume=1[a]',
        '-map', '[a]',
        '-metadata', f'title={title}',
        '-acodec', 'aac',
        '-ar', quality['samplerate'],
        '-b:a', quality['bitrate'],
        '-f', 'hls',
        '-hls_time', '6',
        '-hls_list_size', '6',
        '-hls_flags', 'delete_segments',
        os.path.join(out_dir, 'index.m3u8')
    ]

def stream_channel(channel_name, index):
    while True:
        audio_dir = os.path.join(CHANNEL_DIR, channel_name)
        files = sorted([
            os.path.join(audio_dir, f) for f in os.listdir(audio_dir)
            if f.endswith(('.mp3', '.wav'))
        ]) or [SILENCE_FILE]

        title = TITLES[index] if index < len(TITLES) else channel_name

        for quality_key, quality in QUALITIES.items():
            out_path = os.path.join(STREAM_DIR, channel_name, quality_key)
            os.makedirs(out_path, exist_ok=True)

            input_file = random.choice(files)
            cmd = build_looping_stream_command(input_file, out_path, quality, title)
            print(f"Streaming {channel_name}-{quality_key} with {os.path.basename(input_file)} - Title: {title}")
            proc = subprocess.Popen(cmd)

            time.sleep(300)  # Switch track every 5 minutes
            proc.terminate()

@app.route("/stream/<channel>/<quality>/index.m3u8")
def stream(channel, quality):
    if channel not in CHANNELS or quality not in QUALITIES:
        return "Invalid channel or quality", 404
    path = os.path.join(STREAM_DIR, channel, quality)
    return send_from_directory(path, "index.m3u8")

@app.route("/stream/<channel>/<quality>/<segment>")
def segment(channel, quality, segment):
    path = os.path.join(STREAM_DIR, channel, quality)
    return send_from_directory(path, segment)

@app.route("/stream/<channel>/index.m3u8")
def ch_shorturl(channel):
    if channel not in CHANNELS:
        return "Invalid channel or quality", 404
    path = os.path.join(STREAM_DIR, channel, "hq")
    return send_from_directory(path, "index.m3u8")

@app.route("/stream/<channel>/<segment>")
def ch_shorturl_segment(channel, segment):
    if channel not in CHANNELS:
        return "Invalid channel or quality", 404
    path = os.path.join(STREAM_DIR, channel, "hq")
    return send_from_directory(path, segment)

def start_streams():
    for index, channel in enumerate(CHANNELS):
        t = threading.Thread(target=stream_channel, args=(channel, index), daemon=True)
        t.start()

if __name__ == "__main__":
    os.makedirs(STREAM_DIR, exist_ok=True)
    start_streams()
    app.run(host="0.0.0.0", port=8080)
