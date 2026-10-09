# 📋 NanoOpt — Complete Feature & Version History Log
> Last Updated: October 2026 | Developer: MuneebShahxad

---

## 🔵 v1.0.0 — Initial Stable Release
> Released: September 2026

### Core Features
| Feature | Details |
|---|---|
| **Boost RAM** | Clears working set memory of all active processes via Windows `psapi.EmptyWorkingSet` |
| **Clean Junk (Basic)** | Clears standard Windows temp folders (`%TEMP%`, `C:\Windows\Temp`, SoftwareDistribution, Prefetch, Logs, WER) |
| **CPU Metric Card** | Real-time CPU usage % via circular ProgressRing (Red `#f43f5e`) |
| **RAM Metric Card** | Real-time RAM usage % + GB breakdown via circular ProgressRing (Cyan `#0ea5e9`) |
| **Auto-Purge RAM** | Background thread that auto-triggers RAM purge when usage exceeds a configurable threshold (default 85%) |
| **Cooldown Timer** | Prevents auto-purge from running more than once per configurable cooldown period (default 300s) |
| **Process Whitelist** | User-defined list of processes to skip during RAM purge (e.g. obs64.exe, discord.exe, steam.exe) |
| **Directory Whitelist** | User-defined directories to skip during junk cleaning |
| **Run on Startup** | Uses Windows Task Scheduler to autostart NanoOpt without UAC prompts |
| **Taskbar Notifications** | Windows toast notifications for boost/clean events |
| **Activity Logger** | Rolling `.log` file (`nanoopt_activity.log`) recording all optimization events |
| **CSV Export** | Export activity log as structured CSV from Settings |
| **Open Log** | Open log file directly from Settings dialog |
| **Dark / Light Theme** | System-adaptive auto dark/light mode (PySide6 + QFluentWidgets) |
| **Frameless Window** | Custom frameless window with drag support (`390 × 315 px`) |
| **System Tray** | Minimize to tray silently. Double-click to restore. Right-click tray menu for quick actions |
| **Silent Close** | Clicking X hides to tray (no notification). "Exit NanoOpt" in tray menu = full shutdown |
| **OTA Auto-Updater** | Checks GitHub Releases API for newer version on startup (3s delay). Downloads and installs update automatically |
| **Rocket Icon 🚀** | Segoe UI Emoji rocket used for taskbar, tray icon, and exe icon |
| **Admin Elevation** | Auto-requests UAC elevation at startup. Shows "✓ Running as Administrator" badge |
| **Footer Link** | `NanoOpt v{VERSION} · Developed by MuneebShahxad` — MuneebShahxad is clickable → GitHub profile |
| **Proprietary License** | `Copyright (c) 2026 MuneebShahxad. All Rights Reserved.` |
| **Closed Source** | `main.py` and `requirements.txt` NOT tracked in git. Binary-only public repo |
| **Code Signing** | Self-signed Authenticode certificate (`CN=MuneebShahxad, O=NanoOpt Software`) |
| **Publisher Metadata** | Windows PE version info embedded: CompanyName, FileVersion, ProductVersion, LegalCopyright |

### Settings Dialog (v1.0.0)
- Auto-Purge RAM threshold (SpinBox 50–99%)
- Enable/Disable Background Auto-Purge toggle
- Run on Startup toggle
- Taskbar Toast Notifications toggle
- Process Exclusions text field
- Export CSV button
- Open Log button
- Save & Apply button

### Technical Stack
- **Language:** Python 3.12
- **UI:** PySide6 + qfluentwidgets
- **Build:** PyInstaller `--onefile --noconsole`
- **Portable Python:** `C:\Users\MuneebShahxad\.python312\`
- **OTA Fix:** Uses `explorer.exe` to launch updater to avoid `_PYI_ONEFILE_PARENT` inheritance lock

---

## 🟢 v1.1.0 — Gaming Suite & Hardware Monitoring
> Released: October 2026

### New Features Added
| Feature | Details |
|---|---|
| **Game Mode Power Plan Switcher** | Detects game launch and auto-switches Windows Power Scheme to "High Performance" via `powercfg -setactive 8c5e7fda...` |
| **GPU & VRAM Monitoring (Added then Removed)** | Initially added 3rd MetricCard (Emerald `#10b981`) showing GPU%, VRAM used/total, GPU temp via `nvidia-smi`. Later REMOVED by user request |
| **Background Process Priority Reducer** | During game mode, auto-sets browsers/cloud sync apps (chrome.exe, msedge.exe, discord.exe, onedrive.exe) to `BELOW_NORMAL_PRIORITY_CLASS` |
| **Shader Cache Cleaner** | Clears DirectX and GPU shader caches: `D3DSCache`, NVIDIA `DXCache`, NVIDIA `GLCache`, AMD `DxCache` |
| **Standby Memory Purge** | Clears Windows Standby Memory using undocumented `NtSetSystemInformation` (SystemMemoryListInformation, MemoryPurgeStandbyList) via ctypes ntdll |
| **Auto-Optimize on Game Launch** | `GameWatcherWorker` thread monitors running processes every 5s, checks against `watch_list.json`. On game detected: triggers RAM purge + standby purge + power plan switch |
| **watch_list.json** | User-configurable game watch list stored in app directory. Editable via Settings dialog |
| **Responsive UI Layout** | Window dynamically resizes: `580×315` normal, `580×365` expanded for OTA update bar (later reverted to 390 after GPU card removal) |
| **GPU Card Removed** | After user review, GPU MetricCard was removed. Window reverted to compact `390×315 px` with only CPU+RAM cards |
| **OTA Explorer Fix** | Updated updater to launch via `explorer.exe` to prevent PyInstaller PID inheritance crash |
| **Donationware Button (Added then Removed)** | "☕ Support" button added briefly, then REMOVED by user — no payment gateway available |

### Settings Dialog Changes (v1.1.0)
- Added: **Game Mode** toggle (Auto Power Plan & Priority) — Default OFF
- Added: **Game Watch List** text field (comma-separated game .exe names)

### GitHub
- `App_Certificate.cer` pushed to repo for publisher trust verification

---

## 🟡 v1.2.0 — Advanced 14-Target Deep Clean Engine
> Released: October 2026

### New Features Added
| Feature | Details |
|---|---|
| **14-Target Deep Clean Engine** | Complete rewrite of `clean_junk()` targeting 14 Windows cleanup areas (see below) |
| **Optional Browser Cache Toggle** | New `Clean Browser Cache` toggle in Settings. Default = **OFF**. User must manually enable to clean browser caches |
| **Settings Dialog Expanded** | Dialog width expanded `370px → 400px`. SpinBox width `120px → 135px` so `85%` is fully visible |
| **"Run on Startup" Label Fix** | Removed "(Bypass UAC)" from label — now just says "Run on Startup" |
| **GPU Card Permanently Removed** | Reverted window to compact `390×315 px` dual-card layout (CPU + RAM only) |

### 14 Deep Clean Targets
| # | Target | What Gets Cleaned |
|---|---|---|
| 1 | **Base Temp Folders** | `%TEMP%`, `%TMP%`, `C:\Windows\Temp`, `%USERPROFILE%\Local Settings\Temp`, `%LOCALAPPDATA%\Temp` |
| 2 | **Windows Update Cache** | Stops `wuauserv`, `UsoSvc`, `bits`, `dosvc` → clears `SoftwareDistribution\Download`, DataStore logs → restarts services |
| 3 | **Windows Prefetch** | `C:\Windows\Prefetch` |
| 4 | **System-Wide Junk Extensions** | `.log`, `.tmp`, `.bak`, `.chk`, `.old`, `.dmp` in temp/WER/CrashDumps/LogFiles |
| 5 | **Windows Event Logs** | All logs cleared via `wevtutil.exe cl` (Admin only) |
| 6 | **Microsoft Defender Temp** | Defender Support logs, Scan History Results, `MpCmdRun.log` |
| 7 | **Downloaded Program Files** | `C:\Windows\Downloaded Program Files` |
| 8 | **Browser & Internet Caches** | Chrome, Edge, Brave, Opera, Firefox profile caches + `INetCache`, `WebCache` (only if toggle enabled) |
| 9 | **DirectX & GPU Shader Caches** | `D3DSCache`, NVIDIA `DXCache`/`GLCache`, AMD `DxCache`/`GLCache`, Intel `ShaderCache` |
| 10 | **Delivery Optimization Files** | `SoftwareDistribution\DeliveryOptimization`, Network Downloader, DO Cache/Logs |
| 11 | **Old Device Driver Packages** | `DriverStore\Temp`, `Driver Cache`, `setupapi.offline.log` |
| 12 | **Language Resource & Font Caches** | `%LOCALAPPDATA%\FontCache`, System FontCache |
| 13 | **Temporary Windows Installation Files** | `$WINDOWS.~BT`, `$Windows.~WS`, `Panther`, `Minidump`, `memory.dmp`, `setupact.log`, `setuperr.log` |
| 14 | **Explorer Thumbnail Cache** | `thumbcache_*.db`, `iconcache_*.db` in `%LOCALAPPDATA%\Microsoft\Windows\Explorer` |

### Safety Rules (v1.2.0)
- 🚫 **Recycle Bin** — Never touched (removed `SHEmptyRecycleBinW`)
- 🚫 **Downloads Folder** — Hardcoded blacklist, never scanned under any circumstance
- 🔒 **Per-file try/except** — Every file operation individually error-trapped. Locked/in-use files skipped silently
- 🧵 **Background thread** — Runs in `JunkWorker(QThread)` — zero UI freezing

### Settings Dialog (v1.2.0 Final)
| Setting | Default | Description |
|---|---|---|
| Auto-Purge RAM threshold | 85% | SpinBox 50–99% with fully visible % symbol |
| Enable Background Auto-Purge | ON | Toggle |
| Run on Startup | OFF | Toggle (label cleaned, no "Bypass UAC" text) |
| Taskbar Toast Notifications | ON | Toggle |
| Game Mode | OFF | Toggle |
| Clean Browser Cache | **OFF** | New toggle — browser caches only cleaned if explicitly enabled |
| Process Exclusions | (list) | Comma-separated .exe names |
| Game Watch List | (empty) | Comma-separated game .exe names |
| Export CSV | — | Button |
| Open Log | — | Button |
| Save & Apply | — | Button |

---

## 🔐 Code Signing & Security
| Item | Value |
|---|---|
| Certificate Subject | `CN=MuneebShahxad, O=NanoOpt Software, C=US` |
| Thumbprint | `0D812F74721E9113C702C40A7F3BA1575FD4A593` |
| Hash Algorithm | SHA256 |
| Type | Self-signed Authenticode |
| Location | `Cert:\CurrentUser\My` |
| Public Cert | `App_Certificate.cer` pushed to GitHub repo |

---

## 📁 Project Structure
```
NanoOpt/
├── main.py                  ← Source (NOT in git)
├── icon.ico                 ← App icon
├── icon.png                 ← Icon PNG
├── version_info.txt         ← Windows PE metadata (NOT in git)
├── settings.json            ← Auto-created at runtime
├── watch_list.json          ← Auto-created at runtime
├── nanoopt_activity.log     ← Auto-created at runtime
├── App_Certificate.cer      ← In git (for publisher trust)
├── .gitignore               ← In git
├── LICENSE                  ← In git (Proprietary)
├── README.md                ← In git
├── assets/
│   └── banner.png           ← In git
└── builds/
    ├── v1.0.0/NanoOpt.exe
    ├── v1.1.0/NanoOpt.exe
    └── v1.2.0/NanoOpt.exe   ← Current
```

---

## ⚙️ Build Command (Standard)
```powershell
& "C:\Users\MuneebShahxad\.python312\Scripts\pyinstaller.exe" `
  --noconsole --onefile --icon=icon.ico `
  --version-file=version_info.txt `
  --name=NanoOpt `
  --distpath=builds\v1.2.0 `
  --clean `
  --hidden-import=requests `
  --hidden-import=packaging `
  --hidden-import=packaging.version `
  main.py
```

## 🔏 Sign Command (Standard)
```powershell
$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -match "MuneebShahxad" } | Select-Object -First 1
Set-AuthenticodeSignature -FilePath "builds\v1.2.0\NanoOpt.exe" -Certificate $cert -HashAlgorithm SHA256
```

---

## 🔗 Links
| Resource | URL |
|---|---|
| GitHub Repo | https://github.com/muneebshahxad/NanoOpt |
| Releases | https://github.com/muneebshahxad/NanoOpt/releases |
| Developer | https://github.com/muneebshahxad |

---

## ❌ Features Deliberately NOT Implemented / Removed
| Feature | Reason |
|---|---|
| GPU MetricCard | Removed — not all PCs have NVIDIA, showed N/A on most systems, increased window size |
| Donationware "☕ Support" button | Removed — no payment gateway available yet |
| "(Bypass UAC)" in startup label | Removed — confusing for regular users |
| Recycle Bin emptying (`SHEmptyRecycleBinW`) | Removed in v1.2.0 — user safety requirement |
| GPU monitoring (`nvidia-smi`) | Removed with GPU card — unnecessary background CPU usage |
