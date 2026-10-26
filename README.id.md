# Sengoku Basara 4 Sumeragi — PC Native Port (`basara_pc`)

> ⚠️ **BARU DI SINI?** Baca [Panduan Instalasi (INSTALL.md)](./INSTALL.md) dulu agar tidak gagal paham soal file `eboot.bin` dan `sce_module`!
>
> **Penting:** pilih **folder game PS4 lengkap** (`eboot.bin` + `sce_module` + `sce_sys` + data game), bukan hanya file `eboot.bin`.

<p align="center">
  <img src="packaging/windows/icons/basara4.ico" alt="Logo Sengoku Basara 4" width="128" height="128" />
</p>

<p align="center">
  <a href="https://microsoft.com/windows"><img src="https://img.shields.io/badge/Platform-Windows%2010%201809+%20/%2011%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" /></a>
  <a href="https://www.vulkan.org"><img src="https://img.shields.io/badge/API-Vulkan%201.3+-E42528?style=for-the-badge&logo=vulkan&logoColor=white" alt="Vulkan API" /></a>
  <a href="https://en.wikipedia.org/wiki/X86-64"><img src="https://img.shields.io/badge/Arsitektur-x86__64%20Native%20Runtime-4B32C3?style=for-the-badge" alt="Arsitektur" /></a>
  <a href="https://visualstudio.microsoft.com"><img src="https://img.shields.io/badge/Dependensi-VC++%202015--2022%20x64-5C2D91?style=for-the-badge" alt="VC++ Redist" /></a>
  <a href="../../releases"><img src="https://img.shields.io/badge/Rilis-v1.8-10B981?style=for-the-badge" alt="Rilis" /></a>
</p>

<p align="center">
  <b>Eksekusi Native x86_64 PC & Engine Presentasi Vulkan 1.3</b><br>
  <i>Baca dalam: <a href="README.md">English</a></i>
</p>

Runtime PC native berkinerja tinggi dan engine grafis Vulkan untuk **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)**, menghadirkan aksi hack-and-slash legendaris Capcom secara native ke PC modern dengan latensi ultra-rendah, framerate tanpa batas, resolusi tinggi, dan kenyamanan stik controller modern.

---

## Quick Start (5 Langkah — Kurang dari 10 Menit)

### 1. Unduh & Ekstrak
Dapatkan **v1.8 atau lebih baru** dari tab [Releases](../../releases):
- **Installer (Direkomendasikan):** `Basara4_Sumeragi_PC_Setup_v<version>.exe` (Pemasangan per-user tanpa hak administrator, membuat pintasan Start Menu & Desktop, data user tetap aman saat uninstall).
- **Portable ZIP:** `Basara4_Sumeragi_PC_v<version>.zip` (Ekstrak ke folder biasa seperti `D:\Games\Basara4_Sumeragi_PC`, jangan di dalam ZIP dan jangan di `Program Files`).

### 2. Buka Launcher
Buka **`Basara4_Launcher.exe`**.
- Engine otomatis mengecek **Vulkan 1.3 loader**, **VC++ Redist 2015–2022 x64**, **Versi Windows**, dan **Kapasitas Penyimpanan**.
- Jika dependensi belum terpasang, tombol unduh resmi langsung disediakan dalam 1 klik.

### 3. Klik Setup Wizard
Buka **Wizard 5 Langkah** (ikon tongkat sihir ⚡), baca peringatan fair-use, lalu centang persetujuan legal.

### 4. Pilih FOLDER Game PS4 (Bukan `eboot.bin`)
**Ini langkah yang paling sering salah.** Pilih folder yang **langsung berisi**:
- `eboot.bin`
- `sce_module` (modul audio/sistem — **wajib**)
- `sce_sys` (`param.sfo`, icon)
- `nativePS4` (atau `data`) — aset game

**Jangan** memilih file `eboot.bin` saja. Wizard akan menolak folder tanpa `sce_module` karena itulah penyebab suara kresek dan crash.

### 5. Tunggu Auto-Build, lalu PLAY
Wizard akan melakukan linking modul dan membuat `out/boot-linked.bin` dalam 15–30 detik. Setelah muncul **Setup Completed**, klik **⚔️ Play Now** (atau **Back to Launcher** → **PLAY GAME**).

> 📖 Butuh contoh folder dan solusi masalah? Baca panduan lengkap **[Panduan Instalasi (INSTALL.md)](./INSTALL.md)**.

---

## Panduan Legal Dump

> [!IMPORTANT]
> **Tidak ada aset berhak cipta Capcom, citra disc (ISO/dump), file biner game, atau kunci enkripsi yang disertakan dalam perangkat lunak ini.**
> 
> Kamu wajib melakukan dump **seluruh folder game** dari PS4 milikmu sendiri: `eboot.bin`, `sce_module`, `sce_sys`, dan data game (`nativePS4` atau `data`). Kalau hanya mengambil `eboot.bin`, modul audio akan hilang, suara kresek, atau game crash. Cari tutorial dumping di komunitas homebrew PS4.

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

### 3. Suara Kresek / Putus-Putus atau `sce_module` Hilang
- **Penyebab:** folder game yang dipilih tidak memiliki `sce_module`, sehingga modul audio native seperti `libSceNgs2.sprx` dan `libSceAjm.sprx` tidak ikut ter-link.
- **Solusi:** Klik **🔧 REPAIR & PLAY** di launcher, lalu pilih **folder game PS4 lengkap** (bukan `eboot.bin`). Lihat [INSTALL.md](INSTALL.md#-troubleshooting-solusi-masalah).

### 4. Game Crash saat Mulai atau Masuk Stage
- Periksa file log di `user/logs/basara.log` dan crash dump di `user/crashes/` (`crash_raw_*.log`).
- Telemetri diagnostik bersifat aman (privasi terjamin, identitas pribadi seperti username dan IP lokal disensor otomatis). Lihat [PRIVACY.md](PRIVACY.md).
- Kalau kamu hanya menyalin `eboot.bin`, jalankan ulang Setup Wizard dan pilih folder game lengkap (`eboot.bin` + `sce_module` + `sce_sys` + data game).

### 5. Controller Tidak Terdeteksi
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
| `game_dir` | *(otomatis)* | Folder game PS4 lengkap yang dipilih di Setup Wizard. Dipakai langsung — jangan pindahkan folder setelah setup. |

---

## Lisensi Perangkat Lunak & Legalitas

- **Lisensi Proyek:** [MIT License](LICENSE.txt)
- **Komponen Pihak Ketiga:** [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) (mencakup shadps4 GPL-2.0, LibAtrac9 MIT, SDL3 Zlib, Vulkan SDK Apache-2.0, AMD FidelityFX MIT, miniz MIT, Sirit BSD-2, xbyak BSD-3, Boost BSL-1.0).
- **Kebijakan Privasi & Telemetri:** [PRIVACY.md](PRIVACY.md)
- **Catatan Rilis:** [CHANGELOG.md](CHANGELOG.md)

---

## Pernyataan Penyangkalan (Disclaimer)

*Sengoku Basara (戦国BASARA)* dan *Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)* adalah merek dagang terdaftar milik **CAPCOM CO., LTD.** Proyek ini adalah inisiatif pelestarian independen berbasis sumber terbuka. Tidak ada pelanggaran hak cipta yang dimaksudkan.
