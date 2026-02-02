import os, subprocess, threading, json, time, pytz
from datetime import datetime
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

# Global State Monitoring
player_state = {
    "current_file": "Ready / Tidak ada audio",
    "is_playing": False,
    "is_paused": False,
    "is_alarm": False,
    "time_pos": 0,
    "duration": 0,
    "percent": 0,
    "volume": 100
}

# --- Model Database ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(5), nullable=False) # Format HH:MM
    day = db.Column(db.String(20), nullable=False)
    audio_file = db.Column(db.String(100), nullable=False)

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

# --- Logika MPV IPC ---
def send_ipc(cmd_list):
    if not os.path.exists(IPC_SOCKET): return False
    try:
        cmd = json.dumps({"command": cmd_list}) + "\n"
        p = subprocess.Popen(['socat', '-', f'UNIX-CONNECT:{IPC_SOCKET}'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        p.communicate(input=cmd.encode(), timeout=0.1)
        return True
    except: return False

def get_mpv_prop(prop):
    if not os.path.exists(IPC_SOCKET): return 0
    try:
        cmd = json.dumps({"command": ["get_property", prop]}) + "\n"
        p = subprocess.Popen(['socat', '-', f'UNIX-CONNECT:{IPC_SOCKET}'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        res, _ = p.communicate(input=cmd.encode(), timeout=0.1)
        return json.loads(res.decode()).get('data', 0)
    except: return 0

# --- Fungsi Inti Putar Audio ---
def play_audio(filename, is_alarm=False):
    global player_state
    
    # Interupsi: Jika ada musik manual, jeda dulu
    was_playing_manual = False
    if is_alarm and player_state["is_playing"] and not player_state["is_alarm"]:
        send_ipc(["set_property", "pause", True])
        was_playing_manual = True
        time.sleep(0.5)

    if not is_alarm:
        subprocess.run(["pkill", "-9", "mpv"], stderr=subprocess.DEVNULL)
        time.sleep(0.5)

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        old_file = player_state["current_file"]
        player_state.update({"current_file": filename, "is_playing": True, "is_alarm": is_alarm})
        
        if is_alarm:
            # Putar alarm (Blocking) - Volume paksa 100
            subprocess.run(["mpv", "--no-video", "--audio-device=alsa/plughw:1,0", "--volume=100", file_path])
            
            # Resume musik manual setelah alarm selesai
            if was_playing_manual:
                player_state.update({"current_file": old_file, "is_alarm": False})
                send_ipc(["set_property", "pause", False])
            else:
                player_state.update({"current_file": "Ready / Tidak ada audio", "is_playing": False, "is_alarm": False})
        else:
            # Putar Manual (IPC enabled)
            subprocess.run(["mpv", "--no-video", "--audio-device=alsa/plughw:1,0", f"--volume={player_state['volume']}", f"--input-ipc-server={IPC_SOCKET}", file_path])
            player_state.update({"current_file": "Ready / Tidak ada audio", "is_playing": False, "percent": 0})

# --- Scheduler Engine ---
scheduler = BackgroundScheduler(timezone=jakarta_tz)
scheduler.start()

def reload_jobs():
    scheduler.remove_all_jobs()
    with app.app_context():
        for s in Schedule.query.all():
            h, m = s.time.split(':')
            day_map = {'Monday':'mon','Tuesday':'tue','Wednesday':'wed','Thursday':'thu','Friday':'fri','Saturday':'sat','Sunday':'sun'}
            scheduler.add_job(play_audio, 'cron', day_of_week=day_map.get(s.day), hour=h, minute=m, args=[s.audio_file, True])

# --- Routes ---
@app.route('/')
@login_required
def index():
    schedules = Schedule.query.order_by(Schedule.time).all()
    files = sorted(os.listdir(app.config['UPLOAD_FOLDER'])) if os.path.exists(app.config['UPLOAD_FOLDER']) else []
    return render_template('index.html', schedules=schedules, files=files)

@app.route('/get_status')
def get_status():
    global player_state
    if player_state["is_playing"] and os.path.exists(IPC_SOCKET):
        player_state["time_pos"] = get_mpv_prop("time-pos")
        player_state["duration"] = get_mpv_prop("duration")
        if player_state["duration"] > 0:
            player_state["percent"] = (player_state["time_pos"] / player_state["duration"]) * 100
    
    state = player_state.copy()
    state["server_time"] = datetime.now(jakarta_tz).strftime("%H:%M:%S")
    return jsonify(state)

@app.route('/audio/volume/<int:level>')
@login_required
def set_volume(level):
    global player_state
    level = max(0, min(100, level))
    player_state["volume"] = level
    if not player_state["is_alarm"]: send_ipc(["set_property", "volume", level])
    return jsonify({"status": "ok"})

@app.route('/audio/<action>')
@login_required
def control_audio(action):
    if action == "pause": send_ipc(["set_property", "pause", True])
    elif action == "resume": send_ipc(["set_property", "pause", False])
    elif action == "stop": subprocess.run(["pkill", "-9", "mpv"])
    return jsonify({"status": "ok"})

@app.route('/add_schedule', methods=['POST'])
@login_required
def add_schedule():
    new_s = Schedule(time=request.form['time'], day=request.form['day'], audio_file=request.form['audio_file'])
    db.session.add(new_s); db.session.commit(); reload_jobs()
    return redirect(url_for('index'))

@app.route('/edit_schedule/<int:id>', methods=['POST'])
@login_required
def edit_schedule(id):
    s = db.session.get(Schedule, id)
    if s:
        s.time, s.audio_file = request.form['time'], request.form['audio_file']
        db.session.commit(); reload_jobs()
    return redirect(url_for('index'))

@app.route('/delete_schedule/<int:id>')
@login_required
def delete_schedule(id):
    s = db.session.get(Schedule, id); db.session.delete(s); db.session.commit(); reload_jobs()
    return redirect(url_for('index'))

@app.route('/play_test/<f>')
@login_required
def play_test(f):
    threading.Thread(target=play_audio, args=(f, False)).start()
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
        if user and check_password_hash(user.password, request.form['password']): login_user(user); return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

if __name__ == '__main__':
    if not os.path.exists(MUSIC_FOLDER): os.makedirs(MUSIC_FOLDER)
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password=generate_password_hash('admin123', method='pbkdf2:sha256')))
            db.session.commit()
        reload_jobs()
    app.run(host='0.0.0.0', port=5000)