# 📋 NanoOpt — Complete Feature & Version History Log
> Last Updated: October 2026 | Developer: MuneebShahxad | License: GNU GPLv3

---

## 🟣 v1.3.0 — Live Activity Log Terminal, Media Cache Cleaner & Open Source
> Released: October 2026

### New Features Added
| Feature | Details |
|---|---|
| **Live Activity Log Terminal** | Integrated read-only `TextEdit` terminal on the main dashboard with monospace Consolas (10pt) font, timestamped entries `[HH:MM:SS]`, and translucent theme-aware styling. |
| **Media Editors Cache Cleaner** | Dedicated cleaner for heavy photo/video editing caches: Adobe Suite (Premiere & AE `Media Cache`, Photoshop temp files, Illustrator `AIL*.tmp`), DaVinci Resolve (`CacheClip`, `ProxyMedia`), CapCut, and Filmora (Proxy, Render, Temp). |
| **Settings "Clean Media Editors Cache" Toggle** | User-controlled toggle switch in Settings. Set to **OFF by default** to protect user project caches until explicitly enabled. |
| **Settings "Show/Hide Logs" Toggle** | User-controlled visibility switch in Settings dialog (`show_logs`). Defaults to **ON**. Dynamically toggles terminal visibility and resizes window instantly. |
| **Thread-Safe PySide6 Logging** | Asynchronous workers (`RamWorker`, `JunkWorker`) emit granular updates through custom `Signal(str, str)` (Text, ColorCode) directly to the GUI thread without race conditions or UI freezing. |
| **Granular Step-by-Step Reporting** | Real-time feedback across all scanning zones: scanning notices (Cyan `#38bdf8`), freed byte amounts (Green `#22c55e`), locked system files skipped (Yellow `#facc15`), and process working set counts. |
| **Locked File Tracking** | Gracefully tracks locked/in-use Windows files during deep clean and reports summary to terminal without stopping execution. |
| **Auto-Scroll & 150-Line Buffer** | Auto-scrolls to the absolute bottom on every entry. Automatically caps history at 150 lines to prevent memory bloat. |
| **Adaptive Dynamic Layout** | Window height resizes dynamically (`390×315` when hidden, `390×440` when visible, up to `490` during OTA updates) with zero clipping or squishing of CPU/RAM cards. |
| **Developer Support & Monetization** | Sleek "Buy Me a Coffee ☕" section in Settings featuring a zero-fee copyable Crypto tipping modal (Binance Pay ID + USDT BEP20). |
| **Open Source Release (GPLv3)** | Officially transitioned to free and open source software under the GNU General Public License v3.0 with complete source repository. |

### Settings Dialog (v1.3.0 Final)
| Setting | Default | Description |
|---|---|---|
| Auto-Purge RAM threshold | 85% | SpinBox 50–99% with full % symbol |
| Enable Background Auto-Purge | ON | Toggle |
| Run on Startup | OFF | Toggle |
| Taskbar Toast Notifications | ON | Toggle |
| Game Mode | OFF | Toggle |
| Clean Browser Cache | OFF | Toggle (browser history/cache protected by default) |
| Clean Media Editors Cache | **OFF** | Toggle — Clears Adobe, DaVinci, CapCut, Filmora cache only when enabled |
| Show/Hide Logs | **ON** | Toggle — Controls terminal visibility on main dashboard |
| Process Exclusions | (list) | Comma-separated .exe names |
| Game Watch List | (empty) | Comma-separated game .exe names |
| Export CSV | — | Button |
| Open Log | — | Button |
| 🪙 Tip via Crypto | — | Copyable crypto donation modal button (Binance Pay & USDT) |
| Save & Apply | — | Button |

---

## 🟡 v1.2.0 — Advanced 14-Target Deep Clean Engine
> Released: October 2026

### New Features Added
| Feature | Details |
|---|---|
| **14-Target Deep Clean Engine** | Complete rewrite of `clean_junk()` targeting 14 Windows cleanup areas (see below). |
| **Optional Browser Cache Toggle** | New `Clean Browser Cache` toggle in Settings. Default = **OFF**. User must manually enable to clean browser caches. |
| **Settings Dialog Expanded** | Dialog width expanded `370px → 400px`. SpinBox width `120px → 135px` so `85%` is fully visible. |
| **"Run on Startup" Label Fix** | Removed "(Bypass UAC)" from label — now just says "Run on Startup". |
| **GPU Card Permanently Removed** | Reverted window to compact `390×315 px` dual-card layout (CPU + RAM only). |

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
- 🚫 **Recycle Bin** — Never touched (removed `SHEmptyRecycleBinW`).
- 🚫 **Downloads Folder** — Hardcoded blacklist, never scanned under any circumstance.
- 🔒 **Per-file try/except** — Every file operation individually error-trapped. Locked/in-use files skipped silently.
- 🧵 **Background thread** — Runs in `JunkWorker(QThread)` — zero UI freezing.

---

## 🟢 v1.1.0 — Gaming Suite & Hardware Monitoring
> Released: October 2026

### New Features Added
| Feature | Details |
|---|---|
| **Game Mode Power Plan Switcher** | Detects game launch and auto-switches Windows Power Scheme to "High Performance" via `powercfg -setactive 8c5e7fda...` |
| **Background Process Priority Reducer** | During game mode, auto-sets browsers/cloud sync apps (chrome.exe, msedge.exe, discord.exe, onedrive.exe) to `BELOW_NORMAL_PRIORITY_CLASS` |
| **Shader Cache Cleaner** | Clears DirectX and GPU shader caches: `D3DSCache`, NVIDIA `DXCache`, NVIDIA `GLCache`, AMD `DxCache` |
| **Standby Memory Purge** | Clears Windows Standby Memory using undocumented `NtSetSystemInformation` (SystemMemoryListInformation, MemoryPurgeStandbyList) via ctypes ntdll |
| **Auto-Optimize on Game Launch** | `GameWatcherWorker` thread monitors running processes every 5s, checks against `watch_list.json`. On game detected: triggers RAM purge + standby purge + power plan switch |
| **watch_list.json** | User-configurable game watch list stored in app directory. Editable via Settings dialog |
| **OTA Explorer Fix** | Updated updater to launch via `explorer.exe` to prevent PyInstaller PID inheritance crash |

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
| **Code Signing** | Self-signed Authenticode certificate (`CN=MuneebShahxad, O=NanoOpt Software`) |
| **Publisher Metadata** | Windows PE version info embedded: CompanyName, FileVersion, ProductVersion, LegalCopyright |

---

## 🔐 Code Signing & Security
| Item | Value |
|---|---|
| Certificate Subject | `CN=MuneebShahxad, O=NanoOpt Software, C=US` |
| Thumbprint | `0D812F74721E9113C702C40A7F3BA1575FD4A593` |
| Hash Algorithm | SHA256 |
| Type | Authenticode Digital Signature |
| Status | Valid |

---

## 🔗 Links
| Resource | URL |
|---|---|
| GitHub Repo | https://github.com/muneebshahxad/NanoOpt |
| Releases | https://github.com/muneebshahxad/NanoOpt/releases |
| Developer | https://github.com/muneebshahxad |
