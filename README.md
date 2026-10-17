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
- **☕ Support & Tipping**: Support continuous development directly through zero-fee Crypto (Binance Pay & USDT) in Settings.
- **🌙 Modern Windows 11 Design**: Clean, compact dark/light mode interface with real-time CPU and RAM monitoring rings powered by PySide6 & Fluent UI.

---

## 📋 Version History & Changelog

### 🟣 v1.3.0 (Latest Release) — Live Activity Terminal & Media Cache Cleaner
* **Live Activity Terminal**: Monospace real-time log terminal embedded right on the dashboard with auto-scrolling and 150-line memory buffer.
* **Media Editors Cache Cleaner**: Targets heavy media cache directories for Adobe Premiere, After Effects, Photoshop temp files, DaVinci Resolve, CapCut, and Filmora (strictly OFF by default).
* **Settings "Show/Hide Logs" Toggle**: Dynamically toggles terminal view between full (`390×440 px`) and compact mode (`390×315 px`).
* **Developer Support**: Sleek "Buy Me a Coffee ☕" section with zero-fee Crypto tipping (Binance Pay ID + USDT BEP20).
* **Open Source Transition**: Fully open-sourced under the **GNU General Public License v3.0 (GPLv3)**.

### 🟡 v1.2.0 — Advanced 14-Target Deep Clean Engine
* **14-Target Deep Cleaner**: Cleans Windows Update Cache (SoftwareDistribution), Prefetch, DirectX/GPU Shader Caches, WER, CrashDumps, Delivery Optimization, and thumbnail databases.
* **Optional Browser Cache Cleaner**: Cleans Chrome, Edge, Brave, Opera, and Firefox profile caches (OFF by default).
* **Hardcoded Safety Rules**: Absolute protection for `%USERPROFILE%\Downloads` and `$Recycle.Bin`.
* **Zero-Crash File Locking**: Every file deletion runs inside individual try/except blocks to silently bypass active Windows files.

### 🟢 v1.1.0 — Gaming Suite & Hardware Optimizations
* **Game Mode Power Switcher**: Auto-switches Windows power plan to "High Performance" on game launch.
* **Background Process Priority Reducer**: Lowers priority of background browsers and cloud sync tools to `BELOW_NORMAL`.
* **Standby Memory Purge**: Clears Windows Standby Memory via undocumented `NtSetSystemInformation` API to eliminate micro-stutters.
* **Game Watch List**: User-configurable watch list (`watch_list.json`) with auto-detection every 5 seconds.

### 🔵 v1.0.0 — Initial Stable Release
* **Core RAM Booster**: Win32 `psapi.EmptyWorkingSet` memory purge with real-time feedback.
* **Dual Metric Cards**: Circular ProgressRings for real-time CPU % and RAM % monitoring.
* **Background Auto-Purge**: Auto-optimizes RAM when system exceeds configurable threshold (default 85%).
* **Task Scheduler Startup**: Runs on startup with administrator rights without annoying UAC prompts.
* **Frameless Fluent UI**: Windows 11 Mica-style dark/light theme with system tray minimization.

> For full technical tables and implementation details, see [**CHANGELOG.md**](CHANGELOG.md).

---

## 📥 Download & Usage

1. Head to the official [**Releases**](https://github.com/muneebshahxad/NanoOpt/releases) page.
2. Download the latest compiled binary (`NanoOpt.exe`).
3. Right-click and select **Run as Administrator** (required for deep system cache cleanup and memory working set optimization).
4. No installation or Python setup needed — it is a standalone portable application.

---

## 📜 License

Distributed under the **GNU General Public License v3.0 (GPLv3)**.  
See the [LICENSE](LICENSE) file for the complete terms.

---

## 👤 Author
Developed by **[MuneebShahxad](https://github.com/muneebshahxad)**
