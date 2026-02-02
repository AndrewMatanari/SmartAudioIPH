# IPH Smart Audio 2026 - Enhanced Edition
## 🎵 Audio Scheduling System with Hardware Monitoring

## 📋 Fitur Utama

### Audio Control
- ✅ Pemutaran audio manual dengan antrian (queue)
- ✅ Kontrol volume real-time (0-100%)
- ✅ Volume alarm tetap 100% (tidak terpengaruh volume playback)
- ✅ Play, Pause, Next, Stop controls
- ✅ Progress bar dan time display

### Scheduling
- ✅ Penjadwalan alarm berdasarkan hari dan waktu
- ✅ Support multi-day (Senin-Minggu) dan Everyday
- ✅ Filter jadwal per hari
- ✅ Edit dan hapus jadwal

### Hardware Monitoring
- ✅ Status audio devices (USB, ALSA, PulseAudio)
- ✅ CPU usage monitoring
- ✅ CPU temperature monitoring dengan indicator
- ✅ Memory usage (RAM)
- ✅ Disk usage
- ✅ System uptime

### File Management
- ✅ Upload audio files (MP3, WAV, OGG, M4A, FLAC, AAC)
- ✅ Rename files
- ✅ Delete files
- ✅ Upload progress dengan speed indicator

## 🔧 Requirements

### System Requirements
- **OS**: Linux (Ubuntu/Debian/Raspberry Pi)
- **Python**: 3.8+
- **MPV**: Media player
- **Socat**: IPC communication
- **Audio System**: ALSA atau PulseAudio

### Python Dependencies
```
Flask==2.3.0
Flask-SQLAlchemy==3.0.5
Flask-Login==0.6.2
APScheduler==3.10.1
pytz==2023.3
Werkzeug==2.3.0
psutil==5.9.5  # NEW: For system monitoring
```

## 📦 Instalasi

### 1. Install System Dependencies
```bash
sudo apt update
sudo apt install -y mpv socat python3 python3-pip python3-venv
```

### 2. Setup Project
```bash
mkdir -p ~/iph-smart-audio-enhanced
cd ~/iph-smart-audio-enhanced

# Copy files:
# - app_enhanced.py (rename ke app.py)
# - index_enhanced.html (simpan ke templates/index.html)
# - login.html (simpan ke templates/login.html)
# - requirements.txt

# Buat virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Directory Structure
```
iph-smart-audio-enhanced/
├── app.py                    # Backend application
├── templates/
│   ├── index.html           # Main dashboard
│   └── login.html           # Login page
├── music/                   # Audio files (auto-created)
├── database.db             # Database (auto-created)
└── requirements.txt        # Python dependencies
```

### 4. Jalankan Aplikasi
```bash
python app.py
```

Akses: **http://localhost:5000**

**Default Login:**
- Username: `admin`
- Password: `admin123`

## 🎛️ Fitur Baru

### 1. Volume Control
- Slider volume di player
- Range: 0-100%
- Update real-time saat playback
- Volume alarm tetap 100% (fixed)

### 2. Hardware Monitoring

#### CPU Monitoring
- Usage percentage
- Temperature dengan color indicator:
  - 🟢 Hijau: < 50°C (Normal)
  - 🟡 Kuning: 50-70°C (Warm)
  - 🔴 Merah: > 70°C (Hot)

#### Memory Monitoring
- Usage percentage
- Used / Total GB

#### Disk Monitoring
- Usage percentage
- Used / Total GB

#### Audio Devices
- Auto-detect semua audio devices
- Tampilkan status (available, running, idle)
- Highlight device USB yang aktif
- Support ALSA dan PulseAudio

#### System Uptime
- Menampilkan berapa lama server berjalan
- Format: HH:MM:SS

## 🔊 Volume Management

### Playback Volume
- Dikontrol via slider
- Default: 70%
- Range: 0-100%
- Tersimpan dan digunakan untuk semua playback manual

### Alarm Volume
- **TETAP 100%** (tidak bisa diubah)
- Garantasi alarm terdengar jelas
- Tidak terpengaruh setting volume playback

### Cara Kerja
```python
# Playback manual: menggunakan volume slider
Playing: song.mp3 at volume 70%

# Alarm: selalu 100%
Triggering alarm: alarm.mp3 at 100% volume
```

## 🎵 Audio Format Support
- MP3
- WAV
- OGG
- M4A
- FLAC
- AAC
- WMA

## 📱 Responsive Design
- Desktop optimized
- Mobile friendly
- Tablet compatible

## 🔒 Security Features
- Login required untuk semua fungsi
- Password hashing (werkzeug)
- Session management
- CSRF protection via Flask

## ⚙️ Configuration

### Mengubah Port
Edit `app.py`:
```python
app.run(host='0.0.0.0', port=5000)  # Ganti 5000
```

### Mengubah Timezone
Edit `app.py`:
```python
jakarta_tz = pytz.timezone('Asia/Jakarta')  # Ganti timezone
```

### Mengubah Alarm Volume
Edit `app.py`:
```python
ALARM_VOLUME = 100  # Ubah jika perlu (default 100%)
```

### Mengubah Upload Size Limit
Edit `app.py`:
```python
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
```

## 🐛 Troubleshooting

### 1. Temperature Tidak Muncul

#### Raspberry Pi
```bash
# Cek thermal zone
cat /sys/class/thermal/thermal_zone0/temp
```

#### PC/Laptop
```bash
# Install lm-sensors
sudo apt install lm-sensors
sudo sensors-detect
sensors
```

### 2. Audio Device Tidak Terdeteksi

```bash
# Cek ALSA
aplay -l

# Cek PulseAudio
pactl list sinks

# Test playback
mpv --audio-device=help
```

### 3. Volume Control Tidak Bekerja

```bash
# Cek MPV socket
ls -la /tmp/mpv-socket

# Test IPC command
echo '{ "command": ["get_property", "volume"] }' | socat - /tmp/mpv-socket
```

### 4. High CPU Usage

- Normal untuk monitoring real-time
- Update interval: 2 detik (system stats), 0.5 detik (player)
- Bisa dikurangi di code jika perlu

### 5. Memory Monitoring Error

```bash
# Install/reinstall psutil
pip install --upgrade psutil
```

## 🚀 Running as Service

```bash
sudo nano /etc/systemd/system/iph-audio.service
```

```ini
[Unit]
Description=IPH Smart Audio Enhanced Service
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/iph-smart-audio-enhanced
Environment="PATH=/home/YOUR_USERNAME/iph-smart-audio-enhanced/venv/bin"
ExecStart=/home/YOUR_USERNAME/iph-smart-audio-enhanced/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable iph-audio
sudo systemctl start iph-audio
sudo systemctl status iph-audio
```

## 📊 System Resource Usage

### Normal Operation
- CPU: 5-15%
- Memory: 50-100 MB
- Disk I/O: Minimal

### During Playback
- CPU: 10-20%
- Memory: 60-120 MB

### During Upload
- CPU: 15-30%
- Disk I/O: High (temporary)

## 🔄 Update & Maintenance

### Update Dependencies
```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Backup Database
```bash
cp database.db database.db.backup
```

### Clean Cache
```bash
rm -f /tmp/mpv-socket
```

## 📈 Performance Tips

1. **Untuk Raspberry Pi:**
   - Gunakan USB audio device untuk kualitas lebih baik
   - Monitor temperature, gunakan heatsink jika > 70°C
   - Gunakan power supply yang cukup (5V 3A)

2. **Untuk Server:**
   - Gunakan SSD untuk database
   - Set proper file permissions
   - Monitor disk space

3. **Network:**
   - Gunakan wired connection untuk reliability
   - Setup port forwarding jika akses dari luar

## 🎯 Use Cases

### 1. School Bell System
- Upload bel sekolah
- Jadwalkan per jam pelajaran
- Volume 100% untuk alarm
- Monitor system dari browser

### 2. Masjid/Gereja Audio
- Upload adzan/lonceng
- Jadwal otomatis per hari
- Remote control dari anywhere
- Monitor hardware status

### 3. Office Announcement
- Upload announcements
- Schedule meetings
- Control volume per area
- Check system health

### 4. Home Automation
- Wake-up alarm
- Schedule music
- Party mode queue
- Voice announcements

## ❓ FAQ

**Q: Bisa ganti user/password admin?**
A: Ya, edit di database atau buat user baru via code.

**Q: Maksimal berapa file audio?**
A: Tergantung disk space. Rekomendasi < 1000 files.

**Q: Bisa remote access?**
A: Ya, forward port 5000 atau gunakan reverse proxy (nginx).

**Q: CPU temp tidak akurat?**
A: Normal, sensor berbeda per hardware. Yang penting trend-nya.

**Q: Volume alarm bisa diubah?**
A: Bisa, edit ALARM_VOLUME di app.py, tapi tidak rekomen.

**Q: Support Bluetooth speaker?**
A: Ya, pair dulu via sistem, MPV auto-detect.

## 📞 Support

- GitHub Issues
- Email: support@example.com
- Documentation: https://docs.example.com

## 📄 License
MIT License - Free to use and modify

## 🙏 Credits
- Flask Framework
- MPV Media Player
- Bootstrap 5
- Font Awesome Icons
- psutil Library

---
**Version**: 2.0 Enhanced  
**Last Updated**: January 2026  
**Maintainer**: IPH Team