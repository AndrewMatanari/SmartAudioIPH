import os
import subprocess
import threading
import json
import time
from datetime import datetime
import pytz 
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "iph_smart_audio_master_2026"
jakarta_tz = pytz.timezone('Asia/Jakarta')

# --- Konfigurasi Path & Database ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
MUSIC_FOLDER = os.path.join(BASE_DIR, 'music')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
app.config['UPLOAD_FOLDER'] = MUSIC_FOLDER
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
IPC_SOCKET = "/tmp/mpv-socket"

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Global State
player_state = {
    "current_file": "Tidak ada audio diputar",
    "is_playing": False,
    "is_paused": False,
    "time_pos": 0,
    "duration": 0,
    "percent": 0,
    "volume": 100,
    "usb_label": "Mencari USB...",
    "queue": [],
    "manual_interrupted": False
}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(5), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    audio_file = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Logika Hardware & MPV ---
def find_usb_device():
    try:
        output = subprocess.check_output(["aplay", "-L"]).decode('utf-8')
        for line in output.splitlines():
            if "CARD=Device" in line and "default" in line:
                return line.strip()
    except: pass
    return None

def send_ipc(cmd_list):
    if not os.path.exists(IPC_SOCKET): return False
    try:
        cmd = json.dumps({"command": cmd_list}) + "\n"
        process = subprocess.Popen(['socat', '-', f'UNIX-CONNECT:{IPC_SOCKET}'], 
                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        process.communicate(input=cmd.encode(), timeout=0.2)
        return True
    except: return False

def get_mpv_prop(prop):
    if not os.path.exists(IPC_SOCKET): return 0
    try:
        cmd = json.dumps({"command": ["get_property", prop]}) + "\n"
        process = subprocess.Popen(['socat', '-', f'UNIX-CONNECT:{IPC_SOCKET}'], 
                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        response, _ = process.communicate(input=cmd.encode(), timeout=0.2)
        return json.loads(response.decode()).get('data', 0)
    except: return 0

# --- Pemutar Antrean Manual ---
def play_worker():
    global player_state
    while player_state["queue"]:
        file_to_play = player_state["queue"].pop(0)
        run_mpv(file_to_play)

def run_mpv(filename):
    global player_state
    usb_device = find_usb_device()
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(file_path): return

    player_state.update({"current_file": filename, "is_playing": True, "is_paused": False})
    dev_flag = f"alsa/{usb_device}" if usb_device else "alsa/plughw:1,0"
    
    # Menjalankan MPV (Blocking sampai lagu selesai)
    subprocess.run(["mpv", "--no-video", f"--audio-device={dev_flag}", 
                    f"--volume={player_state['volume']}",
                    f"--input-ipc-server={IPC_SOCKET}", file_path])
    
    player_state.update({"current_file": "Tidak ada audio diputar", "is_playing": False, "percent": 0})

# --- Pemutar Alarm (Priority) ---
def trigger_alarm(filename):
    global player_state
    # 1. Pause lagu manual jika ada
    was_playing = player_state["is_playing"] and not player_state["is_paused"]
    if was_playing:
        send_ipc(["set_property", "pause", True])
        player_state["manual_interrupted"] = True

    # 2. Putar Alarm - Volume Paksa 100%
    usb_device = find_usb_device()
    dev_flag = f"alsa/{usb_device}" if usb_device else "alsa/plughw:1,0"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Gunakan subprocess mandiri untuk alarm
    subprocess.run(["mpv", "--no-video", f"--audio-device={dev_flag}", "--volume=100", file_path])

    # 3. Resume lagu manual
    if player_state["manual_interrupted"]:
        send_ipc(["set_property", "pause", False])
        player_state["manual_interrupted"] = False

# --- Scheduler ---
scheduler = BackgroundScheduler(timezone=jakarta_tz)
scheduler.start()

def reload_jobs():
    scheduler.remove_all_jobs()
    with app.app_context():
        for s in Schedule.query.all():
            h, m = s.time.split(':')
            day_map = {'Everyday': '*', 'Monday': 'mon', 'Tuesday': 'tue', 'Wednesday': 'wed',
                       'Thursday': 'thu', 'Friday': 'fri', 'Saturday': 'sat', 'Sunday': 'sun'}
            scheduler.add_job(trigger_alarm, 'cron', day_of_week=day_map.get(s.day, '*'), 
                              hour=h, minute=m, args=[s.audio_file])

# --- Flask Routes ---
@app.route('/')
@login_required
def index():
    schedules = Schedule.query.order_by(Schedule.time).all()
    files = sorted(os.listdir(app.config['UPLOAD_FOLDER'])) if os.path.exists(app.config['UPLOAD_FOLDER']) else []
    return render_template('index.html', schedules=schedules, files=files)

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    file = request.files.get('file')
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash(f'File {filename} berhasil diunggah!')
    return redirect(url_for('index'))

@app.route('/audio/add_queue/<f>')
@login_required
def add_queue(f):
    player_state["queue"].append(f)
    if not player_state["is_playing"]:
        threading.Thread(target=play_worker).start()
    return jsonify({"status": "queued", "queue": player_state["queue"]})

@app.route('/get_status')
def get_status():
    usb_active = find_usb_device()
    player_state["usb_label"] = "🎸 USB PnP Audio Aktif" if usb_active else "⚠️ USB Terputus"
    
    if player_state["is_playing"] and os.path.exists(IPC_SOCKET):
        player_state["time_pos"] = get_mpv_prop("time-pos")
        player_state["duration"] = get_mpv_prop("duration")
        if player_state["duration"] > 0:
            player_state["percent"] = (player_state["time_pos"] / player_state["duration"]) * 100
    
    res = player_state.copy()
    res["server_time"] = datetime.now(jakarta_tz).strftime("%H:%M:%S")
    return jsonify(res)

@app.route('/audio/<action>')
@login_required
def control_audio(action):
    if action == "pause": 
        if send_ipc(["set_property", "pause", True]): player_state["is_paused"] = True
    elif action == "resume": 
        if send_ipc(["set_property", "pause", False]): player_state["is_paused"] = False
    elif action == "stop": 
        send_ipc(["quit"])
        player_state["queue"] = []
        player_state["is_playing"] = False
    return jsonify(player_state)

@app.route('/audio/volume/<int:level>')
@login_required
def set_volume(level):
    level = max(0, min(100, level))
    player_state["volume"] = level
    send_ipc(["set_property", "volume", level])
    return jsonify({"status": "success", "volume": level})

@app.route('/add_schedule', methods=['POST'])
@login_required
def add_schedule():
    new_s = Schedule(time=request.form['time'], day=request.form['day'], 
                     audio_file=request.form['audio_file'], description=request.form['description'])
    db.session.add(new_s); db.session.commit(); reload_jobs()
    return redirect(url_for('index'))

@app.route('/delete_schedule/<int:id>')
@login_required
def delete_schedule(id):
    s = db.session.get(Schedule, id)
    if s: db.session.delete(s); db.session.commit(); reload_jobs()
    return redirect(url_for('index'))

@app.route('/delete_file/<f>')
@login_required
def delete_file(f):
    path = os.path.join(app.config['UPLOAD_FOLDER'], f)
    if os.path.exists(path): os.remove(path)
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user); return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists(MUSIC_FOLDER): os.makedirs(MUSIC_FOLDER)
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password=generate_password_hash('admin123')))
            db.session.commit()
        reload_jobs()
    app.run(host='0.0.0.0', port=5000)