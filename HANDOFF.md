# HANDOFF: Sengoku Basara 4 Sumeragi PC Native Port — 2026-11-18

> **Instruksi untuk AI yang menerima dokumen ini**:  
> Kamu adalah asisten yang membantu user melanjutkan proyek porting game.  
> Baca seluruh dokumen ini dulu. Kalau ada data yang tidak jelas, tanya user — jangan tebak.

---

## 1. IDENTITAS PROYEK

| Field | Value |
|---|---|
| Nama Proyek | Sengoku Basara 4 Sumeragi PC Native Port (`basara_pc`) |
| Game / Serial | Sengoku Basara 4 Sumeragi / `CUSA01159` (Game Update v1.02) |
| Region / Platform | JP / PS4 (Capcom MT Framework Engine) |
| Metode | Runtime HLE + Native x86-64 Execution + Vulkan Renderer (shadPS4 base) |
| Workspace | `F:\Project Porting Game PS4\Basara 4 Sumeragi v2.0-Perf` |
| GitHub | https://github.com/krixsan/Basara-4-Sumeragi-Native-PC |
| Versi Rilis Saat Ini | `v2.1.2` |

---

## 2. STATUS MILESTONE

| Milestone | Status | Catatan |
|---|---|---|
| M0 — Foundation | ✅ Selesai | Arsitektur HLE hybrid + Vulkan swapchain terbukti jalan |
| M1 — Runtime/HLE | ✅ Selesai | Guest x86-64 boot ke `0x9c3c60`, dynamic relocations, memory mapping 6GB flex |
| M2 — Renderer | ✅ Selesai | Vulkan 1.4 pipeline, FSR 1.0 upscaling, 60 FPS swapchain stabil |
| M3 — Systems | ✅ Selesai | Audio WASAPI stereo 48kHz, XInput Gamepad, SaveData, PS4 DLC 56 add-ons |
| M4 — Stability | ✅ Selesai | Crash thread spawning `pthread_create: 11` teratasi, cutscene `op_01.mp4` lolos |
| M5 — Release & Polish | ✅ Selesai v2.1.2 | i18n 7-bahasa, Auto-Optimize, embedded modules, DLC fix, release live |

**Commit terakhir**: `a49e39b` — `fix(dlc): embed content_profile directly for PyInstaller bundle`  
**Tag rilis**: `v2.1.2` — https://github.com/krixsan/Basara-4-Sumeragi-Native-PC/releases/tag/v2.1.2

---

## 3. APA YANG SUDAH TERBUKTI BERJALAN

1. ✅ **Boot & 3D Title Screen** — Game boot mulus, DLC dialog dismiss otomatis, logo Capcom muncul, Title Screen 3D 60 FPS.
2. ✅ **Vulkan Renderer & FSR 1.0** — Swapchain 110M+ flips tanpa memory leak. FSR 1.0 aktif (`fsr_pass.cpp`).
3. ✅ **Thread Management Anti-Crash** — Bebas dari `STOP: host pthread_create failed: 11` berkat `MAX_ACTIVE_THREADS = 128`, fallback stack retry, graceful `EAGAIN` ke MT Framework.
4. ✅ **PS4 DLC (56 Add-ons)** — 30 kostum karakter, 24 BGM, 2 unlock keys via `content.bin`, dynamic VFS mount, in-memory caching O(1) di `src/runtime_content.c`.
5. ✅ **Live Trainer / Cheats v1.02** — 12 patch cheat & 6 code caves (Infinite Health, Infinite Basara, Gold 9.99M, Weapon/Growth Points).
6. ✅ **Automated DLC Installer** — Tombol GUI "📦 Install DLC" scan `.dlcp`, link ke VFS, generate `content.bin`.
7. ✅ **Launcher EXE** — `Basara4_Launcher.exe` (30.71 MB), semua modul Python embedded via PyInstaller, tidak butuh Python terinstall.
8. ✅ **i18n 7 Bahasa** — ID, EN, JP, CN, KR, FR, DE di launcher + in-game overlay.
9. ✅ **Auto-Optimize** — Deteksi GPU, set preset performa otomatis saat first run.

---

## 4. PERUBAHAN SESI INI (2026-11-18)

### Fix DLC Install Error (KRITIS)
**Error**: `Script content_profile.py tidak ditemukan di tools/ atau scripts/`  
**Root cause**: `tools/content_profile.py` adalah wrapper yang coba baca `scripts/` via filesystem — tidak valid di dalam PyInstaller exe.  
**Fix**:
- Copy `scripts/content_profile.py` ke root project (tidak di-commit ke git, ada di `.gitignore`)
- Tambah `--paths .` dan `--paths launcher` di `build_launcher.py`
- Rebuild `Basara4_Launcher.exe` → PyInstaller embed file asli
- Repackage ZIP → upload ulang ke release v2.1.2

### Commits Sesi Ini
```
a49e39b fix(dlc): embed content_profile directly for PyInstaller bundle
8408d98 docs: simplify v2.1.2 release notes
33a26a2 feat(v2.1.2): i18n 7-language support, Auto-Optimize, embedded modules & DLC fix
```

---

## 5. PERUBAHAN GRAFIS / GPU (HISTORY LENGKAP)

| Kategori | Perubahan | Commit |
|---|---|---|
| FSR 1.0 Upscaling | AMD FidelityFX Super Resolution 1.0 untuk resolusi lebih tinggi | `14e347e` |
| Zero-Stutter Pipeline | Shader pre-compile dari `shaders/recipe.zip` saat startup | `33a26a2` |
| Graceful Pipeline Skip | Shader/pipeline ditolak driver → log `PIPELINE FAILED`, skip draw (tidak crash) | `33a26a2` |
| Draw Call Optimization | Fast path draw calls berurutan state sama, bypass LRU cache memcmp | `33a26a2` |
| VRAM Management | Staging buffer pool ring idle frame tuning, kurangi CPU↔GPU stall saat DLC aktif | `33a26a2` |
| Shader Fix | InverseBallot quad leaders shader recompiler fix | `cf2e0e3` |
| Font/Text Fix | Bounds check text parser (fix crash Stage Select) | `73078e5` |
| Performance Mode | FPS unlocker 80+ FPS, RCAS sharpening filter | `ede32bb` |
| In-Game Overlay | 7-bahasa di settings menu overlay (bbport) | `33a26a2` |
| Low-Latency Presenter | Vulkan presenter improvements | `33a26a2` |
| Swapchain Stability | Swapchain robustness improvements | `33a26a2` |

---

## 6. BLOCKER SAAT INI

### Blocker #1 — GPU Device Lost / Timeout (Sesi > 2 Jam)
- **Gejala**: Crash `STOP: GPU library assertion failed` setelah 110M+ draw commands
- **Root cause**: Pipeline shader timeout submission di driver NVIDIA saat transisi cutscene panjang + `async_pipelines = 0` di `basara.ini`
- **File**: `basara.ini:41`, `gpu/shadps4/video_core/renderer_vulkan/vk_semaphore.cpp:77`
- **Rencana Fix**:
  1. Set `async_pipelines = 1` di `basara.ini`
  2. Tambah watchdog timeout guard di semaphore wait presenter

---

## 7. NEXT STEP (PRIORITAS)

| # | Task | File | Estimasi |
|---|---|---|---|
| 1 | Aktifkan `async_pipelines = 1` di basara.ini | `basara.ini` | 2 menit |
| 2 | Test gameplay stage penuh dengan cheat aktif | — | 30 menit |
| 3 | Bersihkan file `.bak_*` yang menumpuk | root + subfolder | 5 menit |
| 4 | (Opsional) SMAA / FXAA — file shader sudah ada tapi belum aktif | `gpu/shadps4/video_core/host_shaders/fxaa.comp`, `smaa.comp` | — |
| 5 | (Opsional) Low-latency mode via `vk_low_latency.cpp/.h` (file ada, belum di-hook) | `vk_low_latency.cpp` | — |

---

## 8. FILE YANG TIDAK BOLEH DIEDIT

| File | Alasan |
|---|---|
| `avplayer_state.cpp` | State machine avplayer — sensitif, sudah stabil |
| `avplayer_source.cpp` | Source demuxer — sudah fine-tuned, jangan sentuh |
| `runtime_memory.c` | Memory allocator — ubah → crash langsung |
| `gpu/CMakeLists.txt` | Build system GPU — konfigurasi sensitif |

---

## 9. ATURAN WAJIB AI PENERIMA

```
✅ Backup sebelum edit  : Copy-Item $file "$file.bak_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
✅ Safety check commit  : git status --short | Select-String "extracted_game|DLC"
✅ JANGAN git add .     : extracted_game = 29.7 GB harus tetap di luar repo
✅ Build gagal 3x       : STOP dan tanya user
✅ Edit source C/C++    : STOP dan review dulu bersama user
✅ Bahasa               : Indonesia, fallback English untuk istilah teknis
✅ 7-bahasa sync        : Jika tambah tr() key baru, update semua 7 bahasa sekaligus
✅ Sync DLC files       : basara4_dlc.py (root) selalu sync dari launcher/basara4_dlc.py
```

---

## 10. CARA RESUME PROYEK

Kalau user bilang **"lanjut"**, AI harus:
1. **Print ringkasan**: Proyek, Milestone, Blocker, Next Step
2. **Tanya user**: "Lanjut dari mana? (a) fix blocker, (b) lihat file tertentu, (c) lain?"
3. **Eksekusi** sesuai aturan di atas

---

## 11. ENVIRONMENT LOKAL (TIDAK DI GIT)

| Item | Value |
|---|---|
| `VULKAN_SDK` | `F:\Vulkanskd` |
| MSYS2 Clang64 | `F:\msys64\clang64\bin` (Clang 23 + Ninja) |
| Python Runtime | Python 3.12 (Windows) — untuk build launcher |
| Driver GPU | NVIDIA 617.42 (RTX 3060 12GB), Vulkan 1.4 |
| Host Memory | Total virtual 19.3 GB — game butuh commit 6 GB |
| `content_profile.py` | Di root (copy dari `scripts/`) — tidak di-commit, butuh untuk build launcher |

---

## 12. WORKSPACE INVENTORY

| Path | Isi | Ukuran |
|---|---|---|
| `extracted_game/` | Dump game (eboot.bin + app0 assets) | 29.73 GB |
| `DLC/` | Ekstrak package DLC PS4 (54 add-ons) | 2.90 GB |
| `out/` | Build output binary & pipeline cache | 226 MB |
| `gpu/` | Vulkan renderer & shadPS4 fork | 58.5 MB |
| `src/` | Custom runtime HLE | 1.4 MB |
| `tools/` | Python tools, trainer, live watcher | 32.6 MB |
| `user/` | Save data, logs, shader cache | 1.19 GB |
| `dist/` | Release ZIP & CHECKSUMS | ~86 MB |

---

## 13. FILE BARU YANG BELUM AKTIF (PEKERJAAN BERIKUTNYA)

| File | Keterangan | Status |
|---|---|---|
| `gpu/shadps4/video_core/host_shaders/fxaa.comp` | FXAA anti-aliasing shader | Ada, belum di-hook |
| `gpu/shadps4/video_core/host_shaders/smaa.comp` | SMAA anti-aliasing shader | Ada, belum di-hook |
| `gpu/shadps4/video_core/renderer_vulkan/host_passes/aa_pass.cpp/.h` | AA pass infrastructure | Ada, belum aktif |
| `gpu/shadps4/video_core/renderer_vulkan/vk_low_latency.cpp/.h` | NVIDIA Reflex / low-latency | Ada, belum di-hook |
| `gpu/shadps4/video_core/renderer_vulkan/vk_checkpoints.cpp/.h` | GPU checkpoint debug | Ada, dev only |

---

## 14. GIT LOG (10 TERAKHIR)

```
a49e39b fix(dlc): embed content_profile directly for PyInstaller bundle
8408d98 docs: simplify v2.1.2 release notes
33a26a2 feat(v2.1.2): i18n 7-language support, Auto-Optimize, embedded modules & DLC fix
a5205a8 feat(cheats): implement force-max & zero-damage HP caves and infinite basara/boost gauge for v1.02
25c4f26 fix(cheats): implement infinite health zero-damage code cave at 0x106F660
518e480 feat(probe): add verbose live debug patch verification logging
28be02b fix(cheats): verified v1.02 cheat offsets, inline 9.99M gold and live trainer injection
1b914eb feat(tools): add live memory watcher for real-time cheat verification
cf12a96 feat(cheats): add infinite health patch and dual growth points sites
31d5136 feat(tools): add automated cheat scanner and AOB trainer generator
```

---

## 15. PREFERENSI USER

- **Format**: Tabel, checklist, terstruktur — bukan paragraf panjang
- **Otonomi**: Semi-autonomous (boleh eksekusi read/build/scan; STOP jika butuh edit source)
- **Bahasa**: Indonesia, fallback English untuk istilah teknis
- **Sikap**: Jujur, langsung ke inti, akui jika tidak tahu
- **Release notes**: Simple, tidak menyebut nama file internal (bbport, vk_*, dll.)
