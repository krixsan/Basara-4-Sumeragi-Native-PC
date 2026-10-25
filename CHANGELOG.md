# Changelog

## [v1.8] - 2026-10-25 (Update 4: 2-Player Local Co-op)

### Added
- Local 2-Player Mode (Co-op) support. Up to 4 controllers.
- "Press to Join" auto-join system for controllers (solves virtual/ghost controller issues).
- Instance ID-based SDL3 controller routing.

### Fixed
- Controller 2 input hijacking Player 1.
- Controller detection issues on Windows with multiple XInput devices.

## [v1.5] - 2026-10-25

### Added
- **Priority Tuning**
  - Hybrid P/E-core scheduling (configurable process priority via basara.ini)
  - MMCSS "Pro Audio" integration for audio feeder thread (dynamic avrt.dll)
  - Present thread priority ABOVE_NORMAL
  - Graceful degradation for LTSC/Wine (avrt.dll absent)

- **Crash Reporter**
  - Minidump generation (5s timeout, recursion guard, rate limit 3/hour)
  - Log framework (`src/log.{h,cpp}`) — ring buffer 1000 lines, rotation 5×10MB, thread-safe
  - Opt-in telemetry with PII scrubbing (username, IP, MAC)
  - Consent dialog in launcher (via helper, not from crash process)
  - Hardware info collector (CPUID, DXGI, RtlGetVersion, GlobalMemoryStatusEx)
  - Raw crash log fallback (bypass log framework deadlock)

- **Packaging**
  - Portable ZIP release with 100 bundled runtime DLLs (SDL3, FFmpeg, libc++, libwinpthread, libZydis, etc) — self-contained, tested on clean PC without MSYS2
  - 5-step first-run wizard (Welcome → Legal Check → Locate eboot.bin → Auto-Build → Done)
  - eboot.bin validation supports SELF and ELF formats
  - Dependency checker (Vulkan 1.3, VC++ Redist 2015-2022, Windows 10 1809+, disk space) with download links
  - Inno Setup 6 installer (per-user, non-admin, preserves user/ folder)
  - GitHub Actions CI/CD (auto-build on tag v*)
  - `scripts/package_release.py` — packaging pipeline
  - `scripts/verify_release.py` — SHA256 + anti-leak verification
  - `build_launcher.py` — PyInstaller build for launcher
  - Setup Wizard button in launcher toolbar (re-run anytime)

- **Documentation**
  - `THIRD_PARTY_LICENSES.md` (shadps4, LibAtrac9, SDL3, Vulkan, FidelityFX, FFmpeg, libc++, etc)
  - `PRIVACY.md` (crash reporter data flow, PII scrubbing)
  - `LICENSE.txt` (MIT)
  - `README.md` + `README.id.md` with Quick Start, legal dump guide, troubleshooting
  - `CHANGELOG.md`

### Changed
- Default process priority from HIGH to ABOVE_NORMAL (fixes laptop thermal throttle stutter)
- Launcher: added dependency badges (Vulkan, VC++, Win, Storage)
- Launcher: added telemetry pills (Ask/Never/Always)
- Launcher: refined frosted glass UI

### Fixed
- Audio underrun (crackle) via MMCSS Pro Audio integration
- Frame pacing on hybrid Intel/AMD CPUs
- Crash on map load (VEH too aggressive — now skips benign exceptions, game SEH handles them)
- Logger deadlock in crash path (raw Win32 write bypasses log framework)
- Log flush (unbuffered + fflush on every write)
- ZIP missing runtime DLLs (previously error on clean PC)
