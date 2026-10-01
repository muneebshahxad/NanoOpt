# ------------------------------------------------------------------------------
# NanoOpt - High Performance Windows PC Optimizer
# Copyright (C) 2026 Muneeb Shahxad <https://github.com/muneebshahxad>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# ------------------------------------------------------------------------------

import os
import sys
import time
import json
import csv
import logging
from logging.handlers import RotatingFileHandler
import ctypes
import shutil
import subprocess
import threading
import tempfile
from datetime import datetime

# ── 1. UAC ELEVATION ────────────────────────────────────────────────────────
def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

if not is_admin():
    script = os.path.abspath(sys.argv[0])
    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    if getattr(sys, "frozen", False):
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable,
                                             f'"{script}" {params}', None, 1)
    sys.exit(0)

# ── 2. WIN32 API DEFINITIONS ────────────────────────────────────────────────
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_SET_QUOTA          = 0x0100
kernel32 = ctypes.WinDLL("kernel32")
psapi    = ctypes.WinDLL("psapi")

kernel32.OpenProcess.argtypes  = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
kernel32.OpenProcess.restype   = ctypes.c_void_p
kernel32.CloseHandle.argtypes  = [ctypes.c_void_p]
kernel32.CloseHandle.restype   = ctypes.c_bool
psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
psapi.EmptyWorkingSet.restype  = ctypes.c_bool

# ── 3. DIRECTORY RESOLVER ───────────────────────────────────────────────────
def get_app_dir() -> str:
    """Returns the persistent directory where the executable or script is located."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()
APP_VERSION = "1.0.0"
GITHUB_REPO_OWNER = "muneebshahxad"
GITHUB_REPO_NAME = "NanoOpt"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
LOG_FILE = os.path.join(APP_DIR, "nanoopt_activity.log")

# ── 4. CONFIGURABLE JSON SETTINGS MANAGER ───────────────────────────────────
DEFAULT_SETTINGS = {
    "theme": "auto",
    "auto_optimize_ram": True,
    "ram_threshold_percent": 85,
    "auto_clean_cooldown_sec": 300,
    "polling_interval_sec": 1.0,
    "notifications_enabled": True,
    "autostart_enabled": False,
    "whitelisted_processes": [
        "obs64.exe",
        "obs32.exe",
        "explorer.exe",
        "dwm.exe",
        "discord.exe",
        "steam.exe",
        "steamwebhelper.exe"
    ],
    "whitelisted_dirs": []
}

class SettingsManager:
    _instance = None

    def __init__(self):
        self.settings = dict(DEFAULT_SETTINGS)
        self.load()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SettingsManager()
        return cls._instance

    def load(self):
        """Loads settings from settings.json with graceful fallback on corruption."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        # Merge with defaults to ensure all keys exist
                        for k, v in DEFAULT_SETTINGS.items():
                            if k in data and isinstance(data[k], type(v)):
                                self.settings[k] = data[k]
                            else:
                                self.settings[k] = v
                        return
            except Exception as e:
                logging.warning(f"Failed to load settings.json ({e}). Using defaults.")
        self.settings = dict(DEFAULT_SETTINGS)
        self.save()

    def save(self):
        """Atomically saves settings to settings.json."""
        try:
            temp_file = SETTINGS_FILE + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            if os.path.exists(SETTINGS_FILE):
                os.replace(temp_file, SETTINGS_FILE)
            else:
                os.rename(temp_file, SETTINGS_FILE)
        except Exception as e:
            logging.error(f"Failed to save settings.json: {e}")

    def get(self, key, default=None):
        return self.settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.settings[key] = value
        self.save()

# ── 5. ACTIVITY LOGGER & CSV EXPORTER ───────────────────────────────────────
class ActivityLogger:
    _configured = False

    @classmethod
    def setup(cls):
        if cls._configured:
            return
        logger = logging.getLogger("NanoOpt")
        logger.setLevel(logging.INFO)

        # File Handler (Rolling log, max 2MB, 3 backups)
        try:
            handler = RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=3, encoding="utf-8")
            formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        except Exception as e:
            print(f"Could not initialize rotating file logger: {e}")

        cls._configured = True

    @classmethod
    def log_event(cls, event_type: str, freed_mb: float, items_or_procs: int, skipped: int = 0, details: str = ""):
        cls.setup()
        logger = logging.getLogger("NanoOpt")
        msg = f"EVENT={event_type} | FREED_MB={freed_mb:.1f} | COUNT={items_or_procs} | SKIPPED={skipped} | DETAILS={details}"
        logger.info(msg)

    @classmethod
    def export_csv(cls, target_path: str) -> bool:
        """Parses nanoopt_activity.log and exports structured records to CSV."""
        cls.setup()
        records = []
        if not os.path.exists(LOG_FILE):
            return False

        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or "EVENT=" not in line:
                        continue
                    # Parse log line: [2026-09-30 12:00:00] [INFO] EVENT=...
                    try:
                        time_part = line[1:line.find("]")]
                        content = line[line.find("EVENT="):]
                        parts = dict(item.split("=", 1) for item in content.split(" | ") if "=" in item)
                        records.append({
                            "Timestamp": time_part,
                            "Event": parts.get("EVENT", "UNKNOWN"),
                            "Freed_MB": parts.get("FREED_MB", "0.0"),
                            "Count": parts.get("COUNT", "0"),
                            "Skipped": parts.get("SKIPPED", "0"),
                            "Details": parts.get("DETAILS", "")
                        })
                    except Exception:
                        continue

            with open(target_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["Timestamp", "Event", "Freed_MB", "Count", "Skipped", "Details"])
                writer.writeheader()
                writer.writerows(records)
            return True
        except Exception as e:
            logging.error(f"Failed to export activity logs to CSV: {e}")
            return False

# ── 6. WINDOWS TASK SCHEDULER AUTO-START MANAGER ────────────────────────────
class TaskSchedulerManager:
    TASK_NAME = "NanoOpt_AutoStart"

    @classmethod
    def _get_target_exe(cls) -> str:
        if getattr(sys, "frozen", False):
            return sys.executable
        return sys.executable

    @classmethod
    def is_autostart_enabled(cls) -> bool:
        """Checks if the scheduled task exists and is configured."""
        try:
            flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
            res = subprocess.run(
                ["schtasks", "/Query", "/TN", cls.TASK_NAME],
                capture_output=True, text=True, creationflags=flags
            )
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    def set_autostart(cls, enable: bool) -> bool:
        """Creates or removes a Task Scheduler task configured with HighestPrivileges."""
        flags = 0x08000000 if sys.platform == "win32" else 0
        try:
            if enable:
                exe = cls._get_target_exe()
                # Run on logon with HIGHEST privileges to silently bypass UAC on boot
                cmd = [
                    "schtasks", "/Create",
                    "/TN", cls.TASK_NAME,
                    "/TR", f'"{exe}"',
                    "/SC", "ONLOGON",
                    "/RL", "HIGHEST",
                    "/F"
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags)
                return res.returncode == 0
            else:
                cmd = ["schtasks", "/Delete", "/TN", cls.TASK_NAME, "/F"]
                res = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags)
                return res.returncode == 0
        except Exception as e:
            logging.error(f"Task Scheduler configuration error: {e}")
            return False

# ── 7. THIRD-PARTY & QT IMPORTS ─────────────────────────────────────────────
import psutil
import requests
from packaging.version import Version, InvalidVersion
from PySide6.QtCore    import Qt, QThread, Signal, QTimer, QPoint, QSize, QRectF
from PySide6.QtGui     import (QIcon, QPixmap, QPainter, QColor, QPen, QBrush,
                                QFont, QAction, QPolygon, QDesktopServices)
from PySide6.QtWidgets import (QApplication, QWidget, QDialog, QVBoxLayout,
                                QHBoxLayout, QLabel, QSystemTrayIcon, QMenu,
                                QSizePolicy, QFrame, QFileDialog, QLineEdit,
                                QProgressBar)

from qfluentwidgets import (
    BodyLabel, CaptionLabel, SubtitleLabel, TitleLabel,
    PushButton, PrimaryPushButton, SimpleCardWidget,
    ProgressRing, SwitchButton, SpinBox, setTheme, Theme,
    isDarkTheme, SystemThemeListener, MessageBox
)

# ── 8. OPTIMIZATION ENGINES (WITH WHITELISTING) ─────────────────────────────
class OptimizationEngine:
    @staticmethod
    def purge_ram(whitelist_processes=None, is_auto=False):
        """Purges working sets of active processes while strictly skipping whitelisted executables."""
        if whitelist_processes is None:
            whitelist_processes = SettingsManager.get_instance().get("whitelisted_processes", [])
        whitelist_lower = {p.lower().strip() for p in whitelist_processes if p}

        mem_before = psutil.virtual_memory().used
        success = fail = skipped = 0

        for proc in psutil.process_iter(["pid", "name"]):
            pid = proc.info.get("pid")
            name = (proc.info.get("name") or "").lower()
            if pid in (0, 4) or name in whitelist_lower:
                skipped += 1
                continue

            h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_SET_QUOTA, False, pid)
            if h:
                try:
                    if psapi.EmptyWorkingSet(h):
                        success += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
                finally:
                    kernel32.CloseHandle(h)
            else:
                fail += 1

        time.sleep(0.4)
        mem_after = psutil.virtual_memory().used
        saved_mb  = max(0.0, (mem_before - mem_after) / (1024 * 1024))

        event_name = "AUTO_RAM_PURGE" if is_auto else "MANUAL_RAM_PURGE"
        ActivityLogger.log_event(event_name, saved_mb, success, skipped, f"Failed: {fail}")
        return saved_mb, success, fail, skipped

    @staticmethod
    def clean_junk(whitelist_dirs=None):
        """Cleans junk files across Windows temporary stores while respecting directory exclusions."""
        if whitelist_dirs is None:
            whitelist_dirs = SettingsManager.get_instance().get("whitelisted_dirs", [])
        
        # Normalize whitelisted paths
        whitelist_norm = [os.path.normcase(os.path.abspath(d)) for d in whitelist_dirs if d and os.path.exists(d)]

        def is_whitelisted(target_path):
            norm_target = os.path.normcase(os.path.abspath(target_path))
            for w in whitelist_norm:
                if norm_target == w or norm_target.startswith(w + os.sep):
                    return True
            return False

        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        except Exception:
            pass

        paths = [
            os.environ.get("TEMP", ""),
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Temp"),
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "SoftwareDistribution", "Download"),
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Prefetch"),
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Logs"),
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32", "LogFiles"),
            os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Microsoft", "Windows", "WER"),
        ]

        total_freed   = 0
        files_removed = 0
        dirs_skipped  = 0

        for p in paths:
            if not p or not os.path.exists(p) or is_whitelisted(p):
                dirs_skipped += 1
                continue
            for item in os.listdir(p):
                item_path = os.path.join(p, item)
                if is_whitelisted(item_path):
                    dirs_skipped += 1
                    continue
                try:
                    if os.path.isfile(item_path):
                        total_freed += os.path.getsize(item_path)
                        os.remove(item_path)
                        files_removed += 1
                    elif os.path.isdir(item_path):
                        for dp, _, fns in os.walk(item_path):
                            for fn in fns:
                                fp = os.path.join(dp, fn)
                                if not os.path.islink(fp) and not is_whitelisted(fp):
                                    try:
                                        total_freed += os.path.getsize(fp)
                                    except Exception:
                                        pass
                        shutil.rmtree(item_path, ignore_errors=True)
                        files_removed += 1
                except Exception:
                    pass

        freed_mb = total_freed / (1024 * 1024)
        ActivityLogger.log_event("JUNK_CLEAN", freed_mb, files_removed, dirs_skipped, "Temp & Stores cleared")
        return freed_mb, files_removed


# ── 9. BACKGROUND WORKER THREADS ─────────────────────────────────────────────
class MetricsWorker(QThread):
    updated = Signal(float, float, float, float)  # cpu%, ram%, used_gb, total_gb
    auto_ram_triggered = Signal(float)            # current ram%

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_auto_purge = 0.0

    def run(self):
        settings = SettingsManager.get_instance()
        while True:
            interval = max(0.5, float(settings.get("polling_interval_sec", 1.0)))
            cpu = psutil.cpu_percent(interval=interval)
            ram = psutil.virtual_memory()

            used_gb = ram.used / 1073741824
            total_gb = ram.total / 1073741824
            self.updated.emit(cpu, ram.percent, used_gb, total_gb)

            # Auto-RAM Optimization Evaluation
            if settings.get("auto_optimize_ram", True):
                threshold = float(settings.get("ram_threshold_percent", 85))
                cooldown = float(settings.get("auto_clean_cooldown_sec", 300))
                now = time.time()
                if ram.percent >= threshold and (now - self.last_auto_purge) >= cooldown:
                    self.last_auto_purge = now
                    self.auto_ram_triggered.emit(ram.percent)

            time.sleep(0.5)


class RamWorker(QThread):
    finished = Signal(float, int, int, int)  # saved_mb, success, fail, skipped

    def __init__(self, is_auto=False, parent=None):
        super().__init__(parent)
        self.is_auto = is_auto

    def run(self):
        self.finished.emit(*OptimizationEngine.purge_ram(is_auto=self.is_auto))


class JunkWorker(QThread):
    finished = Signal(float, int)  # freed_mb, files

    def run(self):
        self.finished.emit(*OptimizationEngine.clean_junk())


# ── 9b. OTA AUTO-UPDATE WORKERS ─────────────────────────────────────────────
class UpdateChecker(QThread):
    """Background thread that checks GitHub Releases API for a newer version."""
    update_available = Signal(str, str)  # new_version, download_url
    no_update = Signal()
    check_failed = Signal(str)  # error message

    def run(self):
        try:
            resp = requests.get(GITHUB_API_LATEST, timeout=10, headers={
                "Accept": "application/vnd.github.v3+json"
            })
            if resp.status_code == 404:
                self.no_update.emit()
                return
            resp.raise_for_status()
            data = resp.json()

            tag = data.get("tag_name", "").lstrip("vV")
            if not tag:
                self.no_update.emit()
                return

            try:
                remote_ver = Version(tag)
                local_ver = Version(APP_VERSION)
            except InvalidVersion:
                self.no_update.emit()
                return

            if remote_ver <= local_ver:
                self.no_update.emit()
                return

            # Find the .exe asset in the release
            download_url = ""
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith(".exe"):
                    download_url = asset.get("browser_download_url", "")
                    break

            if not download_url:
                self.check_failed.emit("New version found but no .exe asset in release.")
                return

            self.update_available.emit(tag, download_url)

        except requests.ConnectionError:
            self.check_failed.emit("No internet connection.")
        except requests.Timeout:
            self.check_failed.emit("Update check timed out.")
        except Exception as e:
            self.check_failed.emit(f"Update check error: {e}")


class UpdateDownloader(QThread):
    """Downloads the new .exe from GitHub with progress reporting."""
    progress = Signal(int)        # 0-100 percentage
    download_complete = Signal(str)  # path to downloaded file
    download_failed = Signal(str)    # error message

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            resp = requests.get(self.url, stream=True, timeout=120)
            resp.raise_for_status()

            total_size = int(resp.headers.get("content-length", 0))
            dest = os.path.join(tempfile.gettempdir(), "NanoOpt_update.exe")

            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            pct = int((downloaded / total_size) * 100)
                            self.progress.emit(min(pct, 100))

            self.progress.emit(100)
            self.download_complete.emit(dest)

        except Exception as e:
            self.download_failed.emit(f"Download failed: {e}")


def generate_updater_bat(current_exe: str, new_exe: str) -> str:
    """Generates a batch script that swaps the running exe with the downloaded update."""
    bat_path = os.path.join(tempfile.gettempdir(), "nanoopt_updater.bat")
    script = f"""@echo off
timeout /t 2 /nobreak >nul
del /f /q "{current_exe}"
move /y "{new_exe}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
"""
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(script)
    return bat_path

# ── 10. ICON GENERATOR ───────────────────────────────────────────────────────
def get_rocket_icon() -> QIcon:
    """Returns a crisp Rocket emoji (🚀) QIcon for the taskbar and system tray."""
    icon_path = os.path.join(APP_DIR, "icon.png")
    if os.path.exists(icon_path):
        return QIcon(icon_path)

    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    font = QFont("Segoe UI Emoji", 40)
    p.setFont(font)
    p.drawText(px.rect(), Qt.AlignCenter, "🚀")
    p.end()
    return QIcon(px)


# ── 11. COMPACT METRIC CARD ──────────────────────────────────────────────────
class MetricCard(SimpleCardWidget):
    """Clean, theme-adaptive card with a compact ProgressRing."""

    def __init__(self, title: str, ring_color: str, parent=None):
        super().__init__(parent)
        self._ring_color = ring_color
        self.setFixedHeight(94)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        # Header Title
        self.title_lbl = CaptionLabel(title, self)
        lay.addWidget(self.title_lbl, alignment=Qt.AlignLeft)

        # Content Row
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        # ProgressRing (44x44)
        self.ring = ProgressRing(self)
        self.ring.setFixedSize(44, 44)
        self.ring.setStrokeWidth(4.5)
        self.ring.setTextVisible(False)
        self.ring.setValue(0)
        self.ring.setStyleSheet(f"ProgressRing {{ color: {ring_color}; }}")
        row.addWidget(self.ring, alignment=Qt.AlignVCenter)

        # Values
        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(1)

        self.pct_lbl = QLabel("0.0%", self)
        self.pct_lbl.setStyleSheet(
            f"font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
            f"font-size: 18px; font-weight: 600; color: {ring_color};"
        )
        self.pct_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        info.addWidget(self.pct_lbl)

        self.sub_lbl = CaptionLabel("", self)
        info.addWidget(self.sub_lbl)

        row.addLayout(info)
        row.addStretch()
        lay.addLayout(row)

    def set_value(self, pct: float, subtitle: str = ""):
        self.ring.setValue(int(max(0, min(100, pct))))
        self.pct_lbl.setText(f"{pct:.1f}%")
        if subtitle:
            self.sub_lbl.setText(subtitle)


# ── 12. ENHANCED SETTINGS DIALOG ─────────────────────────────────────────────
class SettingsDialog(QDialog):
    """Modern Settings modal for toggles, thresholds, exclusions, and CSV log export."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 420)
        self.settings = SettingsManager.get_instance()
        self._drag_pos = QPoint()

        self._build_ui()
        self._load_values()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # Title Row
        tb = QHBoxLayout()
        title = QLabel("⚙️ Settings & Enhancements")
        dark = isDarkTheme()
        txt_color = "#ffffff" if dark else "#181818"
        title.setStyleSheet(f"color: {txt_color}; font-size: 14px; font-weight: 600;")
        tb.addWidget(title)
        tb.addStretch()

        close_btn = PushButton("✕")
        close_btn.setFixedSize(26, 24)
        close_btn.setStyleSheet(
            "PushButton { background: transparent; border: none; font-size: 11px; }"
            "PushButton:hover { background: #e81123; color: white; border-radius: 4px; }"
        )
        close_btn.clicked.connect(self.accept)
        tb.addWidget(close_btn)
        root.addLayout(tb)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #383838;" if dark else "color: #e0e0e0;")
        root.addWidget(sep)

        # 1. Auto-Optimize RAM Toggle & Threshold
        row1 = QHBoxLayout()
        lbl1 = CaptionLabel("Auto-Purge RAM when usage exceeds:")
        row1.addWidget(lbl1)
        row1.addStretch()
        self.spin_ram = SpinBox()
        self.spin_ram.setRange(50, 99)
        self.spin_ram.setSuffix("%")
        self.spin_ram.setFixedWidth(120)
        self.spin_ram.setFixedHeight(33)
        row1.addWidget(self.spin_ram)
        root.addLayout(row1)

        row1_toggle = QHBoxLayout()
        lbl1_t = CaptionLabel("Enable Background Auto-Purge")
        self.switch_auto_ram = SwitchButton()
        row1_toggle.addWidget(lbl1_t)
        row1_toggle.addStretch()
        row1_toggle.addWidget(self.switch_auto_ram)
        root.addLayout(row1_toggle)

        # 2. Run on Startup (Task Scheduler with HighestPrivileges)
        row2 = QHBoxLayout()
        lbl2 = CaptionLabel("Run on Startup (Bypass UAC)")
        self.switch_startup = SwitchButton()
        row2.addWidget(lbl2)
        row2.addStretch()
        row2.addWidget(self.switch_startup)
        root.addLayout(row2)

        # 3. Toast Notifications
        row3 = QHBoxLayout()
        lbl3 = CaptionLabel("Taskbar Toast Notifications")
        self.switch_notif = SwitchButton()
        row3.addWidget(lbl3)
        row3.addStretch()
        row3.addWidget(self.switch_notif)
        root.addLayout(row3)

        # 4. Process Whitelist
        lbl4 = CaptionLabel("Process Exclusions (comma-separated):")
        root.addWidget(lbl4)
        self.txt_whitelist = QLineEdit()
        self.txt_whitelist.setPlaceholderText("obs64.exe, explorer.exe, discord.exe")
        self.txt_whitelist.setStyleSheet(
            "QLineEdit { border: 1px solid #3d3d3d; border-radius: 5px; padding: 4px; background: #252525; color: #fff; }"
            if dark else
            "QLineEdit { border: 1px solid #ccc; border-radius: 5px; padding: 4px; background: #fff; color: #000; }"
        )
        root.addWidget(self.txt_whitelist)

        # 5. Export Activity Logs Button & View Log Button
        log_row = QHBoxLayout()
        self.btn_export_csv = PrimaryPushButton("📊 Export CSV")
        self.btn_export_csv.setFixedHeight(30)
        self.btn_export_csv.clicked.connect(self._on_export_csv)

        self.btn_view_log = PushButton("📂 Open Log")
        self.btn_view_log.setFixedHeight(30)
        self.btn_view_log.clicked.connect(self._on_open_log)

        log_row.addWidget(self.btn_export_csv)
        log_row.addWidget(self.btn_view_log)
        root.addLayout(log_row)

        root.addStretch()

        # Save Button
        self.btn_save = PrimaryPushButton("Save & Apply")
        self.btn_save.setFixedHeight(34)
        self.btn_save.clicked.connect(self._save_values)
        root.addWidget(self.btn_save)

    def _load_values(self):
        self.switch_auto_ram.setChecked(self.settings.get("auto_optimize_ram", True))
        self.spin_ram.setValue(int(self.settings.get("ram_threshold_percent", 85)))
        self.switch_startup.setChecked(TaskSchedulerManager.is_autostart_enabled())
        self.switch_notif.setChecked(self.settings.get("notifications_enabled", True))
        procs = self.settings.get("whitelisted_processes", [])
        self.txt_whitelist.setText(", ".join(procs))

    def _save_values(self):
        self.settings.set("auto_optimize_ram", self.switch_auto_ram.isChecked())
        self.settings.set("ram_threshold_percent", self.spin_ram.value())
        self.settings.set("notifications_enabled", self.switch_notif.isChecked())

        # Update Startup
        target_startup = self.switch_startup.isChecked()
        TaskSchedulerManager.set_autostart(target_startup)
        self.settings.set("autostart_enabled", target_startup)

        # Update Whitelist
        raw = self.txt_whitelist.text()
        procs = [p.strip() for p in raw.split(",") if p.strip()]
        self.settings.set("whitelisted_processes", procs)

        self.accept()

    def _on_export_csv(self):
        default_name = f"NanoOpt_Activity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export Activity Log as CSV", default_name, "CSV Files (*.csv)")
        if path:
            if ActivityLogger.export_csv(path):
                self.btn_export_csv.setText("✓ Exported!")
                QTimer.singleShot(2500, lambda: self.btn_export_csv.setText("📊 Export CSV"))

    def _on_open_log(self):
        if os.path.exists(LOG_FILE):
            os.startfile(LOG_FILE)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        dark = isDarkTheme()
        bg = QColor(28, 28, 28, 252) if dark else QColor(245, 245, 245, 252)
        border = QColor(255, 255, 255, 25) if dark else QColor(0, 0, 0, 25)
        p.setPen(QPen(border, 1))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(rect, 10, 10)
        p.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and not self._drag_pos.isNull():
            self.move(e.globalPosition().toPoint() - self._drag_pos)


# ── 13. MAIN WINDOW ─────────────────────────────────────────────────────────
class NanoOptWindow(QWidget):
    """Frameless, System-Themed NanoOpt Application with General Enhancements."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = QPoint()
        self._busy     = False

        # Compact window size
        self.setFixedSize(380, 290)
        self.setWindowTitle("NanoOpt")
        self.setWindowIcon(get_rocket_icon())

        # Load Settings & Activity Logger
        self.settings = SettingsManager.get_instance()
        ActivityLogger.setup()

        # System Theme Listener
        self.theme_listener = SystemThemeListener(self)
        self.theme_listener.systemThemeChanged.connect(self._on_theme_changed)

        self._build_ui()
        self._apply_theme_styles()
        self._setup_tray()

        # Background Metrics & Auto-Optimization Poller
        self._metrics_worker = MetricsWorker(self)
        self._metrics_worker.updated.connect(self._on_metrics)
        self._metrics_worker.auto_ram_triggered.connect(self._on_auto_ram)
        self._metrics_worker.start()

        # Status Auto-Reset
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._reset_status)

        # OTA Update Checker (delayed 3s after startup)
        self._update_checker = None
        self._update_downloader = None
        self._pending_update_version = None
        QTimer.singleShot(3000, self._check_for_updates)

    def _on_theme_changed(self):
        setTheme(Theme.AUTO)
        self._apply_theme_styles()
        self.update()

    def _apply_theme_styles(self):
        dark = isDarkTheme()
        txt_color = "#ffffff" if dark else "#181818"
        sub_color = "#9e9e9e" if dark else "#616161"
        link_color = "#60cdff" if dark else "#0066cc"

        self._app_lbl.setStyleSheet(
            f"color: {txt_color}; font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
            f"font-size: 15px; font-weight: 600;"
        )

        admin_color = "#22c55e" if dark else "#107c41"
        self._status_lbl.setStyleSheet(
            f"color: {admin_color}; font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
            f"font-size: 11px;"
        )

        # Chrome Buttons
        btn_hover = "#333333" if dark else "#e5e5e5"
        btn_txt   = "#a0a0a0" if dark else "#505050"
        for btn in (self._min_btn, self._settings_btn):
            btn.setStyleSheet(
                f"PushButton {{ background: transparent; border: none;"
                f"color: {btn_txt}; font-size: 12px; }}"
                f"PushButton:hover {{ background: {btn_hover}; border-radius: 5px; color: {txt_color}; }}"
            )
        self._close_btn.setStyleSheet(
            f"PushButton {{ background: transparent; border: none;"
            f"color: {btn_txt}; font-size: 12px; }}"
            f"PushButton:hover {{ background: #e81123; border-radius: 5px; color: #ffffff; }}"
        )

        # Action Buttons (High Contrast Fills)
        if dark:
            ram_style = (
                "QPushButton, PushButton, PrimaryPushButton {"
                "  background: #0284c7; color: #ffffff;"
                "  font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
                "  font-size: 12px; font-weight: 600; border-radius: 6px; border: none;"
                "}"
                "QPushButton:hover, PushButton:hover, PrimaryPushButton:hover { background: #0ea5e9; }"
                "QPushButton:pressed, PushButton:pressed, PrimaryPushButton:pressed { background: #0369a1; }"
                "QPushButton:disabled, PushButton:disabled, PrimaryPushButton:disabled { background: #2a3441; color: #64748b; }"
            )
            junk_style = (
                "QPushButton, PushButton {"
                "  background: #7c3aed; color: #ffffff;"
                "  font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
                "  font-size: 12px; font-weight: 600; border-radius: 6px; border: none;"
                "}"
                "QPushButton:hover, PushButton:hover { background: #8b5cf6; }"
                "QPushButton:pressed, PushButton:pressed { background: #6d28d9; }"
                "QPushButton:disabled, PushButton:disabled { background: #2a3441; color: #64748b; }"
            )
        else:
            ram_style = (
                "QPushButton, PushButton, PrimaryPushButton {"
                "  background: #0284c7; color: #ffffff;"
                "  font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
                "  font-size: 12px; font-weight: 600; border-radius: 6px; border: none;"
                "}"
                "QPushButton:hover, PushButton:hover, PrimaryPushButton:hover { background: #0369a1; }"
                "QPushButton:pressed, PushButton:pressed, PrimaryPushButton:pressed { background: #075985; }"
                "QPushButton:disabled, PushButton:disabled, PrimaryPushButton:disabled { background: #e2e8f0; color: #94a3b8; }"
            )
            junk_style = (
                "QPushButton, PushButton {"
                "  background: #7c3aed; color: #ffffff;"
                "  font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
                "  font-size: 12px; font-weight: 600; border-radius: 6px; border: none;"
                "}"
                "QPushButton:hover, PushButton:hover { background: #6d28d9; }"
                "QPushButton:pressed, PushButton:pressed { background: #5b21b6; }"
                "QPushButton:disabled, PushButton:disabled { background: #e2e8f0; color: #94a3b8; }"
            )

        self._btn_ram.setStyleSheet(ram_style)
        self._btn_junk.setStyleSheet(junk_style)

        # Footer Link
        self._footer_lbl.setText(
            f'NanoOpt v{APP_VERSION} · Developed by <a href="https://github.com/muneebshahxad" '
            f'style="color: {link_color}; text-decoration: none; font-weight: 600;">MuneebShahxad</a>'
        )
        self._footer_lbl.setStyleSheet(
            f"color: {sub_color}; font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
            f"font-size: 10px;"
        )

    # ── UI LAYOUT ───────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(8)

        # Title Bar
        tb = QWidget()
        tb.setFixedHeight(34)
        tb_lay = QHBoxLayout(tb)
        tb_lay.setContentsMargins(8, 0, 0, 0)
        tb_lay.setSpacing(6)

        self._app_lbl = QLabel("NanoOpt")
        tb_lay.addWidget(self._app_lbl)
        tb_lay.addStretch()

        self._settings_btn = PushButton("⚙️")
        self._settings_btn.setFixedSize(28, 26)
        self._settings_btn.setToolTip("Settings & Exclusions")
        self._settings_btn.clicked.connect(self._open_settings)

        self._min_btn = PushButton("─")
        self._min_btn.setFixedSize(28, 26)
        self._min_btn.clicked.connect(self.showMinimized)

        self._close_btn = PushButton("✕")
        self._close_btn.setFixedSize(28, 26)
        self._close_btn.clicked.connect(self._hide_to_tray)

        tb_lay.addWidget(self._settings_btn)
        tb_lay.addWidget(self._min_btn)
        tb_lay.addWidget(self._close_btn)

        tb.mousePressEvent = lambda e: self._drag_press(e)
        tb.mouseMoveEvent  = lambda e: self._drag_move(e)
        self._app_lbl.mousePressEvent = lambda e: self._drag_press(e)
        self._app_lbl.mouseMoveEvent  = lambda e: self._drag_move(e)
        root.addWidget(tb)

        # Status Badge
        self._status_lbl = QLabel("✓  Running as Administrator")
        self._status_lbl.setContentsMargins(8, 0, 0, 0)
        root.addWidget(self._status_lbl)

        # Metric Cards Row
        cards_row = QWidget()
        cards_lay = QHBoxLayout(cards_row)
        cards_lay.setContentsMargins(0, 2, 0, 2)
        cards_lay.setSpacing(10)

        self._cpu_card = MetricCard("CPU Usage", "#f43f5e")
        self._ram_card = MetricCard("RAM Usage", "#0ea5e9")
        cards_lay.addWidget(self._cpu_card)
        cards_lay.addWidget(self._ram_card)
        root.addWidget(cards_row)

        # Action Buttons
        btn_row = QWidget()
        btn_lay = QHBoxLayout(btn_row)
        btn_lay.setContentsMargins(0, 2, 0, 2)
        btn_lay.setSpacing(10)

        self._btn_ram  = PrimaryPushButton("🚀  Boost RAM")
        self._btn_junk = PushButton("🧹  Clean Junk")

        for btn in (self._btn_ram, self._btn_junk):
            btn.setFixedHeight(36)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._btn_ram.clicked.connect(lambda: self._trigger_ram(is_auto=False))
        self._btn_junk.clicked.connect(self._trigger_junk)

        btn_lay.addWidget(self._btn_ram)
        btn_lay.addWidget(self._btn_junk)
        root.addWidget(btn_row)

        # Log Status Banner
        self._log_lbl = CaptionLabel("")
        self._log_lbl.setWordWrap(False)
        self._log_lbl.setAlignment(Qt.AlignCenter)
        self._log_lbl.setFixedHeight(18)
        root.addWidget(self._log_lbl)

        # Footer
        self._footer_lbl = QLabel()
        self._footer_lbl.setTextFormat(Qt.RichText)
        self._footer_lbl.setOpenExternalLinks(True)
        self._footer_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(self._footer_lbl)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    # ── DRAG EVENTS ─────────────────────────────────────────────────────────
    def _drag_press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _drag_move(self, e):
        if e.buttons() & Qt.LeftButton and not self._drag_pos.isNull():
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    # ── SYSTEM THEME BACKGROUND PAINT ───────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        dark = isDarkTheme()
        bg = QColor(28, 28, 28, 250) if dark else QColor(245, 245, 245, 250)
        border = QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 22)

        p.setPen(QPen(border, 1))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(rect, 10, 10)
        p.end()

    # ── METRICS & AUTO-PURGE SLOTS ──────────────────────────────────────────
    def _on_metrics(self, cpu: float, ram_pct: float, used: float, total: float):
        self._cpu_card.set_value(cpu)
        self._ram_card.set_value(ram_pct, f"{used:.1f} GB / {total:.1f} GB")

    def _on_auto_ram(self, ram_pct: float):
        self._trigger_ram(is_auto=True, current_pct=ram_pct)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self._btn_ram.setEnabled(not busy)
        self._btn_junk.setEnabled(not busy)

    # ── RAM PURGE ───────────────────────────────────────────────────────────
    def _trigger_ram(self, is_auto=False, current_pct=0.0):
        if self._busy:
            return
        self._set_busy(True)
        self._btn_ram.setText("Purging…")
        self._log("🚀 RAM purge in progress…", "#0ea5e9")
        w = RamWorker(is_auto=is_auto, parent=self)
        w.finished.connect(lambda saved, s, f, skip: self._on_ram_done(saved, s, f, skip, is_auto, current_pct))
        w.finished.connect(w.deleteLater)
        w.start()

    def _on_ram_done(self, saved_mb: float, success: int, fail: int, skipped: int, is_auto: bool, current_pct: float):
        self._set_busy(False)
        self._btn_ram.setText("🚀  Boost RAM")
        prefix = "⚡ Auto-RAM Purge" if is_auto else "✓ RAM Purge"
        msg = f"{prefix}: {saved_mb:.1f} MB freed ({success} optimized, {skipped} whitelisted)"
        self._log(msg, "#22c55e" if isDarkTheme() else "#107c41")
        self._status_lbl.setText(f"✓  RAM Purge — {saved_mb:.1f} MB freed")
        self._status_timer.start(4500)

        # Taskbar Toast Notification on Auto-Purge
        if is_auto and self.settings.get("notifications_enabled", True) and hasattr(self, "_tray"):
            self._tray.showMessage(
                "NanoOpt Auto-Optimizer",
                f"🚀 Auto-purged {saved_mb:.1f} MB RAM (Usage was {current_pct:.1f}%)",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )

    # ── JUNK CLEAN ──────────────────────────────────────────────────────────
    def _trigger_junk(self):
        if self._busy:
            return
        self._set_busy(True)
        self._btn_junk.setText("Cleaning…")
        self._log("🧹 Scanning & cleaning junk files…", "#a855f7")
        w = JunkWorker(self)
        w.finished.connect(self._on_junk_done)
        w.finished.connect(w.deleteLater)
        w.start()

    def _on_junk_done(self, freed_mb: float, files: int):
        self._set_busy(False)
        self._btn_junk.setText("🧹  Clean Junk")
        msg = f"✓ Junk Clean: {freed_mb:.1f} MB freed ({files} items)"
        self._log(msg, "#22c55e" if isDarkTheme() else "#107c41")
        self._status_lbl.setText(f"✓  Junk Clean — {freed_mb:.1f} MB freed")
        self._status_timer.start(4500)

    # ── LOG + STATUS ────────────────────────────────────────────────────────
    def _log(self, text: str, color: str = None):
        if not color:
            color = "#a0a0a0" if isDarkTheme() else "#606060"
        self._log_lbl.setText(text)
        self._log_lbl.setStyleSheet(
            f"color: {color}; font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
            f"font-size: 11px;"
        )

    def _reset_status(self):
        self._status_lbl.setText("✓  Running as Administrator")
        admin_color = "#22c55e" if isDarkTheme() else "#107c41"
        self._status_lbl.setStyleSheet(
            f"color: {admin_color}; font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
            f"font-size: 11px;"
        )
        self._log_lbl.setText("")

    # ── OTA AUTO-UPDATE ────────────────────────────────────────────────────
    def _check_for_updates(self):
        """Launches the background UpdateChecker thread."""
        self._update_checker = UpdateChecker(self)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.no_update.connect(self._on_no_update)
        self._update_checker.check_failed.connect(self._on_update_check_failed)
        self._update_checker.start()

    def _on_no_update(self):
        logging.info("OTA: App is up to date.")

    def _on_update_check_failed(self, err: str):
        logging.warning(f"OTA: {err}")

    def _on_update_available(self, new_version: str, download_url: str):
        """Shows a MessageBox prompting the user to update."""
        self._pending_update_version = new_version
        self._restore()  # Bring window to front

        dlg = MessageBox(
            f"Update Available — v{new_version}",
            f"A new version of NanoOpt (v{new_version}) is available.\n"
            f"You are currently running v{APP_VERSION}.\n\n"
            f"Would you like to update now?",
            self
        )
        dlg.yesButton.setText("Update Now")
        dlg.cancelButton.setText("Later")

        if dlg.exec():
            self._start_download(download_url)
        else:
            logging.info("OTA: User declined update.")

    def _start_download(self, url: str):
        """Starts the download and shows a progress bar overlay."""
        # Create download progress UI
        self._download_bar = QProgressBar(self)
        self._download_bar.setRange(0, 100)
        self._download_bar.setValue(0)
        self._download_bar.setFixedHeight(18)
        self._download_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #3d3d3d; border-radius: 4px; background: #252525; text-align: center; color: #fff; font-size: 10px; }"
            "QProgressBar::chunk { background: #0ea5e9; border-radius: 3px; }"
            if isDarkTheme() else
            "QProgressBar { border: 1px solid #ccc; border-radius: 4px; background: #f0f0f0; text-align: center; color: #000; font-size: 10px; }"
            "QProgressBar::chunk { background: #0078d4; border-radius: 3px; }"
        )
        self._download_bar.setFormat(f"Downloading v{self._pending_update_version}… %p%")

        # Insert progress bar into layout (above footer)
        main_layout = self.layout()
        if main_layout:
            main_layout.insertWidget(main_layout.count() - 1, self._download_bar)

        self._log(f"⬇ Downloading NanoOpt v{self._pending_update_version}…", "#0ea5e9")
        self._set_busy(True)

        self._update_downloader = UpdateDownloader(url, self)
        self._update_downloader.progress.connect(self._on_download_progress)
        self._update_downloader.download_complete.connect(self._on_download_complete)
        self._update_downloader.download_failed.connect(self._on_download_failed)
        self._update_downloader.start()

    def _on_download_progress(self, pct: int):
        if hasattr(self, "_download_bar"):
            self._download_bar.setValue(pct)

    def _on_download_failed(self, err: str):
        self._set_busy(False)
        self._log(f"✗ {err}", "#f43f5e")
        if hasattr(self, "_download_bar"):
            self._download_bar.setParent(None)
            self._download_bar.deleteLater()
        logging.error(f"OTA: {err}")

    def _on_download_complete(self, downloaded_path: str):
        """Download finished — generate updater.bat, launch it, and exit."""
        self._set_busy(False)
        if hasattr(self, "_download_bar"):
            self._download_bar.setValue(100)

        self._log(f"✓ Download complete. Restarting…", "#22c55e" if isDarkTheme() else "#107c41")
        logging.info(f"OTA: Downloaded update to {downloaded_path}")

        # Determine current exe path
        if getattr(sys, "frozen", False):
            current_exe = os.path.abspath(sys.executable)
        else:
            current_exe = os.path.abspath(sys.argv[0])

        # Generate and run the updater batch script
        bat_path = generate_updater_bat(current_exe, downloaded_path)
        logging.info(f"OTA: Launching updater script: {bat_path}")

        # Launch the batch file silently (hidden window)
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=CREATE_NO_WINDOW,
            close_fds=True
        )

        # Clean shutdown
        self._force_exit = True
        try:
            if hasattr(self, "_metrics_worker") and self._metrics_worker.isRunning():
                self._metrics_worker.terminate()
            if hasattr(self, "_tray"):
                self._tray.hide()
        except Exception:
            pass
        QApplication.quit()
        sys.exit(0)

    # ── SYSTEM TRAY ─────────────────────────────────────────────────────────
    def _setup_tray(self):
        self._tray = QSystemTrayIcon(get_rocket_icon(), self)
        self._tray.setToolTip("NanoOpt — PC Optimizer")

        menu = QMenu()
        act_show   = QAction("Show Dashboard",        self)
        act_sett   = QAction("⚙️  Settings",           self)
        act_export = QAction("📊  Export Logs (CSV)",  self)
        act_boost  = QAction("🚀  Boost RAM Now",      self)
        act_clean  = QAction("🧹  Clean Junk Now",     self)
        act_quit   = QAction("✕   Exit NanoOpt",       self)

        act_show.triggered.connect(self._restore)
        act_sett.triggered.connect(self._open_settings)
        act_export.triggered.connect(self._export_logs_from_tray)
        act_boost.triggered.connect(lambda: self._trigger_ram(is_auto=False))
        act_clean.triggered.connect(self._trigger_junk)
        act_quit.triggered.connect(self._quit_app)

        menu.addAction(act_show)
        menu.addAction(act_sett)
        menu.addAction(act_export)
        menu.addSeparator()
        menu.addAction(act_boost)
        menu.addAction(act_clean)
        menu.addSeparator()
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_click)
        self._tray.show()

    def _export_logs_from_tray(self):
        default_name = f"NanoOpt_Activity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export Activity Log as CSV", default_name, "CSV Files (*.csv)")
        if path:
            ActivityLogger.export_csv(path)

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore()

    def _restore(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _hide_to_tray(self):
        self.hide()

    def _quit_app(self):
        self._force_exit = True
        try:
            if hasattr(self, "_metrics_worker") and self._metrics_worker.isRunning():
                self._metrics_worker.terminate()
            if hasattr(self, "_tray"):
                self._tray.hide()
        except Exception:
            pass
        QApplication.quit()
        sys.exit(0)

    def closeEvent(self, event):
        if getattr(self, "_force_exit", False):
            event.accept()
        else:
            event.ignore()
            self.hide()


# ── 14. ENTRY POINT ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        try:
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("NanoOpt")
    app.setQuitOnLastWindowClosed(False)

    # Initialize Settings & Theme
    setTheme(Theme.AUTO)
    app.setWindowIcon(get_rocket_icon())

    window = NanoOptWindow()
    window.show()
    sys.exit(app.exec())
