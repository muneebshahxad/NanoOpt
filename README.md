# 🚀 NanoOpt — High Performance Windows PC Optimizer

<p align="center">
  <strong>Lightweight · Modern Fluent Design · Safe RAM Purge · Junk Cleaner · Auto-Optimizer</strong>
</p>

---

## ✨ Features

- **🚀 Smart RAM Boost**: Safely frees memory via Windows `EmptyWorkingSet` while protecting critical apps.
- **🧹 System Junk Cleaner**: Cleans User Temp, Windows Temp, Prefetch, LogFiles, SoftwareDistribution downloads, crash dumps, and empties the Recycle Bin.
- **⚙️ Configurable JSON Settings**: Customize auto-purge RAM thresholds, polling intervals, and notification preferences.
- **🛡️ Process & Directory Whitelist**: Built-in exclusions for streaming apps (OBS), system components (`dwm.exe`, `explorer.exe`), games, and custom paths.
- **🔔 Windows System Tray & Toast Notifications**: Runs discreetly in your taskbar with rocket icon and delivers native Windows notifications when memory is recovered.
- **🪟 Auto-Start on Boot**: Configures Windows Task Scheduler with `HighestPrivileges` to seamlessly start with Windows without UAC prompts.
- **📊 Exportable Activity Logs**: Track every byte saved with rotating log files and one-click CSV exports.
- **🔄 Over-The-Air (OTA) Updates**: Automatically checks GitHub Releases for new updates and performs seamless one-click file updates.
- **🎨 Windows 11 Fluent UI**: System-adaptive dark and light mode powered by PySide6 and Fluent Widgets.

---

## 📥 Download & Usage

1. Go to the [**Releases**](https://github.com/muneebshahxad/NanoOpt/releases) page.
2. Download the latest `NanoOpt.exe`.
3. Right-click and **Run as Administrator** (required for deep system cache cleanup and memory management).

---

## 🛠️ Development & Building from Source

### Prerequisites
- Python 3.10+
- Windows 10 or 11 (64-bit)

### Installation
```bash
git clone https://github.com/muneebshahxad/NanoOpt.git
cd NanoOpt
pip install -r requirements.txt
```

### Run
```bash
python main.py
```

### Build Executable
```bash
pyinstaller --noconsole --onefile --icon=icon.ico --name=NanoOpt --distpath=dist_v2 --clean --hidden-import=requests --hidden-import=packaging --hidden-import=packaging.version main.py
```

---

## 👤 Author
Developed by **[MuneebShahxad](https://github.com/muneebshahxad)**
