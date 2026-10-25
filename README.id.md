# Sengoku Basara 4 Sumeragi — PC Native Port (`basara_pc`)

<p align="center">
  <img src="packaging/windows/icons/basara4.ico" alt="Logo Sengoku Basara 4" width="128" height="128" />
</p>

<p align="center">
  <a href="https://microsoft.com/windows"><img src="https://img.shields.io/badge/Platform-Windows%2010%201809+%20/%2011%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" /></a>
  <a href="https://www.vulkan.org"><img src="https://img.shields.io/badge/API-Vulkan%201.3+-E42528?style=for-the-badge&logo=vulkan&logoColor=white" alt="Vulkan API" /></a>
  <a href="https://en.wikipedia.org/wiki/X86-64"><img src="https://img.shields.io/badge/Arsitektur-x86__64%20Native%20Runtime-4B32C3?style=for-the-badge" alt="Arsitektur" /></a>
  <a href="https://visualstudio.microsoft.com"><img src="https://img.shields.io/badge/Dependensi-VC++%202015--2022%20x64-5C2D91?style=for-the-badge" alt="VC++ Redist" /></a>
  <a href="../../releases"><img src="https://img.shields.io/badge/Rilis-Update%203-10B981?style=for-the-badge" alt="Rilis" /></a>
</p>

<p align="center">
  <b>Eksekusi Native x86_64 PC & Engine Presentasi Vulkan 1.3</b><br>
  <i>Baca dalam: <a href="README.md">English</a></i>
</p>

Runtime PC native berkinerja tinggi dan engine grafis Vulkan untuk **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)**, menghadirkan aksi hack-and-slash legendaris Capcom secara native ke PC modern dengan latensi ultra-rendah, framerate tanpa batas, resolusi tinggi, dan kenyamanan stik controller modern.

---

## Quick Start (3 Langkah — Kurang dari 5 Menit)

### 1. Unduh (Download)
Dapatkan paket rilis terbaru dari tab [Releases](../../releases):
- **Installer (Direkomendasikan):** `Basara4_Sumeragi_PC_Setup_v<version>.exe` (Pemasangan per-user tanpa hak administrator, membuat pintasan Start Menu & Desktop, data user tetap aman saat uninstall).
- **Portable ZIP:** `Basara4_Sumeragi_PC_v<version>.zip` (Ekstrak ke folder mana saja).

### 2. Jalankan Launcher
Buka **`Basara4_Launcher.exe`**.
- Engine otomatis mengecek **Vulkan 1.3 loader**, **VC++ Redist 2015–2022 x64**, **Versi Windows**, dan **Kapasitas Penyimpanan**.
- Jika dependensi belum terpasang, tombol unduh resmi langsung disediakan dalam 1 klik.

### 3. Setup Wizard & Mainkan
Pada pemasangan baru, **Wizard 5 Langkah** akan muncul secara otomatis:
1. Konfirmasi persetujuan legal fair-use.
2. Pilih file `eboot.bin` hasil dump legal (format SELF terdekripsi dan ELF standar didukung penuh).
3. Wizard akan melakukan linking modul dan membangun `out/boot-linked.bin` dalam hitungan detik.
4. Klik **PLAY GAME**!

---

## Panduan Legal Dump

> [!IMPORTANT]
> **Tidak ada aset berhak cipta Capcom, citra disc (ISO/dump), file biner game, atau kunci enkripsi yang disertakan dalam perangkat lunak ini.**
> 
> You need to dump `eboot.bin` from your legally owned PS4. Search PS4 homebrew community for dumping tutorials.

---

## Persyaratan Sistem

| Komponen | Minimum | Rekomendasi |
|---|---|---|
| **OS** | Windows 10 64-bit (Build 17763 / Versi 1809+) | Windows 11 64-bit |
| **Prosesor** | 4-Core / 8-Thread x86_64 CPU | 6-Core / 12-Thread x86_64 CPU (Zen 3 / Intel Gen 12+) |
| **Memori** | 8 GB RAM | 16 GB Dual-Channel RAM |
| **Grafis** | GPU Vulkan 1.3 (GTX 1060 6GB / RX 580) | RTX 2060 / RX 6600 atau lebih tinggi |
| **Penyimpanan** | 500 MB kosong (untuk engine & cache) + Aset game | NVMe / SATA SSD |
| **Runtime** | [Vulkan Runtime 1.3+](https://vulkan.lunarg.com/sdk/home#windows) & [VC++ 2015–2022 x64](https://aka.ms/vs/17/release/vc_redist.x64.exe) | Driver GPU Terkini |

---

## Panduan Troubleshooting (Solusi Masalah)

### 1. "Vulkan Loader (vulkan-1.dll) Missing"
- **Penyebab:** Sistem Windows belum memiliki loader Vulkan Khronos.
- **Solusi:** Unduh dan pasang runtime resmi dari [LunarG Vulkan SDK / Runtime](https://vulkan.lunarg.com/sdk/home#windows), atau perbarui driver GPU NVIDIA / AMD / Intel ke versi terbaru.

### 2. "Microsoft Visual C++ Redistributable Missing"
- **Penyebab:** Library runtime MSVC 14.0 x64 belum terpasang di Windows (`vcruntime140.dll` / `msvcp140.dll`).
- **Solusi:** Pasang [Microsoft Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).

### 3. Game Crash saat Mulai atau Masuk Stage
- Periksa file log di `user/logs/basara.log` dan crash dump di `user/crashes/` (`crash_raw_*.log`).
- Telemetri diagnostik bersifat aman (privasi terjamin, identitas pribadi seperti username dan IP lokal disensor otomatis). Lihat [PRIVACY.md](PRIVACY.md).

### 4. Controller Tidak Terdeteksi
- Controller XInput (Xbox, PlayStation via DS4Windows/Steam) langsung berfungsi otomatis.
- Untuk controller generic DirectInput, klik tombol **🎮 Gamepad** di bilah alat launcher untuk membuka utilitas kalibrasi `basara4-pad-mapper.exe`.

---

## Konfigurasi (`basara.ini`)

Semua opsi tersinkronisasi otomatis antara GUI Launcher, menu in-game (`Insert` atau `L3+R3`), dan `basara.ini`:

| Parameter | Bawaan | Deskripsi |
|---|---|---|
| `output_res` | `1920x1080` | Resolusi jendela dan tampilan output |
| `render_res` | `1080` | Target resolusi rendering internal (`720`, `1080`, `1440`, `2160`) |
| `fullscreen` | `1` | `1` untuk borderless fullscreen, `0` untuk windowed |
| `fps_limit` | `144` | Batas framerate target (`60`, `90`, `120`, `144`, `240`, `0` untuk tanpa batas) |
| `anisotropy` | `16` | Tingkat filter tekstur anisotropic (`0`, `2`, `4`, `8`, `16`) |
| `fsr1` | `1` | `1` untuk mengaktifkan spatial upscaler AMD FSR 1.0 |
| `rcas` | `1` | `1` untuk mengaktifkan penajaman kontras adaptif (RCAS) |
| `process_priority` | `above_normal` | Prioritas penjadwalan thread CPU Windows (`normal`, `above_normal`, `high`) |
| `telemetry_upload` | `ask` | Perilaku pelaporan crash (`ask`, `never`, `always`) |
| `first_run_done` | `0` | Status penyelesaian setup wizard pertama |
| `legal_acknowledged`| `0` | Status persetujuan disclaimer legal fair use |

---

## Membangun dari Kode Sumber (Building from Source)

### Kebutuhan
- Windows 10 1809+ / 11 x64
- Lingkungan [MSYS2](https://www.msys2.org/) dengan `CLANG64`
- Python 3.10+ (dengan modul `pillow` dan `pyinstaller`)
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (opsional, untuk membuat setup installer)

### 1. Kompilasi Engine Utama (`basara_pc.exe`)
```bash
# Buka shell MSYS2 CLANG64:
pacman -S --needed git ninja mingw-w64-clang-x86_64-clang mingw-w64-clang-x86_64-cmake \
  mingw-w64-clang-x86_64-vulkan-headers mingw-w64-clang-x86_64-vulkan-loader \
  mingw-w64-clang-x86_64-sdl3 mingw-w64-clang-x86_64-ffmpeg mingw-w64-clang-x86_64-zydis

./win_build.sh
```

### 2. Kompilasi GUI Launcher
```powershell
python -m pip install pillow pyinstaller
python build_launcher.py
```

### 3. Pembuatan Paket Rilis & Verifikasi
```powershell
# Buat arsip ZIP portabel & checksums SHA256
python scripts/package_release.py --version 1.0-update3

# Verifikasi integritas paket rilis
python scripts/verify_release.py
```

---

## Lisensi Perangkat Lunak & Legalitas

- **Lisensi Proyek:** [MIT License](LICENSE.txt)
- **Komponen Pihak Ketiga:** [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) (mencakup shadps4 GPL-2.0, LibAtrac9 MIT, SDL3 Zlib, Vulkan SDK Apache-2.0, AMD FidelityFX MIT, miniz MIT, Sirit BSD-2, xbyak BSD-3, Boost BSL-1.0).
- **Kebijakan Privasi & Telemetri:** [PRIVACY.md](PRIVACY.md)
- **Catatan Rilis:** [CHANGELOG.md](CHANGELOG.md)

---

## Pernyataan Penyangkalan (Disclaimer)

*Sengoku Basara (戦国BASARA)* dan *Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)* adalah merek dagang terdaftar milik **CAPCOM CO., LTD.** Proyek ini adalah inisiatif pelestarian independen berbasis sumber terbuka. Tidak ada pelanggaran hak cipta yang dimaksudkan.
