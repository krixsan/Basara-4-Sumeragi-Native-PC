# HANDOFF: Sengoku Basara 4 Sumeragi PC Native Port — 2026-11-05

> **Instruksi untuk AI yang menerima dokumen ini**:
> Kamu adalah asisten yang membantu user melanjutkan proyek porting game.
> Baca seluruh dokumen ini dulu. Kalau ada data yang tidak jelas, tanya user — jangan tebak.
> Semua klaim di bawah punya bukti path/baris. Data yang tidak ada ditulis "tidak ada" atau "belum diverifikasi".

---

## 1. IDENTITAS PROYEK

| Field | Value |
|---|---|
| Nama Proyek | Basara 4 Sumeragi PC Native Port (`basara_pc`) |
| Game / Serial | Sengoku Basara 4 Sumeragi / `CUSA01159` |
| Region / Platform | Region tidak tercatat di repo (title ID `CUSA01159`) / PS4 |
| Metode | Native x86_64 execution + runtime HLE (bukan static recompilation) |
| Workspace | `F:\Project Porting Game PS4\Basara 4 Sumeragi v2.0-Perf` |
| Repo Fondasi | shadPS4 (Vulkan GPU core) + runtime native custom di `src/` |
| Versi Saat Ini | `v2.1.0` (`VERSION.txt`) |
| Branch / Commit | `main` / `bbd3802` |
| Status Git | Bersih (tidak ada perubahan belum di-commit) |

---

## 2. STATUS MILESTONE

| Milestone | Status | Catatan |
|---|---|---|
| M0 — Foundation | ✅ | Riset dan keputusan arsitektur di `docs/research/` (2026-10-22) |
| M1 — Runtime/Recomp | ✅ | Guest x86-64 berjalan native; HLE syscall di `src/runtime*.c` |
| M2 — Renderer | ✅ | Vulkan 1.3 lewat shadPS4; render scale, RCAS, FXAA sudah ada di kode |
| M3 — Systems | ✅ | Audio, pad, savedata, net, trophy, crash reporter, launcher |
| M4 — Stability | 🚧 | Freeze transisi cutscene; watchdog 3 detik; belum ada validasi pasca-rilis |
| M5 — Release | 🚧 | ZIP v2.1.0 sudah dibuat; v2.1.1 tertahan oleh M4 |

**Milestone saat ini**: M4 — Stability menuju v2.1.1.
**Commit terakhir**: `bbd3802` — `fix: resolve paths relative to executable directory instead of CWD` (2026-11-01 17:10 +0800).
**Catatan**: `VERSION.txt` = `v2.1.0`, tetapi banner engine masih mencetak `v2.0` (`src/probe.c:877`).

---

## 3. APA YANG SUDAH TERBUKTI BERJALAN

1. ✅ **Boot sampai gameplay**: log menunjukkan `Entering original x86-64 code at guest offset 0x9c3c60` dan thread game berjalan — `user/logs/basara.log`, `user/logs/last_run.log`.
2. ✅ **Renderer Vulkan 1080p**: log mendeteksi `NVIDIA GeForce RTX 3060, 12115 MiB VRAM; Vulkan 1.4.351` dan display `PHL 272M8 1920x1080` — `user/logs/last_run.log` baris 8-12.
3. ✅ **Audio 48 kHz**: `Audio port 0/1/8 opened (ch=8, rate=48000, frames=256)` dan `Video/Audio stream starting: 4096 bytes, 2 ch, 48000 Hz` — `user/logs/basara.log`.
4. ✅ **Gamepad**: `Gamepad connected: Xbox 360 Controller` — `user/logs/basara.log`.
5. ✅ **Cutscene / AvPlayer teardown**: decoder, demuxer, dan watchdog di-join tanpa deadlock; buffer dibersihkan — `crashes/crash_20261101_181023.txt` (bagian `CRITICAL CONTEXT SCAN`).
6. ✅ **Runtime patch stack canary**: patch `BBPATCH2` 4 entry, termasuk trampoline bounds-check di `0xc32cf2` — `make_patch.py`, `out/patches.bin` (132 byte).
7. ✅ **Crash reporter**: laporan `.txt` + bundle `.zip` berhasil dibuat dari simulasi `--test-crash` — `crashes/crash_20261101_181023.txt`, `crashes/crash_bundle_20261101_181023.zip`.
8. ✅ **FXAA pass sudah dikompilasi dan dipanggil**: `fxaa_pass.Create(...)` dan `fxaa_pass.Render(...)` — `gpu/shadps4/video_core/renderer_vulkan/vk_presenter.cpp:326,651`; build log memuat `fxaa_pass.cpp.obj` — `build_output.log`.

**Belum terbukti**: Tidak ada log run penuh pasca-rilis v2.1.0 yang menunjukkan 5+ cutscene selesai tanpa watchdog dan gameplay stabil 5+ menit. Log terakhir yang tersedia adalah run cutscene pendek 2026-10-31 19:25 atau simulasi crash.

---

## 4. BLOCKER SAAT INI (KRITIS)

### Blocker #1 — Freeze transisi cutscene; `sceAvPlayerDisableStream` masih stub

**Gejala** (dari log):
```text
GPU [Lib.AvPlayer] <Error> gpu\shadps4\core\libraries\avplayer\avplayer.cpp:204
sceAvPlayerDisableStream: (STUBBED) called
```
Baris yang sama muncul di semua log terbaru (`crashes/log_20261101_*.txt`, `user/logs/last_run.log` baris 1052). Known issue resmi v2.1.0 juga menyebut freeze transisi karakter sebelum Stage Select.

- **Root cause (dugaan kuat, perlu verifikasi)**: fungsi hanya mengembalikan `ORBIS_OK` tanpa benar-benar menonaktifkan stream. Game menunggu state stream berubah; watchdog lalu men-skip cutscene setelah 3 detik.
- **File terkait**: `gpu/shadps4/core/libraries/avplayer/avplayer.cpp:203-209`; watchdog di `gpu/shadps4/core/libraries/avplayer/avplayer_source.cpp:1329-1357`.
- **Rencana Fix**:
  1. Jalankan cutscene transisi dengan `BASARA_AVPLAYER_TRACE=1`, catat `stream_id` dan urutan call.
  2. Cek API stream di `avplayer_source.*`; implementasikan disable/enable yang mengubah state player, bukan no-op.
  3. Uji ulang transisi karakter, Stage Select, dan Roulette; target nol `[AV_WATCHDOG]`.

### Blocker #2 — Dokumen v2.1.1 klaim watchdog 10 detik, kode masih 3 detik

**Gejala** (kode vs dokumen):
```text
avplayer_source.cpp:1330   if (delivered_now == last_delivered && elapsed > 3000) {
docs/CHANGELOG_v2.1.1_CUTSCENE_FIXES.md:96   elapsed > 10000
docs/CUTSCENE_FREEZE_FIX_COMPLETION.md:102   elapsed > 10000
```
- **Root cause**: perubahan v2.1.1 tidak ada di HEAD, atau dokumen ditulis sebelum patch masuk. Ini inconsistency, bukan sekadar dokumen basi.
- **File terkait**: `gpu/shadps4/core/libraries/avplayer/avplayer_source.cpp:1329-1330`; `docs/CHANGELOG_v2.1.1_CUTSCENE_FIXES.md`; `docs/CUTSCENE_FREEZE_FIX_COMPLETION.md`.
- **Rencana Fix**:
  1. Putuskan target: 3 detik (agresif, sesuai kode) atau 10 detik (sesuai dokumen).
  2. Ubah salah satu, lalu rebuild `basara_pc.exe`.
  3. Update `VERSION.txt`, `CHANGELOG.md`, dan dokumen terkait agar konsisten.

### Blocker #3 — Belum ada validasi manual pasca-v2.1.0

**Gejala** (dari laporan crash):
```text
Trigger : TEST SIMULATION (--test-crash): Exit Code 0xC0000005
```
- **Root cause**: crash report terbaru adalah simulasi yang sengaja dibuat untuk menguji crash reporter, bukan crash game nyata (`crashes/crash_20261101_181023.txt` baris 5). Tidak ada log sesi gameplay penuh setelah ZIP v2.1.0 dibuat.
- **File terkait**: `crashes/crash_20261101_*.txt`, `user/logs/last_run.log`, `user/logs/usanA_monitor.txt`.
- **Rencana Fix**:
  1. Jalankan minimal 5 cutscene berbeda + 5 menit gameplay + 1 stage select.
  2. Simpan log baru; pastikan tidak ada `STOP: guest stack protector` dan hitung kemunculan `[AV_WATCHDOG]`.
  3. Baru nyatakan v2.1.1 siap rilis.

**Risiko tambahan (bukan blocker aktif)**: log lama menunjukkan `MapViewOfFile3 failed ... error 1455` saat commit charge tinggi — `crashes/log_20261031_085707.txt:1856`. Mesin punya 16 GB RAM dan pagefile 9.330 MB; naikkan pagefile jika error ini muncul lagi.

---

## 5. NEXT STEP (PRIORITAS)

- **Immediate**:
  1. Implementasi `sceAvPlayerDisableStream` yang benar — 0,5-1 hari — `gpu/shadps4/core/libraries/avplayer/avplayer.cpp:203`.
  2. Selaraskan timeout watchdog (3 detik vs 10 detik) lalu rebuild — 1 jam — `avplayer_source.cpp:1330` + docs.
  3. Validasi manual cutscene transisi, Stage Select, dan Roulette — 0,5 hari — rekam ke `user/logs/`.
- **Short-term**:
  4. Perbaiki banner versi engine `v2.0` menjadi mengikuti `VERSION.txt` — 15 menit — `src/probe.c:877`.
  5. Update dokumen basi: `docs/BASARA4_PROJECT_STATUS.md`, `docs/implementation-status.md`, `docs/FXAA_TODO.md`, `docs/build-instructions.md`.
  6. Package v2.1.1: `python scripts/package_release.py --version 2.1.1` lalu `python scripts/verify_release.py`.
- **Deferred (bukan blocker)**:
  - Integrasi ultrawide — script ada di `scripts/` tetapi belum masuk launcher.
  - Discord Rich Presence — belum ada implementasi.
  - Auto-upload crash report — masih lokal.
  - Steam Deck / Linux — Windows-only.

---

## 6. TOOLCHAIN AKTIF

| Tool | Versi | Path | Status |
|---|---|---|---|
| Compiler (utama) | clang 23.1.3 | `F:\msys64\clang64\bin\clang.exe` | ✅ |
| Compiler C++ | clang++ 23.1.3 | `F:\msys64\clang64\bin\clang++.exe` | ✅ |
| Build System | Ninja 1.13.2 | `F:\msys64\clang64\bin\ninja.exe` | ✅ |
| CMake | 4.4.4 | `C:\Program Files\CMake\bin\cmake.exe` | ✅ |
| MSYS2 | CLANG64 | `F:\msys64\clang64` | ✅ |
| Vulkan SDK | `F:\Vulkanskd` | `VULKAN_SDK` | ✅ |
| glslangValidator | ada | `F:\Vulkanskd\Bin\glslangValidator.exe` | ✅ |
| Python | 3.12.10 | `C:\Users\krixs\AppData\Local\Programs\Python\Python312\python.exe` | ✅ |
| Ghidra | tidak ada | tidak ditemukan | ⏸️ |
| RPCS3 | tidak relevan | PS4, bukan PS3 | ⏸️ |

**Build resmi**: `win_build.sh` (MSYS2 CLANG64 + CMake + Ninja). Script ini mengonfigurasi `out/gpu`, build `basara_pc.exe`, lalu menyalin ke root. Build log terakhir sukses — `build_output.log`, `out/gpu/basara_pc.exe` (2026-10-31 10:47).
**Catatan**: `gcc` WinLibs juga ada di PATH, tetapi jangan dipakai untuk build utama; campur toolchain bisa merusak link DLL.

---

## 7. FILE KUNCI & ISI RINGKAS

| File | Isi / Baris Penting |
|---|---|
| `src/probe.c` | 70.731 byte — loader/entry engine; `:877` banner versi masih `v2.0` |
| `src/runtime.c` | 21.542 byte — runtime HLE; cek canary guest di `:210` |
| `src/runtime_memory.c` | 66.536 byte — mapping memori guest; `MapViewOfFile3` |
| `gpu/shadps4/core/libraries/avplayer/avplayer.cpp` | `:203-209` — `sceAvPlayerDisableStream` stub |
| `gpu/shadps4/core/libraries/avplayer/avplayer_source.cpp` | `:729-740` drift fallback; `:1263` null check audio; `:1329-1330` watchdog 3000 ms |
| `gpu/shadps4/video_core/renderer_vulkan/vk_presenter.cpp` | `:326` create FXAA; `:651` render FXAA; render scale/RCAS |
| `gpu/shim/bbport_settings.cpp` | load/save `basara.ini` (render scale, FSR, RCAS, dll) |
| `launcher.py` | Launcher Tkinter/CustomTkinter; wizard, repair, crash reporter; path relatif ke exe (commit `bbd3802`) |
| `scripts/auto_builder.py` | Link 7 module wajib: `libc.prx`, `libSceFios2.prx`, `ulobjmgr.sprx`, `libSceFiber.sprx`, `libSceUlt.sprx`, `libSceAjm.sprx`, `libSceNgs2.sprx` |
| `scripts/package_release.py` | ZIP rilis + `CHECKSUMS.txt`; `--version`, `--out-dir` |
| `scripts/verify_release.py` | Verifikasi isi ZIP dan checksum |
| `make_patch.py` | Generator `BBPATCH2`: 4 entry, base `0x400000`, trampoline `0x1063e20` |
| `out/patches.bin` | 132 byte — patch runtime, jangan diedit manual |
| `basara.ini` | Config aktif: `process_priority=high`, `fps_limit=0`, `anisotropy=16`, `fsr1=1`, `rcas=1`, `render_scale=1.0`, `anti_aliasing=off` |
| `docs/CHANGELOG_v2.1.1_CUTSCENE_FIXES.md` | Klaim fix 4 bug; timeout 10 detik (tidak cocok dengan kode) |
| `docs/CUTSCENE_FREEZE_FIX_COMPLETION.md` | Klaim 4/4 bug fixed; juga klaim 10 detik |

**Ukuran kode**: `gpu/` 334 `.cpp` + 888 `.h` (1.791 file, 57,6 MB); `src/` 36 file (0,8 MB); `scripts/` 45 file; `docs/` 34 file.

**⚠️ JANGAN Edit Manual**: `out/boot-linked.bin` (29,8 MB, hasil linker), `out/patches.bin` (binary patch), `extracted_game/` (dump game 27,6 GB), `gpu/third_party/` (submodule). Untuk patch guest, ubah `make_patch.py` lalu generate ulang.

---

## 8. PELAJARAN & PITFALL (JANGAN ULANGI)

1. ❌ Jangan percaya klaim dokumen tanpa cek kode → ✅ grep dulu (contoh: watchdog 10 detik hanya ada di dokumen, kode masih 3000 ms).
2. ❌ Jangan `git add .` → ✅ `git add <file spesifik>`; `extracted_game/` 27,6 GB dan `user/` 1,1 GB di-ignore, tetapi tetap berisiko.
3. ❌ Jangan join watchdog/thread sambil memegang `m_state_mutex` → ✅ pakai `try_to_lock`; komentar di `avplayer_source.cpp:1348-1350` menjelaskan deadlock teardown.
4. ❌ Jangan mengedit `eboot.bin` asli → ✅ pakai runtime patch `BBPATCH2` lewat `make_patch.py`.
5. ❌ Jangan pilih hanya `eboot.bin` di wizard → ✅ pilih folder game lengkap (`eboot.bin` + `sce_module` + `sce_sys` + `nativePS4`); tanpa `sce_module` audio crackle/crash.
6. ❌ Jangan build dengan gcc WinLibs → ✅ pakai `win_build.sh` (MSYS2 CLANG64).
7. ❌ Jangan langsung diagnosis dari `crashes/*.txt` → ✅ baca baris `Trigger`; banyak laporan adalah `TEST SIMULATION (--test-crash)`.
8. ❌ Jangan asumsikan path kerja = folder exe → ✅ commit `bbd3802` memaksa path relatif ke lokasi executable; jangan regresi ke CWD.

---

## 9. RIWAYAT KEPUTUSAN PENTING

| # | Keputusan | Alasan | Tanggal |
|---|---|---|---|
| 1 | Native x86_64 + runtime HLE, bukan emulator penuh | PS4 sudah x86-64; overhead emulasi tidak perlu | 2026-10-22 |
| 2 | Reuse shadPS4 untuk Vulkan/GNM | Renderer dan shader recompiler sudah matang; GPL-2.0 | 2026-10-24 |
| 3 | Patch guest lewat trampoline runtime, bukan ubah `eboot.bin` | Menjaga dump asli, patch bisa didistribusikan terpisah | 2026-11-01 |
| 4 | Watchdog cutscene sebagai safety net | Game tidak boleh hang permanen saat decoder macet | 2026-10-28 |
| 5 | Launcher Python + PyInstaller | Cepat diiterasi, UI Tkinter/CustomTkinter, crash reporter terintegrasi | 2026-10-24 |
| 6 | Lisensi proyek MIT, komponen shadPS4 GPL-2.0 | Kompatibilitas distribusi dan atribusi | 2026-10-24 |

---

## 10. CARA RESUME PROYEK

Kalau user bilang **"lanjut"**, AI harus:
1. **Konfirmasi pemahaman**: print ringkasan (Proyek, Milestone, Blocker, Next Step).
2. **Tanya user**: "Lanjut dari mana? (a) fix blocker #1, (b) cek file tertentu, (c) lain?"
3. **Eksekusi** sesuai aturan:
   - Backup sebelum edit: `Copy-Item $file "$file.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"`.
   - Safety check sebelum commit: `git status --short | Select-String "extracted_game|\.iso|\.pkg|user/"`.
   - Build gagal 3x: **STOP** dan tanya user.
   - Butuh edit source: **STOP** dan review dulu (kecuali user sudah menyetujui).
4. **Verifikasi**: build lewat `win_build.sh`, jalankan minimal satu cutscene, cek `user/logs/last_run.log` untuk `STOP:` dan `[AV_WATCHDOG]`.

---

## 11. BATASAN AI PENERIMA

- ❌ Kalau dokumen ini dipaste ke chat AI tanpa akses filesystem: AI **tidak bisa** membaca file lokal, build, atau menjalankan game.
- ✅ AI **bisa** analisis log, desain strategi, review kode, dan menulis prompt untuk agent lain (Cline/Claude Code/Codex).
- ✅ AI yang punya akses workspace **bisa** scan, baca, build, dan jalankan test — tetapi tetap wajib minta konfirmasi sebelum edit source atau commit.
- ❌ Jangan mengarang status. Kalau data tidak ada, tulis "belum diverifikasi".

---

## 12. GIT LOG (20 TERAKHIR)

```text
bbd3802 fix: resolve paths relative to executable directory instead of CWD
22229bd release: v2.1.0 core stability, avplayer watchdog, and crash reporting
b648a24 chore: bump launcher UI version to v2.1.0
cf2e0e3 fix(shader): eliminate immediate InverseBallot for quad leaders and general masks
73078e5 fix(font): bounds check prevents stack canary crash
e80dfd8 Hotfix v2.0.1: Fixed RCAS slider coordinates, UI overlap, and Performance Mode logic
b559aaf docs: use high-level results-focused v2.0 release notes
de6d51e Docs: Move internal docs to /docs folder, clean README, and rebuild clean release ZIP
773feb8 docs: finalize v2.0 release notes
afd4118 Docs: Format markdown files and update release notes for v2.0
285ef72 docs: update v2.0 release notes with visual quality overhaul
c5ca9b7 docs: add v2.0 release notes markdown
307ef5b Release v2.0: Premium Samurai UI, Zero-Stutter FPS Unlocker, and Watchdog
ad0b62e docs: remove building-from-source section
8ea4705 docs: add clear installation guide (emphasize sce_module & folder selection)
55e9d62 feat(coop): v1.8 - Local 2-Player Support & Auto-Join controllers
932382d fix(launcher): add auto-repair UI and fix sprx linking order for missing audio modules
f93eb53 fix(stability): resolve audio port race condition, input deadlock, and SEH for secondary threads
ab47c23 chore(release): update checksums, version metadata, and packaging pipeline for v1.5
af27af0 feat(v1.5): priority tuning + crash reporter + packaging
```

**Tag**: `v2.0`, `v1.8`, `v1.5`, `v1.0-update1`. Tidak ada tag `v2.1.0` (rilis ada di ZIP + `VERSION.txt`).

---

## 13. WORKSPACE INVENTORY

| Path | Isi | Ukuran |
|---|---|---|
| `extracted_game/` | Dump PS4 `app0` (eboot, sce_module, nativePS4) | 27,6 GB (8.352 file) |
| `gpu/` | shadPS4 core, shim, third_party, patches | 57,6 MB (1.791 file) |
| `src/` | Runtime native, HLE, probe, crash reporter | 0,8 MB (36 file) |
| `user/` | Log, save, sys_modules, trophy | 1.113,5 MB (10.392 file) |
| `out/` | Build output, `boot-linked.bin`, `patches.bin`, cache | 225,8 MB (454 file) |
| `dist/` | `Basara4_Launcher.exe` hasil PyInstaller | 30,4 MB |
| `docs/` | Riset, changelog, laporan QA, TODO | 0,3 MB (34 file) |
| `tests/` | Test runtime/pad/sema/content/net | 0,2 MB (31 file) |
| `crashes/` | Laporan crash + bundle ZIP (banyak simulasi) | ukuran tidak dihitung total |

**Catatan struktur**: Workspace ini **tidak** memakai layout `00_GAME_DUMP/01_REPOS/02_PROJECT/03_BUILD`; semua ada di root. ZIP rilis: `Basara4_Sumeragi_PC_v2.1.0.zip` (86.516.689 byte / 82,5 MiB), `v2.0.3` (85,6 MB), `v2.0` (85,6 MB). `CHECKSUMS.txt` berisi 116 entri.

---

## 14. PREFERENSI USER & GAYA KOMUNIKASI (PENTING)

- **Gaya jawaban**: Terstruktur, tabel, checklist; hindari paragraf panjang. Hemat token.
- **Otonomi**: Semi-autonomous — boleh scan/baca/build; **STOP** sebelum edit source atau commit.
- **Bahasa**: Bahasa Indonesia; istilah teknis boleh English.
- **Kejujuran**: Jangan fabrikasi. Kalau tidak ada bukti, tulis "belum diverifikasi" atau "tidak ada log".
- **Format prompt untuk agent lain**: `# TASK: ... ## ROLE ... ## ATURAN ... ## TASK LIST ... ## LAPORAN`.
- **Sikap**: Langsung ke inti, akui kalau tidak tahu, laporkan inconsistency (jangan pilih satu sisi).
- **Saat ini**: User mengaktifkan skill `ponytail` (perubahan最小) dan `caveman ultra` (jawaban chat sangat ringkas). Artefak file tetap ditulis normal.

---

## 15. ENVIRONMENT KHUSUS (DI LUAR GIT)

| Item | Value | Kenapa |
|---|---|---|
| OS | Windows 11 Build 10.0.26200 x64 | Target build/test |
| CPU | Intel Family 6 Model 158 | Host test |
| RAM | 16 GB (17.097.392.128 byte) | Game butuh memori guest besar |
| GPU | NVIDIA RTX 3060 12 GB, driver 617.42, Vulkan 1.4.351 | Target renderer |
| Display | PHL 272M8 1920x1080 | Output test |
| Pagefile | 9.330 MB allocated, 1.415 MB terpakai | Cegah error 1455 saat commit charge tinggi |
| `VULKAN_SDK` | `F:\Vulkanskd` | Header, loader, glslang |
| MSYS2 | `F:\msys64\clang64` | Toolchain build resmi |
| Python | 3.12.10 | Launcher, packaging, crash reporter |
| Game dir aktif | `basara.ini` → `extracted_game\app0` | Sumber dump PS4 |
| Ghidra | tidak ada | Tidak dipakai untuk alur build saat ini |

---

## 16. CONTOH PROMPT UNTUK AI BARU

- **Lanjut fix blocker #1**:
  > "Baca HANDOFF. Fokus blocker #1 (`sceAvPlayerDisableStream`). Baca `avplayer.cpp:203` dan `avplayer_source.*`, jelaskan state machine stream, lalu kasih langkah konkret. Jangan edit source dulu; tunjukkan file+baris."
- **Review kode**:
  > "Baca HANDOFF. Review `gpu/shadps4/core/libraries/avplayer/avplayer_source.cpp` bagian watchdog dan teardown. Ada race, deadlock, atau salah klaim timeout? Jangan edit, laporkan saja."
- **Validasi rilis**:
  > "Baca HANDOFF. Susun test plan v2.1.1: 5 cutscene, Stage Select, Roulette, 5 menit gameplay, co-op. Tentukan log yang harus dicek dan kriteria lulus/gagal."
- **Update dokumen**:
  > "Baca HANDOFF. Bandingkan `docs/CHANGELOG_v2.1.1_CUTSCENE_FIXES.md`, `docs/CUTSCENE_FREEZE_FIX_COMPLETION.md`, dan kode HEAD. Buat daftar klaim yang tidak cocok; jangan edit dulu."
