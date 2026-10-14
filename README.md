<p align="center">
  <img src="assets/banner.png" alt="NanoOpt" width="100%" />
</p>

# 🚀 NanoOpt — High Performance Windows PC Optimizer

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPLv3" /></a>
  <img src="https://img.shields.io/badge/Source-Open%20Source-success.svg" alt="Open Source" />
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg" alt="Windows" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python" />
  <img src="https://img.shields.io/badge/Version-1.3.0-success.svg" alt="Version 1.3.0" />
</p>

<p align="center">
  <strong>Lightweight · Modern Fluent Design · Safe RAM Purge · Deep Junk & Media Cache Cleaner · Live Terminal · Auto-Optimizer</strong>
</p>

---

## ✨ Features

- **🚀 Smart RAM Boost**: Instantly frees up memory with a single click while safely protecting running programs via Win32 `EmptyWorkingSet`.
- **🧹 Deep Multi-Target Junk Cleaner**: Safely finds and purges junk files across Windows Update cache, Prefetch, GPU shader caches, CrashDumps, and temporary directories.
- **🎬 Media Editors Cache Cleaner**: Safely cleans heavy media cache files for Adobe Creative Suite (Premiere, After Effects, Photoshop temp files), DaVinci Resolve, CapCut, and Filmora (turned **OFF** by default in Settings to protect workflow caches).
- **🖥️ Live Activity Log Terminal**: Watch live step-by-step cleaning details right on your dashboard with color-coded feedback (easily toggle on/off in Settings).
- **🛡️ 100% Safe & Protected**: Your personal **Downloads** folder and **Recycle Bin** are strictly protected and never touched.
- **🎮 Game Mode Optimizer**: Automatically switches Windows to "High Performance" power mode and lowers background app priority when gaming.
- **⚡ Standby Memory Purge**: Clears Windows standby memory list before games start to eliminate in-game micro-stutters.
- **🎯 Game Watch List**: Automatically detects when your selected games launch and applies instant optimizations.
- **🌐 Optional Browser Cache Clean**: Choose whether to clean browser caches (Chrome, Edge, Firefox, Brave, Opera) via a simple toggle in Settings (turned **OFF** by default).
- **⚙️ Auto-Purge RAM**: Set your preferred RAM threshold (e.g. 85%) so NanoOpt automatically purges memory in the background when usage gets high.
- **🛡️ App & Directory Whitelist**: Add your favorite apps and folders to the exclusion list so they are never touched.
- **🪟 Run on Startup**: Seamlessly starts with Windows using Task Scheduler without annoying UAC prompts.
- **🔔 Desktop Notifications**: Displays helpful, silent desktop notifications when memory is recovered.
- **📊 Activity History & CSV Export**: Automatically logs all cleaning events with one-click export to CSV.
- **🔄 Instant Auto-Updates (OTA)**: Checks for new versions automatically and updates in one click.
- **☕ Support & Tipping**: Support continuous development directly through Card/Apple Pay or zero-fee crypto in Settings.
- **🌙 Modern Windows 11 Design**: Clean, compact dark/light mode interface with real-time CPU and RAM monitoring rings powered by PySide6 & Fluent UI.

---

## 📋 Changelog & Version History

See the complete feature log and release history across all versions in [**CHANGELOG.md**](CHANGELOG.md).

---

## 📥 Download (Pre-built Executable)

1. Head to the official [**Releases**](https://github.com/muneebshahxad/NanoOpt/releases) page.
2. Download the latest compiled binary (`NanoOpt.exe`).
3. Right-click and select **Run as Administrator** (required for deep system cache cleanup and memory working set optimization).
4. No installation or Python setup needed — it is a standalone portable application.

---

## 🛠️ Building from Source

### Prerequisites
* Windows 10 or 11
* Python 3.10+ (Python 3.12 recommended)
* Administrator privileges

### Installation & Run

1. **Clone the repository:**
   ```bash
   git clone https://github.com/muneebshahxad/NanoOpt.git
   cd NanoOpt
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run NanoOpt:**
   ```bash
   python main.py
   ```

4. **Compile to Standalone `.exe` (PyInstaller):**
   ```bash
   pyinstaller --noconfirm --clean NanoOpt.spec
   ```

---

## 📜 License

Distributed under the **GNU General Public License v3.0 (GPLv3)**.  
See the [LICENSE](LICENSE) file for the complete terms.

---

## 👤 Author
Developed by **[MuneebShahxad](https://github.com/muneebshahxad)**
