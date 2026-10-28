# Sengoku Basara 4 Sumeragi — PC Native Port (`basara_pc`)

> ⚠️ **BARU DI SINI?** Baca [Panduan Instalasi (INSTALL.md)](./INSTALL.md) dulu agar tidak gagal paham soal file `eboot.bin` dan `sce_module`!
>
> **Penting:** Pilih **folder game PS4 lengkap** (`eboot.bin` + `sce_module` + `sce_sys` + data game), bukan hanya file `eboot.bin`.

<p align="center">
  <img src="packaging/windows/icons/basara4.ico" alt="Logo Sengoku Basara 4" width="128" height="128" />
</p>

<p align="center">
  <a href="https://microsoft.com/windows"><img src="https://img.shields.io/badge/Platform-Windows%2010%201809+%20/%2011%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" /></a>
  <a href="https://www.vulkan.org"><img src="https://img.shields.io/badge/API-Vulkan%201.3+-E42528?style=for-the-badge&logo=vulkan&logoColor=white" alt="Vulkan API" /></a>
  <a href="https://en.wikipedia.org/wiki/X86-64"><img src="https://img.shields.io/badge/Arsitektur-x86__64%20Native%20Runtime-4B32C3?style=for-the-badge" alt="Arsitektur" /></a>
  <a href="https://visualstudio.microsoft.com"><img src="https://img.shields.io/badge/Dependensi-VC++%202015--2022%20x64-5C2D91?style=for-the-badge" alt="VC++ Redist" /></a>
  <a href="../../releases"><img src="https://img.shields.io/badge/Rilis-v2.0-10B981?style=for-the-badge" alt="Rilis" /></a>
</p>

<p align="center">
  <b>Eksekusi Native x86_64 PC & Engine Presentasi Vulkan 1.3</b><br>
  <i>Baca dalam: <a href="README.md">English</a></i>
</p>

Runtime PC native berkinerja tinggi dan engine grafis Vulkan untuk **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)**, menghadirkan aksi hack-and-slash legendaris Capcom secara native ke PC modern dengan latensi ultra-rendah, framerate tanpa batas, resolusi tinggi, dan kenyamanan stik controller modern.

---

## Fitur Utama

- **Eksekusi Native x86_64**: Berjalan langsung pada CPU Windows 64-bit modern tanpa overhead mesin virtual atau emulator lambat.
- **Engine Grafis Vulkan 1.3**: Pipeline grafis modern dengan konsumsi resource rendah dan manajemen swapchain mandiri.
- **Framerate Terbuka (120+ FPS)**: Present mode dinamis (`eImmediate` / `eMailbox`) membuka batas 60 Hz, sementara target tetap (60/90/120/144 FPS) berjalan presisi dengan frame pacing FIFO.
- **Kualitas Visual Tinggi**: Fitur supersampling render scale (1.0x hingga 2.0x), ketajaman adaptif AMD RCAS, dan Anisotropic Filtering hingga 16x.
- **Launcher Premium Samurai**: Tampilan antarmuka satu jendela bertema Crimson & Gold dengan pengaturan grafis terintegrasi dan tooltip interaktif.
- **Optimalisasi Multi-Thread Co-op**: Prioritas thread render dan audio dinaikkan agar tidak terjadi frame drop saat pertempuran split-screen 2 pemain.
- **Pemulihan Otomatis Cutscene**: Timer watchdog 3 detik otomatis mendeteksi dan melewati cutscene yang macet tanpa softlock.

---

## Quick Start (5 Langkah — Kurang dari 10 Menit)

### 1. Unduh & Ekstrak

Dapatkan **v2.0 atau lebih baru** dari tab [Releases](../../releases):
- **Portable ZIP:** `Basara4_Sumeragi_PC_v2.0.zip` (Ekstrak ke folder biasa seperti `D:\Games\Basara4_Sumeragi_PC`; jangan jalankan dari dalam ZIP dan jangan di `Program Files`).

### 2. Buka Launcher

Buka **`Basara4_Launcher.exe`**.
- Engine otomatis mengecek **Vulkan 1.3 loader**, **VC++ Redist 2015–2022 x64**, **Versi Windows**, dan **Kapasitas Penyimpanan**.
- Jika dependensi belum terpasang, tombol unduh resmi langsung disediakan dalam 1 klik.

### 3. Klik Setup Wizard

Buka **Wizard 5 Langkah** (ikon tongkat sihir ⚡), baca peringatan fair-use, lalu centang persetujuan legal.

### 4. Pilih FOLDER Game PS4 (Bukan `eboot.bin`)

Pilih folder yang **langsung berisi**:
- `eboot.bin`
- `sce_module` (modul audio/sistem — **wajib**)
- `sce_sys` (`param.sfo`, icon)
- `nativePS4` (atau `data`) — aset game

**Jangan** memilih file `eboot.bin` saja. Wizard akan menolak folder tanpa `sce_module` karena itulah penyebab suara kresek dan crash.

### 5. Tunggu Auto-Build, lalu PLAY

Wizard akan melakukan linking modul dan membuat `out/boot-linked.bin` dalam 15–30 detik. Setelah muncul **Setup Completed**, klik **⚔️ Play Now** (atau **Back to Launcher** → **INITIALIZE & PLAY**).

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
- **Solusi:** Unduh dan pasang runtime resmi dari [LunarG Vulkan SDK / Runtime](https://vulkan.lunarg.com/sdk/home#windows), atau perbarui driver GPU ke versi terbaru.

### 2. "Microsoft Visual C++ Redistributable Missing"
- **Penyebab:** Library runtime MSVC 14.0 x64 belum terpasang (`vcruntime140.dll` / `msvcp140.dll`).
- **Solusi:** Pasang [Microsoft Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).

### 3. Suara Kresek / Putus-Putus atau `sce_module` Hilang
- **Penyebab:** Folder game yang dipilih tidak memiliki `sce_module`, sehingga modul audio native tidak ikut ter-link.
- **Solusi:** Klik **🔧 REPAIR & PLAY** di launcher, lalu pilih **folder game PS4 lengkap** (bukan `eboot.bin`). Lihat [INSTALL.md](INSTALL.md).

### 4. Game Crash saat Mulai atau Masuk Stage
- Periksa file log di `user/logs/basara.log` dan crash dump di `user/crashes/` (`crash_raw_*.log`).
- Telemetri diagnostik bersifat privat dan aman (identitas pengguna disensor otomatis). Lihat [PRIVACY.md](PRIVACY.md).
- Jika hanya menyalin `eboot.bin`, jalankan ulang Setup Wizard dan pilih folder game lengkap.

### 5. Controller Tidak Terdeteksi
- Stik XInput (Xbox, PS4/PS5 via DS4Windows/Steam) didukung secara native.
- Untuk controller generic DirectInput, klik **🎮 Gamepad** di launcher untuk membuka pemetaan tombol.

---

## Pengaturan Grafis & Kinerja (`basara.ini`)

Pengaturan dapat disesuaikan langsung lewat Launcher atau file konfigurasi `basara.ini`:

```ini
# Resolusi tampilan jendela
output_res=1920x1080         # 1280x720 | 1920x1080 | 2560x1440 | 3840x2160

# Pengali resolusi render internal (supersampling)
render_scale=1.0             # 1.0 (asli) | 1.5 (supersampling) | 2.0 (sangat tajam)

# Filter tekstur sudut
anisotropy=16                # 0 (mati) | 2 | 4 | 8 | 16 (disarankan)

# Ketajaman AMD RCAS
rcas=1                       # 0 (mati) | 1 (nyala)
rcas_strength=75             # 0 (lembut) sampai 100 (tajam)

# Batas framerate
fps_limit=144                # 60 | 90 | 120 | 144 | 240 | 0 (unlimited)

# Prioritas CPU
process_priority=above_normal # normal | above_normal | high
```

---

## Lisensi Sumber Terbuka & Kepatuhan

- **Lisensi Proyek:** [MIT License](LICENSE.txt)
- **Komponen Pihak Ketiga:** [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) (mencakup shadps4 GPL-2.0, LibAtrac9 MIT, SDL3 Zlib, Vulkan SDK Apache-2.0, AMD FidelityFX MIT, miniz MIT, Sirit BSD-2, xbyak BSD-3, Boost BSL-1.0).
- **Kebijakan Privasi & Telemetri:** [PRIVACY.md](PRIVACY.md)
- **Catatan Rilis:** [CHANGELOG.md](CHANGELOG.md)

---

## Penafian (Disclaimer)

*Sengoku Basara (戦国BASARA)* dan *Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)* adalah merek dagang terdaftar milik **CAPCOM CO., LTD.** Proyek ini adalah inisiatif pelestarian independen open source tanpa afiliasi komersial.
