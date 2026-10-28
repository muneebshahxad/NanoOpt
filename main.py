# ------------------------------------------------------------------------------
# NanoOpt - High Performance Windows PC Optimizer
# Copyright (c) 2026 MuneebShahxad. All Rights Reserved.
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
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
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
import webbrowser
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
APP_VERSION = "1.3.0"
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
    "whitelisted_dirs": [],
    "game_mode_enabled": False,
    "clean_browser_cache": False,
    "clean_media_cache": False,
    "show_logs": True
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
    isDarkTheme, SystemThemeListener, MessageBox, TextEdit
)

# ── 8. OPTIMIZATION ENGINES (WITH WHITELISTING) ─────────────────────────────
class OptimizationEngine:
    @staticmethod
    def purge_ram(whitelist_processes=None, is_auto=False, log_callback=None):
        """Purges working sets of active processes while strictly skipping whitelisted executables."""
        if log_callback:
            prefix = "⚡ Auto-RAM" if is_auto else "🚀 RAM"
            log_callback(f"{prefix} scan initiated...", "#38bdf8")

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
        saved_gb  = saved_mb / 1024.0

        if log_callback:
            if skipped > 0:
                log_callback(f"Skipped {skipped} whitelisted / system processes", "#facc15")
            if saved_gb >= 1.0:
                freed_str = f"{saved_gb:.2f} GB ({saved_mb:.1f} MB)"
            else:
                freed_str = f"{saved_mb:.1f} MB"
            log_callback(f"RAM Boosted: Flushed working set for {success} processes. Freed {freed_str}", "#22c55e")
            if fail > 0:
                log_callback(f"Protected: {fail} Windows kernel processes preserved", "#94a3b8")

        event_name = "AUTO_RAM_PURGE" if is_auto else "MANUAL_RAM_PURGE"
        ActivityLogger.log_event(event_name, saved_mb, success, skipped, f"Failed: {fail}")
        return saved_mb, success, fail, skipped

    @staticmethod
    def clean_shader_cache():
        """Clears DirectX and OpenGL/Vulkan GPU shader caches."""
        localappdata = os.environ.get("LOCALAPPDATA", "")
        paths = [
            os.path.join(localappdata, "D3DSCache") if localappdata else "",
            os.path.join(localappdata, "NVIDIA", "DXCache") if localappdata else "",
            os.path.join(localappdata, "NVIDIA", "GLCache") if localappdata else "",
            os.path.join(localappdata, "AMD", "DxCache") if localappdata else "",
            os.path.join(localappdata, "AMD", "GLCache") if localappdata else "",
            os.path.join(localappdata, "Intel", "ShaderCache") if localappdata else "",
        ]
        total_freed = 0
        files_removed = 0
        for p in paths:
            if not p or not os.path.exists(p):
                continue
            for dp, _, fns in os.walk(p):
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    try:
                        sz = os.path.getsize(fp)
                        os.remove(fp)
                        total_freed += sz
                        files_removed += 1
                    except Exception:
                        pass
        freed_mb = total_freed / (1024 * 1024)
        ActivityLogger.log_event("SHADER_CACHE_CLEAN", freed_mb, files_removed, 0, "Shader Caches cleared")
        return freed_mb, files_removed

    @staticmethod
    def clean_junk(whitelist_dirs=None, log_callback=None):
        """
        Advanced Windows Deep-Cleaning Engine incorporating legacy batch optimizations
        and Windows Disk Clean-up targets across 14 comprehensive categories.
        Strictly excludes the Windows Recycle Bin and user Downloads directory.
        """
        if log_callback:
            log_callback("🧹 Starting 14-Target Deep Clean Engine...", "#a855f7")

        if whitelist_dirs is None:
            whitelist_dirs = SettingsManager.get_instance().get("whitelisted_dirs", [])

        # Normalize whitelisted directories
        whitelist_norm = [os.path.normcase(os.path.abspath(d)) for d in whitelist_dirs if d and os.path.exists(d)]

        # Environment paths
        windir = os.environ.get("WINDIR", r"C:\Windows")
        user_profile = os.environ.get("USERPROFILE", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")
        programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")

        # Explicit forbidden locations: NEVER touch Downloads or Recycle Bin under any circumstances
        downloads_norm = os.path.normcase(os.path.abspath(os.path.join(user_profile, "Downloads"))) if user_profile else ""

        def is_forbidden(target_path: str) -> bool:
            """Validates that a path is safe to clean and strictly not protected/whitelisted."""
            if not target_path:
                return True
            try:
                norm = os.path.normcase(os.path.abspath(target_path))
                # 1. Strict Downloads protection
                if downloads_norm and (norm == downloads_norm or norm.startswith(downloads_norm + os.sep)):
                    return True
                # 2. Strict Recycle Bin exclusion
                if "$recycle.bin" in norm or "recycler" in norm:
                    return True
                # 3. User whitelist exclusions
                for w in whitelist_norm:
                    if norm == w or norm.startswith(w + os.sep):
                        return True
            except Exception:
                return True
            return False

        total_freed = 0
        files_removed = 0
        dirs_skipped = 0
        skipped_locked = 0

        def delete_file_safe(file_path: str):
            """Safely deletes an individual file or symlink with per-file error trapping."""
            nonlocal total_freed, files_removed, skipped_locked
            if is_forbidden(file_path):
                return
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    sz = os.path.getsize(file_path)
                    os.remove(file_path)
                    total_freed += sz
                    files_removed += 1
            except (PermissionError, OSError):
                skipped_locked += 1
            except Exception:
                pass

        def clean_directory_contents(dir_path: str, extensions=None, max_depth=3):
            """Walks a directory and safely purges files without removing forbidden roots."""
            nonlocal dirs_skipped
            if not dir_path or not os.path.exists(dir_path) or is_forbidden(dir_path):
                dirs_skipped += 1
                return
            try:
                base_depth = dir_path.rstrip(os.sep).count(os.sep)
                for root, dirs, files in os.walk(dir_path, topdown=False):
                    cur_depth = root.rstrip(os.sep).count(os.sep) - base_depth
                    if cur_depth > max_depth:
                        continue
                    if is_forbidden(root):
                        continue
                    for f in files:
                        if extensions:
                            if not any(f.lower().endswith(ext) for ext in extensions):
                                continue
                        delete_file_safe(os.path.join(root, f))
                    # Safely remove empty non-root subdirectories if no extension filtering
                    if not extensions:
                        for d in dirs:
                            dp = os.path.join(root, d)
                            if not is_forbidden(dp):
                                try:
                                    if not os.listdir(dp):
                                        os.rmdir(dp)
                                except Exception:
                                    pass
            except Exception:
                dirs_skipped += 1

        # ── 1. BASE TEMP FOLDERS ──────────────────────────────────────────
        if log_callback:
            log_callback("Scanning Base Temp folders (%TEMP%, Windows\\Temp)...", "#38bdf8")
        freed_before = total_freed
        base_temp_folders = [
            os.environ.get("TEMP", ""),
            os.environ.get("TMP", ""),
            os.path.join(windir, "Temp"),
            os.path.join(user_profile, "Local Settings", "Temp") if user_profile else "",
            os.path.join(localappdata, "Temp") if localappdata else "",
        ]
        for tf in set(filter(None, base_temp_folders)):
            clean_directory_contents(tf)
        if log_callback and (total_freed - freed_before) > 0:
            log_callback(f"Cleared {(total_freed - freed_before)/(1024*1024):.1f}MB from %TEMP%", "#22c55e")

        # ── 2. WINDOWS UPDATE CACHE ───────────────────────────────────────
        if log_callback:
            log_callback("Checking Windows Update Cache (SoftwareDistribution)...", "#38bdf8")
        freed_before = total_freed
        update_services = ["wuauserv", "UsoSvc", "bits", "dosvc"]
        stopped_services = []
        if is_admin():
            for svc in update_services:
                try:
                    res = subprocess.run(
                        ["net", "stop", svc, "/y"],
                        capture_output=True, text=True,
                        creationflags=0x08000000, timeout=8
                    )
                    if res.returncode == 0:
                        stopped_services.append(svc)
                except Exception:
                    pass

        try:
            sw_dist = os.path.join(windir, "SoftwareDistribution")
            sw_targets = [
                os.path.join(sw_dist, "Download"),
                os.path.join(sw_dist, "DataStore", "Logs"),
                os.path.join(sw_dist, "PostRebootEventCache"),
                os.path.join(sw_dist, "ScanFile"),
            ]
            for st in sw_targets:
                clean_directory_contents(st)
        finally:
            if is_admin() and stopped_services:
                for svc in reversed(stopped_services):
                    try:
                        subprocess.run(
                            ["net", "start", svc],
                            capture_output=True, text=True,
                            creationflags=0x08000000, timeout=8
                        )
                    except Exception:
                        pass
        if log_callback and (total_freed - freed_before) > 0:
            log_callback(f"Cleared {(total_freed - freed_before)/(1024*1024):.1f}MB from Windows Update cache", "#22c55e")

        # ── 3. WINDOWS PREFETCH ───────────────────────────────────────────
        if log_callback:
            log_callback("Scanning Windows Prefetch...", "#38bdf8")
        freed_before = total_freed
        clean_directory_contents(os.path.join(windir, "Prefetch"))
        if log_callback and (total_freed - freed_before) > 0:
            log_callback(f"Cleared {(total_freed - freed_before)/(1024*1024):.1f}MB from Prefetch", "#22c55e")

        # ── 4. SYSTEM-WIDE JUNK EXTENSIONS (.log, .tmp, .bak, .chk, .old) ──
        if log_callback:
            log_callback("Scanning residual junk files (.tmp, .log, .dmp)...", "#38bdf8")
        freed_before = total_freed
        junk_exts = (".log", ".tmp", ".bak", ".chk", ".old", ".dmp")
        ext_target_dirs = [
            os.path.join(localappdata, "CrashDumps") if localappdata else "",
            os.path.join(programdata, "Microsoft", "Windows", "WER"),
            os.path.join(localappdata, "Microsoft", "Windows", "WER") if localappdata else "",
            os.path.join(windir, "Logs"),
            os.path.join(windir, "System32", "LogFiles"),
        ]
        for ed in set(filter(None, ext_target_dirs)):
            clean_directory_contents(ed, extensions=junk_exts, max_depth=3)
        if log_callback and (total_freed - freed_before) > 0:
            log_callback(f"Purged {(total_freed - freed_before)/(1024*1024):.1f}MB residual logs & dumps", "#22c55e")

        # ── 5. WINDOWS EVENT LOGS (wevtutil cl) ────────────────────────────
        if is_admin():
            if log_callback:
                log_callback("Truncating Windows Event Logs via wevtutil...", "#38bdf8")
            try:
                proc = subprocess.run(
                    ["wevtutil.exe", "el"],
                    capture_output=True, text=True,
                    creationflags=0x08000000, timeout=12
                )
                if proc.returncode == 0 and proc.stdout:
                    for log_name in proc.stdout.splitlines():
                        log_name = log_name.strip()
                        if log_name:
                            try:
                                subprocess.run(
                                    ["wevtutil.exe", "cl", log_name],
                                    capture_output=True, text=True,
                                    creationflags=0x08000000, timeout=2
                                )
                            except Exception:
                                pass
                if log_callback:
                    log_callback("Windows Event Logs cleared", "#22c55e")
            except Exception:
                pass

        # ── 6. MICROSOFT DEFENDER ANTIVIRUS TEMP FILES ────────────────────
        if log_callback:
            log_callback("Scanning Defender antivirus cache & logs...", "#38bdf8")
        defender_targets = [
            os.path.join(programdata, "Microsoft", "Windows Defender", "Support"),
            os.path.join(programdata, "Microsoft", "Windows Defender", "Scans", "History", "Results", "Quick"),
            os.path.join(programdata, "Microsoft", "Windows Defender", "Scans", "History", "Results", "Resource"),
            os.path.join(windir, "Temp", "MpCmdRun.log"),
        ]
        for dt in defender_targets:
            if os.path.isfile(dt):
                delete_file_safe(dt)
            else:
                clean_directory_contents(dt)

        # ── 7. DOWNLOADED PROGRAM FILES ───────────────────────────────────
        clean_directory_contents(os.path.join(windir, "Downloaded Program Files"))

        # ── 8. TEMPORARY INTERNET FILES / BROWSER CACHES (Optional — user controlled) ──
        if SettingsManager.get_instance().get("clean_browser_cache", False):
            if log_callback:
                log_callback("Cleaning Web Browser caches (Chrome, Edge, Firefox)...", "#38bdf8")
            freed_before = total_freed
            browser_cache_dirs = [
                os.path.join(localappdata, "Microsoft", "Windows", "INetCache") if localappdata else "",
                os.path.join(localappdata, "Microsoft", "Windows", "WebCache") if localappdata else "",
                # Google Chrome
                os.path.join(localappdata, "Google", "Chrome", "User Data", "Default", "Cache") if localappdata else "",
                os.path.join(localappdata, "Google", "Chrome", "User Data", "Default", "Code Cache") if localappdata else "",
                os.path.join(localappdata, "Google", "Chrome", "User Data", "Default", "GPUCache") if localappdata else "",
                # Microsoft Edge
                os.path.join(localappdata, "Microsoft", "Edge", "User Data", "Default", "Cache") if localappdata else "",
                os.path.join(localappdata, "Microsoft", "Edge", "User Data", "Default", "Code Cache") if localappdata else "",
                os.path.join(localappdata, "Microsoft", "Edge", "User Data", "Default", "GPUCache") if localappdata else "",
                # Brave
                os.path.join(localappdata, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Cache") if localappdata else "",
                # Opera
                os.path.join(localappdata, "Opera Software", "Opera Stable", "Cache") if localappdata else "",
                os.path.join(appdata, "Opera Software", "Opera Stable", "Cache") if appdata else "",
            ]
            # Mozilla Firefox Profile Caches
            if localappdata:
                ff_profiles = os.path.join(localappdata, "Mozilla", "Firefox", "Profiles")
                if os.path.exists(ff_profiles) and not is_forbidden(ff_profiles):
                    try:
                        for prof in os.listdir(ff_profiles):
                            prof_cache = os.path.join(ff_profiles, prof, "cache2")
                            browser_cache_dirs.append(prof_cache)
                    except Exception:
                        pass

            for bcd in set(filter(None, browser_cache_dirs)):
                clean_directory_contents(bcd)
            if log_callback and (total_freed - freed_before) > 0:
                log_callback(f"Cleared {(total_freed - freed_before)/(1024*1024):.1f}MB browser caches", "#22c55e")
        else:
            if log_callback:
                log_callback("Browser Cache skipped (disabled in Settings)", "#94a3b8")

        # ── 8b. MEDIA EDITORS CACHE & TEMP (Optional — strictly user controlled) ──
        if SettingsManager.get_instance().get("clean_media_cache", False):
            if log_callback:
                log_callback("Scanning Media Editor Caches (Adobe, DaVinci, CapCut, Filmora)...", "#38bdf8")
            freed_before = total_freed

            media_cache_dirs = [
                # Adobe Suite Media Caches
                os.path.join(appdata, "Adobe", "Common", "Media Cache") if appdata else "",
                os.path.join(appdata, "Adobe", "Common", "Media Cache Files") if appdata else "",
                os.path.join(localappdata, "Adobe", "After Effects") if localappdata else "",
                # DaVinci Resolve
                os.path.join(localappdata, "Blackmagic Design", "DaVinci Resolve", "Support", "workspace", "CacheClip") if localappdata else "",
                os.path.join(localappdata, "Blackmagic Design", "DaVinci Resolve", "Support", "workspace", "ProxyMedia") if localappdata else "",
                # CapCut
                os.path.join(localappdata, "CapCut", "User Data", "Cache") if localappdata else "",
                # Wondershare Filmora
                os.path.join(localappdata, "Wondershare", "Wondershare Filmora", "Temp") if localappdata else "",
                os.path.join(localappdata, "Wondershare", "Wondershare Filmora", "Proxy") if localappdata else "",
                os.path.join(localappdata, "Wondershare", "Wondershare Filmora", "Render") if localappdata else "",
            ]

            for mcd in set(filter(None, media_cache_dirs)):
                clean_directory_contents(mcd, max_depth=6)

            # Adobe Photoshop Temp & Illustrator AIL Temp files in %TEMP%
            temp_env = os.environ.get("TEMP", "")
            if temp_env and os.path.exists(temp_env) and not is_forbidden(temp_env):
                try:
                    for item in os.listdir(temp_env):
                        item_lower = item.lower()
                        if item_lower.startswith("photoshop temp") or (item_lower.startswith("ail") and item_lower.endswith(".tmp")):
                            delete_file_safe(os.path.join(temp_env, item))
                except Exception:
                    pass

            if log_callback and (total_freed - freed_before) > 0:
                log_callback(f"Cleared {(total_freed - freed_before)/(1024*1024):.1f}MB media editor caches", "#22c55e")
            elif log_callback:
                log_callback("Media Editor caches scanned (clean / no files removed)", "#94a3b8")
        else:
            if log_callback:
                log_callback("Media Editor Cache skipped (disabled in Settings)", "#94a3b8")

        # ── 9. DIRECTX & GPU SHADER CACHES ──────────────────────────────
        if log_callback:
            log_callback("Purging DirectX and GPU shader caches...", "#38bdf8")
        freed_before = total_freed
        shader_dirs = [
            os.path.join(localappdata, "D3DSCache") if localappdata else "",
            os.path.join(localappdata, "NVIDIA", "DXCache") if localappdata else "",
            os.path.join(localappdata, "NVIDIA", "GLCache") if localappdata else "",
            os.path.join(localappdata, "AMD", "DxCache") if localappdata else "",
            os.path.join(localappdata, "AMD", "GLCache") if localappdata else "",
            os.path.join(localappdata, "Intel", "ShaderCache") if localappdata else "",
        ]
        for sd in set(filter(None, shader_dirs)):
            clean_directory_contents(sd)
        if log_callback and (total_freed - freed_before) > 0:
            log_callback(f"Cleared {(total_freed - freed_before)/(1024*1024):.1f}MB GPU shader caches", "#22c55e")

        # ── 10. DELIVERY OPTIMIZATION FILES ───────────────────────────────
        if log_callback:
            log_callback("Clearing Delivery Optimization cache...", "#38bdf8")
        delivery_dirs = [
            os.path.join(windir, "SoftwareDistribution", "DeliveryOptimization"),
            os.path.join(programdata, "Microsoft", "Network", "Downloader"),
            os.path.join(windir, "ServiceProfiles", "NetworkService", "AppData", "Local", "Microsoft", "Windows", "DeliveryOptimization", "Cache"),
            os.path.join(windir, "ServiceProfiles", "NetworkService", "AppData", "Local", "Microsoft", "Windows", "DeliveryOptimization", "Logs"),
        ]
        for dd in set(filter(None, delivery_dirs)):
            clean_directory_contents(dd)

        # ── 11. OLD DEVICE DRIVER PACKAGES / LOGS ─────────────────────────
        if log_callback:
            log_callback("Scanning old device driver logs...", "#38bdf8")
        driver_targets = [
            os.path.join(windir, "System32", "DriverStore", "Temp"),
            os.path.join(windir, "Driver Cache"),
            os.path.join(windir, "INF", "setupapi.offline.log"),
        ]
        for dt in driver_targets:
            if os.path.isfile(dt):
                delete_file_safe(dt)
            else:
                clean_directory_contents(dt)

        # ── 12. LANGUAGE RESOURCE FILES & FONT CACHES ─────────────────────
        if log_callback:
            log_callback("Cleaning temporary font caches...", "#38bdf8")
        lang_font_dirs = [
            os.path.join(localappdata, "FontCache") if localappdata else "",
            os.path.join(windir, "ServiceProfiles", "LocalService", "AppData", "Local", "FontCache"),
        ]
        for lfd in set(filter(None, lang_font_dirs)):
            clean_directory_contents(lfd)

        # ── 13. TEMPORARY WINDOWS INSTALLATION FILES ──────────────────────
        if log_callback:
            log_callback("Scanning residual Windows installation files...", "#38bdf8")
        install_targets = [
            r"C:\$WINDOWS.~BT",
            r"C:\$Windows.~WS",
            os.path.join(windir, "Panther"),
            os.path.join(windir, "Logs", "Setup"),
            os.path.join(windir, "Minidump"),
            os.path.join(windir, "memory.dmp"),
            os.path.join(windir, "setupact.log"),
            os.path.join(windir, "setuperr.log"),
        ]
        for it in install_targets:
            if os.path.isfile(it):
                delete_file_safe(it)
            else:
                clean_directory_contents(it)

        # ── 14. THUMBNAIL CACHE (thumbcache_*.db, iconcache_*.db) ────────
        if log_callback:
            log_callback("Flushing explorer thumbnail cache...", "#38bdf8")
        freed_before = total_freed
        if localappdata:
            explorer_cache = os.path.join(localappdata, "Microsoft", "Windows", "Explorer")
            if os.path.exists(explorer_cache) and not is_forbidden(explorer_cache):
                try:
                    for f in os.listdir(explorer_cache):
                        f_lower = f.lower()
                        if f_lower.startswith("thumbcache_") or f_lower.startswith("iconcache_"):
                            delete_file_safe(os.path.join(explorer_cache, f))
                except Exception:
                    pass
        if log_callback and (total_freed - freed_before) > 0:
            log_callback(f"Cleared {(total_freed - freed_before)/(1024*1024):.1f}MB thumbnail databases", "#22c55e")

        freed_mb = total_freed / (1024 * 1024)
        if log_callback and skipped_locked > 0:
            log_callback(f"Skipped {skipped_locked} locked system files (in use by Windows)", "#facc15")
        if log_callback:
            log_callback(f"✓ Deep Clean Complete: {freed_mb:.1f} MB freed across {files_removed} files", "#22c55e")

        ActivityLogger.log_event("JUNK_CLEAN", freed_mb, files_removed, dirs_skipped, "Comprehensive 14-target Deep Clean")
        return freed_mb, files_removed

    @staticmethod
    def purge_standby_memory():
        """Attempts to purge Windows Standby Memory using undocumented NtSetSystemInformation."""
        try:
            ntdll = ctypes.WinDLL("ntdll")
            command = ctypes.c_int(4) # MemoryPurgeStandbyList
            # Only works if process has SeProfileSingleProcessPrivilege, which admins usually can get,
            # or it might just work when elevated.
            res = ntdll.NtSetSystemInformation(80, ctypes.byref(command), ctypes.sizeof(command))
            success = (res == 0)
            ActivityLogger.log_event("STANDBY_MEMORY_PURGE", 0, 1 if success else 0, 0, "Attempted Standby list purge")
            return success
        except Exception:
            return False


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

class GameWatcherWorker(QThread):
    game_started = Signal(str)
    game_stopped = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_game = None
        
    def run(self):
        settings = SettingsManager.get_instance()
        while True:
            if settings.get("game_mode_enabled", False):
                watch_list = []
                wl_path = os.path.join(APP_DIR, "watch_list.json")
                if os.path.exists(wl_path):
                    try:
                        with open(wl_path, "r", encoding="utf-8") as f:
                            watch_list = json.load(f)
                    except:
                        pass
                wl_lower = {g.lower() for g in watch_list if g}
                
                found_game = None
                if wl_lower:
                    for proc in psutil.process_iter(["name"]):
                        name = (proc.info.get("name") or "").lower()
                        if name in wl_lower:
                            found_game = name
                            break
                        
                if found_game and not self._active_game:
                    self._active_game = found_game
                    self.game_started.emit(found_game)
                elif not found_game and self._active_game:
                    self._active_game = None
                    self.game_stopped.emit()
            time.sleep(5.0)

class RamWorker(QThread):
    finished = Signal(float, int, int, int)  # saved_mb, success, fail, skipped
    log_message = Signal(str, str)            # text, color

    def __init__(self, is_auto=False, parent=None):
        super().__init__(parent)
        self.is_auto = is_auto

    def run(self):
        def log_cb(text, color="#38bdf8"):
            self.log_message.emit(text, color)

        self.finished.emit(*OptimizationEngine.purge_ram(is_auto=self.is_auto, log_callback=log_cb))


class JunkWorker(QThread):
    finished = Signal(float, int)    # freed_mb, files
    log_message = Signal(str, str)   # text, color

    def run(self):
        def log_cb(text, color="#38bdf8"):
            self.log_message.emit(text, color)

        j_freed, j_files = OptimizationEngine.clean_junk(log_callback=log_cb)
        self.finished.emit(j_freed, j_files)


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
setlocal
:: Unset PyInstaller parent environment variables
set _PYI_ONEFILE_PARENT=
set _MEIPASS2=
set PYTHONHOME=
set PYTHONPATH=

:: Wait until old process fully exits and file lock is released
:RETRY_LOOP
timeout /t 1 /nobreak >nul
del /f /q "{current_exe}" >nul 2>&1
if exist "{current_exe}" goto RETRY_LOOP

move /y "{new_exe}" "{current_exe}" >nul

:: Launch via Windows Explorer shell to ensure a clean, top-level process with zero PID inheritance
explorer.exe "{current_exe}"

endlocal
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
    """Clean, theme-adaptive card with a compact ProgressRing and strict single-line constraints."""

    def __init__(self, title: str, ring_color: str, parent=None):
        super().__init__(parent)
        self._ring_color = ring_color
        self.setFixedHeight(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(4)

        # Header Title (Strict Single-Line)
        self.title_lbl = CaptionLabel(title, self)
        self.title_lbl.setWordWrap(False)
        self.title_lbl.setFixedHeight(16)
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
        self.pct_lbl.setWordWrap(False)
        self.pct_lbl.setFixedHeight(22)
        self.pct_lbl.setStyleSheet(
            f"font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;"
            f"font-size: 18px; font-weight: 600; color: {ring_color};"
        )
        self.pct_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        info.addWidget(self.pct_lbl)

        self.sub_lbl = CaptionLabel("", self)
        self.sub_lbl.setWordWrap(False)
        self.sub_lbl.setFixedHeight(16)
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
        self.setFixedSize(400, 715)
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
        self.spin_ram.setFixedWidth(135)
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

        # 2. Run on Startup
        row2 = QHBoxLayout()
        lbl2 = CaptionLabel("Run on Startup")
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
        
        # 3b. Game Mode
        row_gm = QHBoxLayout()
        lbl_gm = CaptionLabel("Game Mode (Auto Power Plan & Priority)")
        self.switch_gm = SwitchButton()
        row_gm.addWidget(lbl_gm)
        row_gm.addStretch()
        row_gm.addWidget(self.switch_gm)
        root.addLayout(row_gm)

        # 3c. Clean Browser Cache (Default OFF)
        row_browser = QHBoxLayout()
        lbl_browser = CaptionLabel("Clean Browser Cache")
        self.switch_browser = SwitchButton()
        row_browser.addWidget(lbl_browser)
        row_browser.addStretch()
        row_browser.addWidget(self.switch_browser)
        root.addLayout(row_browser)

        # 3c2. Clean Media Editors Cache (Default OFF)
        row_media = QHBoxLayout()
        lbl_media = CaptionLabel("Clean Media Editors Cache")
        self.switch_media = SwitchButton()
        row_media.addWidget(lbl_media)
        row_media.addStretch()
        row_media.addWidget(self.switch_media)
        root.addLayout(row_media)

        # 3d. Show/Hide Logs (Default ON)
        row_logs = QHBoxLayout()
        lbl_logs = CaptionLabel("Show/Hide Logs")
        self.switch_logs = SwitchButton()
        row_logs.addWidget(lbl_logs)
        row_logs.addStretch()
        row_logs.addWidget(self.switch_logs)
        root.addLayout(row_logs)

        # 4. Process Whitelist & Watchlist
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
        
        lbl_watch = CaptionLabel("Game Watch List (comma-separated):")
        root.addWidget(lbl_watch)
        self.txt_watchlist = QLineEdit()
        self.txt_watchlist.setPlaceholderText("cyberpunk.exe, csgo.exe")
        self.txt_watchlist.setStyleSheet(
            "QLineEdit { border: 1px solid #3d3d3d; border-radius: 5px; padding: 4px; background: #252525; color: #fff; }"
            if dark else
            "QLineEdit { border: 1px solid #ccc; border-radius: 5px; padding: 4px; background: #fff; color: #000; }"
        )
        root.addWidget(self.txt_watchlist)

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

        # 6. Support the Developer Section (Monetization & Donations)
        sep_support = QFrame()
        sep_support.setFrameShape(QFrame.HLine)
        sep_support.setStyleSheet("color: #383838;" if dark else "color: #e0e0e0;")
        root.addWidget(sep_support)

        lbl_support = CaptionLabel("Buy Me a Coffee ☕")
        root.addWidget(lbl_support)

        support_row = QHBoxLayout()
        support_row.setContentsMargins(0, 0, 0, 0)
        support_row.setSpacing(8)

        self.btn_support_crypto = PrimaryPushButton("🪙 Tip via Crypto (Binance Pay / USDT)")
        self.btn_support_crypto.setFixedHeight(32)
        self.btn_support_crypto.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_support_crypto.setToolTip("View Binance Pay ID and USDT BEP20 deposit address (Zero Fees)")
        self.btn_support_crypto.clicked.connect(self._on_support_crypto)

        support_row.addWidget(self.btn_support_crypto)
        root.addLayout(support_row)

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
        self.switch_gm.setChecked(self.settings.get("game_mode_enabled", False))
        self.switch_browser.setChecked(self.settings.get("clean_browser_cache", False))
        self.switch_media.setChecked(self.settings.get("clean_media_cache", False))
        self.switch_logs.setChecked(self.settings.get("show_logs", True))
        procs = self.settings.get("whitelisted_processes", [])
        self.txt_whitelist.setText(", ".join(procs))
        
        watch_list = []
        wl_path = os.path.join(APP_DIR, "watch_list.json")
        if os.path.exists(wl_path):
            try:
                with open(wl_path, "r", encoding="utf-8") as f:
                    watch_list = json.load(f)
            except: pass
        self.txt_watchlist.setText(", ".join(watch_list))

    def _save_values(self):
        self.settings.set("auto_optimize_ram", self.switch_auto_ram.isChecked())
        self.settings.set("ram_threshold_percent", self.spin_ram.value())
        self.settings.set("notifications_enabled", self.switch_notif.isChecked())
        self.settings.set("game_mode_enabled", self.switch_gm.isChecked())
        self.settings.set("clean_browser_cache", self.switch_browser.isChecked())
        self.settings.set("clean_media_cache", self.switch_media.isChecked())
        self.settings.set("show_logs", self.switch_logs.isChecked())

        # Update Startup
        target_startup = self.switch_startup.isChecked()
        TaskSchedulerManager.set_autostart(target_startup)
        self.settings.set("autostart_enabled", target_startup)

        # Update Whitelist
        raw = self.txt_whitelist.text()
        procs = [p.strip() for p in raw.split(",") if p.strip()]
        self.settings.set("whitelisted_processes", procs)
        
        # Update Watchlist
        wl_raw = self.txt_watchlist.text()
        wl = [p.strip() for p in wl_raw.split(",") if p.strip()]
        try:
            with open(os.path.join(APP_DIR, "watch_list.json"), "w", encoding="utf-8") as f:
                json.dump(wl, f)
        except: pass

        self.accept()

    def _on_support_crypto(self):
        crypto_text = (
            "Thank you for supporting NanoOpt independent development!\n\n"
            "• Binance Pay ID:\n368917674\n\n"
            "• USDT (BEP20) Address:\n0x3e8084a465c50b39e22815fee1b7e78b4edcd84f\n\n"
            "(Select text above to copy)"
        )
        msg = MessageBox("🪙 Tip via Crypto (Zero Fees)", crypto_text, self)
        msg.setContentCopyable(True)
        msg.yesButton.setText("Close")
        msg.hideCancelButton()
        msg.exec()

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

        # Responsive window sizing specifications
        self.NORMAL_SIZE   = (390, 315)
        self.EXPANDED_SIZE = (390, 365)
        self.setFixedSize(*self.NORMAL_SIZE)
        self.setWindowTitle("NanoOpt")
        self.setWindowIcon(get_rocket_icon())

        # Load Settings & Activity Logger
        self.settings = SettingsManager.get_instance()
        ActivityLogger.setup()

        # System Theme Listener
        self.theme_listener = SystemThemeListener(self)
        self.theme_listener.systemThemeChanged.connect(self._on_theme_changed)

        self._is_updating = False
        self._build_ui()
        self._update_window_size()
        self._apply_theme_styles()
        self._setup_tray()

        # Background Metrics & Auto-Optimization Poller
        self._metrics_worker = MetricsWorker(self)
        self._metrics_worker.updated.connect(self._on_metrics)
        self._metrics_worker.auto_ram_triggered.connect(self._on_auto_ram)
        self._metrics_worker.start()
        
        # Game Watcher
        self._game_worker = GameWatcherWorker(self)
        self._game_worker.game_started.connect(self._on_game_started)
        self._game_worker.game_stopped.connect(self._on_game_stopped)
        self._game_worker.start()

        # Status Auto-Reset
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._reset_status)

        # OTA Update Checker (delayed 3s after startup)
        self._update_checker = None
        self._update_downloader = None
        self._pending_update_version = None
        QTimer.singleShot(3000, self._check_for_updates)

    def _update_window_size(self):
        """Dynamically adapts window height based on log terminal visibility and OTA update bar."""
        show_logs = self.settings.get("show_logs", True)
        if hasattr(self, "_terminal"):
            self._terminal.setVisible(show_logs)
        base_h = 440 if show_logs else 315
        target_h = base_h + 50 if getattr(self, "_is_updating", False) else base_h
        self.setFixedSize(390, target_h)
        self.update()

    def _set_expanded(self, expanded: bool):
        """Smoothly adapts the window height for dynamic update UI without squeezing any existing widgets."""
        self._is_updating = expanded
        if hasattr(self, "_update_container"):
            self._update_container.setVisible(expanded)
        self._update_window_size()

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

        if hasattr(self, "_terminal"):
            self._terminal.setStyleSheet(
                "QTextEdit { background-color: rgba(18, 18, 18, 0.85); color: #d1d5db; "
                "border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 6px; "
                "font-family: 'Consolas', 'Courier New', monospace; font-size: 10pt; }"
                if dark else
                "QTextEdit { background-color: rgba(245, 245, 245, 0.95); color: #1e293b; "
                "border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 6px; padding: 6px; "
                "font-family: 'Consolas', 'Courier New', monospace; font-size: 10pt; }"
            )

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
        self._app_lbl.setWordWrap(False)
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

        # Status Badge (Strict Single-Line)
        self._status_lbl = QLabel("✓  Running as Administrator")
        self._status_lbl.setWordWrap(False)
        self._status_lbl.setFixedHeight(16)
        self._status_lbl.setContentsMargins(8, 0, 0, 0)
        root.addWidget(self._status_lbl)

        # Metric Cards Row
        cards_row = QWidget()
        cards_lay = QHBoxLayout(cards_row)
        cards_lay.setContentsMargins(0, 0, 0, 0)
        cards_lay.setSpacing(10)

        self._cpu_card = MetricCard("CPU Usage", "#f43f5e")
        self._ram_card = MetricCard("RAM Usage", "#0ea5e9")
        cards_lay.addWidget(self._cpu_card)
        cards_lay.addWidget(self._ram_card)
        root.addWidget(cards_row)

        # Action Buttons
        btn_row = QWidget()
        btn_lay = QHBoxLayout(btn_row)
        btn_lay.setContentsMargins(0, 0, 0, 0)
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

        # Dedicated Dynamic Update Container (Non-Destructive)
        self._update_container = QWidget(self)
        self._update_container.setFixedHeight(44)
        u_lay = QVBoxLayout(self._update_container)
        u_lay.setContentsMargins(0, 0, 0, 0)
        u_lay.setSpacing(4)

        self._download_info_lbl = CaptionLabel("⬇ Downloading update…", self._update_container)
        self._download_info_lbl.setWordWrap(False)
        self._download_info_lbl.setAlignment(Qt.AlignCenter)
        self._download_info_lbl.setFixedHeight(16)
        self._download_info_lbl.setStyleSheet("color: #0ea5e9; font-weight: 600;")
        u_lay.addWidget(self._download_info_lbl)

        self._download_bar = QProgressBar(self._update_container)
        self._download_bar.setRange(0, 100)
        self._download_bar.setValue(0)
        self._download_bar.setFixedHeight(20)
        self._download_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #3d3d3d; border-radius: 4px; background: #252525; text-align: center; color: #fff; font-size: 10px; font-weight: 600; }"
            "QProgressBar::chunk { background: #0ea5e9; border-radius: 3px; }"
            if isDarkTheme() else
            "QProgressBar { border: 1px solid #ccc; border-radius: 4px; background: #f0f0f0; text-align: center; color: #000; font-size: 10px; font-weight: 600; }"
            "QProgressBar::chunk { background: #0078d4; border-radius: 3px; }"
        )
        u_lay.addWidget(self._download_bar)
        self._update_container.setVisible(False)
        root.addWidget(self._update_container)

        # Log Status Banner (Strict Single-Line)
        self._log_lbl = CaptionLabel("")
        self._log_lbl.setWordWrap(False)
        self._log_lbl.setAlignment(Qt.AlignCenter)
        self._log_lbl.setFixedHeight(18)
        root.addWidget(self._log_lbl)

        # Live Activity Log Terminal
        self._terminal = TextEdit(self)
        self._terminal.setReadOnly(True)
        self._terminal.setFixedHeight(115)
        self._terminal.setFont(QFont("Consolas", 10))
        self._terminal.setStyleSheet(
            "QTextEdit { background-color: rgba(18, 18, 18, 0.85); color: #d1d5db; "
            "border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 6px; padding: 6px; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 10pt; }"
            if isDarkTheme() else
            "QTextEdit { background-color: rgba(245, 245, 245, 0.95); color: #1e293b; "
            "border: 1px solid rgba(0, 0, 0, 0.12); border-radius: 6px; padding: 6px; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 10pt; }"
        )
        self._terminal.setHtml(
            "<span style='color: #64748b;'>[System]</span> <span style='color: #38bdf8;'>NanoOpt v1.3.0 Live Terminal ready.</span>"
        )
        root.addWidget(self._terminal)

        # Footer (Strict Single-Line)
        self._footer_lbl = QLabel()
        self._footer_lbl.setWordWrap(False)
        self._footer_lbl.setTextFormat(Qt.RichText)
        self._footer_lbl.setOpenExternalLinks(True)
        self._footer_lbl.setAlignment(Qt.AlignCenter)
        self._footer_lbl.setFixedHeight(18)
        root.addWidget(self._footer_lbl)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._update_window_size()

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

    def _on_game_started(self, game_name: str):
        self._log(f"🎮 Game Mode ON: {game_name}", "#10b981")
        self._status_lbl.setText(f"🎮  Game Mode Active — {game_name}")
        self._append_terminal_log(f"🎮 Game Mode Activated: {game_name}", "#10b981")
        OptimizationEngine.purge_standby_memory()
        self._trigger_ram(is_auto=True)
        try: subprocess.run(["powercfg", "-setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"], creationflags=subprocess.CREATE_NO_WINDOW)
        except: pass
        targets = ["chrome.exe", "msedge.exe", "discord.exe", "onedrive.exe"]
        for p in psutil.process_iter(["name"]):
            name = (p.info.get("name") or "").lower()
            if name in targets:
                try: p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                except: pass
                
    def _on_game_stopped(self):
        self._log("🎮 Game Mode OFF", "#10b981")
        self._status_lbl.setText("✓  Running as Administrator")
        self._append_terminal_log("🎮 Game Mode Deactivated: Restored normal power plan", "#94a3b8")
        try: subprocess.run(["powercfg", "-setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"], creationflags=subprocess.CREATE_NO_WINDOW)
        except: pass
        targets = ["chrome.exe", "msedge.exe", "discord.exe", "onedrive.exe"]
        for p in psutil.process_iter(["name"]):
            name = (p.info.get("name") or "").lower()
            if name in targets:
                try: p.nice(psutil.NORMAL_PRIORITY_CLASS)
                except: pass

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
        w.log_message.connect(self._append_terminal_log)
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
        w.log_message.connect(self._append_terminal_log)
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
    def _append_terminal_log(self, text: str, color: str = "#d1d5db"):
        """Thread-safe terminal log appender with timestamp, color coding, auto-scroll, and 150-line limit."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        html_line = f"<span style='color: #64748b;'>[{timestamp}]</span> <span style='color: {color}; font-weight: 500;'>{text}</span>"
        self._terminal.append(html_line)

        # Limit to latest 150 lines
        doc = self._terminal.document()
        if doc.blockCount() > 150:
            cursor = self._terminal.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            for _ in range(doc.blockCount() - 150):
                cursor.select(cursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()

        # Auto-scroll to absolute bottom
        sb = self._terminal.verticalScrollBar()
        sb.setValue(sb.maximum())

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
        """Shows a MessageBox prompting the user to update with adaptive text sizing."""
        self._pending_update_version = new_version
        self._restore()  # Bring window to front

        raw_msg = (
            f"A new version of NanoOpt (v{new_version}) is available.\n"
            f"You are currently running v{APP_VERSION}.\n\n"
            f"Would you like to update now?"
        )

        dlg = MessageBox(f"Update Available - v{new_version}", raw_msg, self)
        
        # Adaptive dialog geometry to prevent awkward mid-sentence line breaks
        try:
            dlg.contentLabel.setText(raw_msg)
            dlg.contentLabel.setWordWrap(True)
            dlg.titleLabel.adjustSize()
            dlg.contentLabel.adjustSize()

            w_hint = max(dlg.titleLabel.sizeHint().width(), dlg.contentLabel.sizeHint().width()) + 52
            modal_w = min(max(w_hint, 310), self.width() - 30)
            dlg.contentLabel.setFixedWidth(modal_w - 48)
            dlg.contentLabel.adjustSize()
            modal_h = dlg.titleLabel.sizeHint().height() + dlg.contentLabel.sizeHint().height() + 115
            dlg.widget.setFixedSize(modal_w, modal_h)
        except Exception:
            pass

        dlg.yesButton.setText("Update Now")
        dlg.cancelButton.setText("Later")

        if dlg.exec():
            self._start_download(download_url)
        else:
            logging.info("OTA: User declined update.")

    def _start_download(self, url: str):
        """Starts the download, smoothly expands the window height, and displays progress."""
        self._download_bar.setValue(0)
        self._download_bar.setFormat(f"Downloading v{self._pending_update_version}… %p%")
        self._download_info_lbl.setText(f"⬇ Downloading NanoOpt v{self._pending_update_version}…")
        
        # Smooth non-destructive layout transition
        self._update_container.setVisible(True)
        self._log_lbl.setVisible(False)
        self._set_expanded(True)
        self._set_busy(True)

        self._update_downloader = UpdateDownloader(url, self)
        self._update_downloader.progress.connect(self._on_download_progress)
        self._update_downloader.download_complete.connect(self._on_download_complete)
        self._update_downloader.download_failed.connect(self._on_download_failed)
        self._update_downloader.start()

    def _on_download_progress(self, pct: int):
        self._download_bar.setValue(pct)

    def _on_download_failed(self, err: str):
        self._set_busy(False)
        self._update_container.setVisible(False)
        self._log_lbl.setVisible(True)
        self._set_expanded(False)
        self._log(f"✗ {err}", "#f43f5e")
        logging.error(f"OTA: {err}")

    def _on_download_complete(self, downloaded_path: str):
        """Download finished — generate updater.bat, launch it, and exit."""
        self._set_busy(False)
        self._download_bar.setValue(100)
        self._download_info_lbl.setText("✓ Download complete. Restarting…")
        self._download_info_lbl.setStyleSheet("color: #22c55e; font-weight: 600;" if isDarkTheme() else "color: #107c41; font-weight: 600;")
        logging.info(f"OTA: Downloaded update to {downloaded_path}")

        # Determine current exe path
        if getattr(sys, "frozen", False):
            current_exe = os.path.abspath(sys.executable)
        else:
            current_exe = os.path.abspath(sys.argv[0])

        # Generate and run the updater batch script
        bat_path = generate_updater_bat(current_exe, downloaded_path)
        logging.info(f"OTA: Launching updater script: {bat_path}")

        # Launch the batch file silently with clean environment
        CREATE_NO_WINDOW = 0x08000000
        clean_env = os.environ.copy()
        for k in list(clean_env.keys()):
            if "PYI" in k.upper() or "MEI" in k.upper() or "PYTHON" in k.upper():
                clean_env.pop(k, None)

        subprocess.Popen(
            ["cmd.exe", "/c", bat_path],
            creationflags=CREATE_NO_WINDOW,
            env=clean_env,
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
