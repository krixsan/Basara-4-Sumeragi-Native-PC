# Sengoku Basara 4 Sumeragi — PC Native Port (`basara_pc`)

<p align="center">
  <img src="packaging/windows/icons/basara4.ico" alt="Logo Sengoku Basara 4" width="128" height="128" />
</p>

<p align="center">
  <a href="https://microsoft.com/windows"><img src="https://img.shields.io/badge/Platform-Windows%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" /></a>
  <a href="https://www.vulkan.org"><img src="https://img.shields.io/badge/API-Vulkan%201.3-E42528?style=for-the-badge&logo=vulkan&logoColor=white" alt="Vulkan API" /></a>
  <a href="https://en.wikipedia.org/wiki/X86-64"><img src="https://img.shields.io/badge/Arsitektur-x86__64%20Native%20Runtime-4B32C3?style=for-the-badge" alt="Arsitektur" /></a>
  <a href="https://github.com/krixsan/Basara-4-Sumeragi-Native-PC"><img src="https://img.shields.io/badge/Status-Preservasi%20Aktif-D4AF37?style=for-the-badge" alt="Status" /></a>
  <a href="../../releases"><img src="https://img.shields.io/badge/Rilis-Update%202-10B981?style=for-the-badge" alt="Rilis" /></a>
</p>

<p align="center">
  <b>Eksekusi Native x86_64 PC & Engine Presentasi Vulkan 1.3</b><br>
  <i>Baca dalam: <a href="README.md">English</a></i>
</p>

Runtime PC native berkinerja tinggi dan engine grafis Vulkan untuk **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)**, menghadirkan aksi hack-and-slash legendaris Capcom secara native ke PC modern dengan latensi ultra-rendah, framerate tanpa batas, resolusi tinggi, dan dukungan penuh stik controller.

---

## Gambaran Arsitektur

Proyek ini menghadirkan arsitektur engine modular sumber terbuka yang dirancang khusus untuk eksekusi biner native tanpa beban virtualisasi sistem operasi penuh:

```
├── src/                  # Lapisan Translasi OS & Platform Native
│   ├── runtime.c         # Manajemen proses, dynamic symbol dispatch & linking
│   ├── runtime_audio.c   # Sub-engine audio multi-kanal ATRAC9 & PCM
│   ├── runtime_pad.c     # Pengalihan controller via SDL3 / XInput & custom mapping
│   ├── runtime_memory.c  # Direct memory mapping & manajemen virtual address space
│   ├── runtime_thread.c  # Jembatan threading & sinkronisasi POSIX / Orbis
│   ├── probe.c           # Relokasi memori, eboot loader & dynamic byte-patching
│   └── compat_win.c      # Abstraksi Windows Win32 API & timer presisi tinggi
│
├── gpu/                  # Subsistem Rendering Kinerja Tinggi Vulkan 1.3
│   ├── shadps4/          # Graphics command processor & manajemen memori GPU
│   ├── shader_recompiler # Penerjemah bytecode shader GPU ke SPIR-V dinamis
│   └── shim/             # Overlay performa in-game, FSR 1 / RCAS & Anisotropic filtering
│
├── third_party/          # LibAtrac9 (hardened), ImGui, FSR-Vulkan, Miniz
├── packaging/            # Ikon, manifes, dan sumber daya kompilasi
├── launcher.py           # GUI Launcher desktop profesional (PIL glassmorphism)
└── CMakeLists.txt        # Konfigurasi build modular
```

- **`src/` (Lapisan Eksekusi Native):** Menjembatani panggilan biner x86_64 ELF game langsung ke Windows Win32 / POSIX API, memetakan memori, file sistem, threading, dan input controller dengan overhead nol.
- **`gpu/` (Engine Vulkan 1.3):** Mengkompilasi ulang bytecode shader GPU PS4 menjadi SPIR-V efisiensi tinggi, menjalankan pipeline Vulkan dengan akselerasi perangkat keras, upscaling FSR 1, penajaman kontras RCAS, dan 16x Anisotropic Filtering.
- **`launcher.py` (Desktop Launcher):** Dibangun dengan arsitektur single-canvas PIL alpha-composited glassmorphism, integrasi Windows 11 dark mode title bar, selektor tombol segmen, pembuka kunci internal FPS, dan sinkronisasi instan ke `basara.ini`.

---

## Yang Baru di Update 2

- **True Internal MT Framework FPS Unlocker:**
  - Pemindaian pola byte otomatis pada limiter internal Capcom MT Framework di dalam `eboot.bin`.
  - Mendukung target 60 FPS, 90 FPS, 120 FPS, 144 FPS, 165 FPS, 240 FPS, hingga Unlimited tanpa merusak kecepatan waktu atau simulasi fisik karakter.
- **AMD FSR 1.0 + RCAS Sharpening:**
  - Upscaling AMD FidelityFX Super Resolution yang dipadukan dengan Robust Contrast Adaptive Sharpening (RCAS).
  - Gambar terlihat sangat tajam di resolusi 1440p dan 4K dengan konsumsi daya kartu grafis yang minimal.
- **16x Anisotropic Filtering:**
  - Peningkatan kualitas penyaringan tekstur anisotropic tingkat tinggi (Off, 2x, 4x, 8x, 16x) yang menghilangkan efek kabur pada permukaan lantai dan kostum di sudut miring, dengan tetap menjaga akurasi *Cascade Shadow Depth-Bias*.
- **LibAtrac9 Boundary Hardening:**
  - Penguatan batas alokasi memori pada dekoder ATRAC9 (`band_extension.c`, `huffCodes.c`, `unpack.c`) untuk mencegah crash saat memutar file audio BGM atau dialog yang rusak/terpotong.
- **Dukungan Stik & Alat Kalibrasi (`basara4-pad-mapper.exe`):**
  - Deteksi dan pembacaan otomatis file pemetaan `user/gamepad_mapping.txt` dan `gamepad_mapping.txt`.
  - Disertakan aplikasi kalibrasi mandiri `basara4-pad-mapper.exe` untuk stik generik USB / DirectInput.
- **Tangkapan Layar Lossless (Hotkey F12):**
  - Ambil tangkapan layar langsung dari frame buffer game dalam format PNG beresolusi penuh ke folder `user/screenshots/` cukup dengan menekan tombol **F12**.

---

## Fitur Utama

- **Framerate Tinggi:** Pilihan 60 FPS, 90 FPS, 120 FPS, 144 FPS, 240 FPS, hingga Uncapped.
- **Resolusi Layar Modern:** Dukungan penuh untuk 720p, 1080p, 1440p, 4K, dan rasio Ultrawide (21:9).
- **Menu Pengaturan In-Game:** Menu pengaturan langsung saat game berjalan dengan menekan tombol `Insert` di keyboard atau `L3 + R3` di stik.
- **Dukungan Controller Komprehensif:** Plug-and-play untuk PlayStation DualSense, DualShock 4, Xbox Wireless Controller, Nintendo Switch Pro Controller, dan stik USB standar via SDL3.
- **Multiplayer Lokal:** Mendukung hingga 4 pemain sekaligus di satu PC.

---

## Panduan Pengguna Baru

### Spesifikasi Minimum & Rekomendasi
| Komponen | Minimum | Rekomendasi |
|---|---|---|
| **OS** | Windows 10 (64-bit) | Windows 11 (64-bit) |
| **Prosesor** | 4-Core / 8-Thread x86_64 CPU | 6-Core / 12-Thread x86_64 CPU (AMD Zen 3 / Intel Gen 12+) |
| **Memori** | 8 GB RAM | 16 GB Dual-Channel RAM |
| **Kartu Grafis** | GPU Vulkan 1.3 (GTX 1060 6GB / RX 580) | RTX 2060 / RX 6600 atau lebih baru |
| **Penyimpanan** | 25 GB ruang kosong | NVMe / SATA SSD |

### Langkah Pemasangan
1. Unduh **`Basara4_Sumeragi_PC_Update2.zip`** dari menu [Releases](../../releases).
2. Ekstrak seluruh isi file ZIP ke folder yang Anda inginkan.
3. Masukkan folder game hasil dump legal Anda (`app0` atau `extracted_game/app0`) sejajar dengan file `basara_pc.exe`.
4. Jalankan **`Basara4_Launcher.exe`** (atau **`launcher.py`** / **`Play_Basara4.bat`**).
   - Saat pertama kali dijalankan, klik tombol emas **INITIALIZE & PLAY** untuk menghasilkan file biner engine secara otomatis (~15-30 detik).
   - Setelah selesai, tombol akan berubah menjadi **PLAY GAME** dan langsung masuk ke game!

---

## Konfigurasi File (`basara.ini`)

Semua preferensi yang diatur lewat Launcher atau menu overlay tersimpan secara otomatis di `basara.ini`:

| Kunci | Nilai Default | Keterangan |
|---|---|---|
| `output_res` | `1920x1080` | Resolusi tampilan window atau layar penuh |
| `render_res` | `1080` | Resolusi rendering internal game (`720`, `1080`, `1440`, `2160`) |
| `fullscreen` | `1` | `1` untuk layar penuh tanpa border, `0` untuk mode jendela |
| `fps_limit` | `144` | Batasan framerate (`60`, `90`, `120`, `144`, `240`, `0` untuk tanpa batas) |
| `anisotropy` | `16` | Level Anisotropic Filtering (`0`, `2`, `4`, `8`, `16`) |
| `fsr1` | `1` | `1` untuk mengaktifkan spatial upscaler AMD FSR 1.0 |
| `rcas` | `1` | `1` untuk mengaktifkan penajaman kontras adaptif RCAS |
| `rcas_strength` | `75` | Tingkat ketajaman RCAS (`0` sampai `100` persen) |
| `skip_intro` | `0` | `1` untuk melewati video intro pembuka langsung ke layar judul |
| `show_fps` | `1` | `1` untuk menampilkan overlay performa dan status FPS |

---

## Tombol Pintas & Hotkey In-Game

| Fungsi | Tombol Keyboard | Tombol Stik |
|---|---|---|
| **Buka/Tutup Menu Pengaturan** | `Insert` | `L3 + R3` (Tekan kedua analog) |
| **Ambil Screenshot (PNG)** | `F12` | — |
| **Menu Jeda (Pause)** | `Esc` | Touchpad / `View` / `Back` |

---

## Kompilasi dari Source Code

Untuk mengompilasi engine runtime dan Vulkan renderer sendiri di Windows:

```powershell
# Kebutuhan: MSYS2 CLANG64 atau Visual Studio 2022 dengan Clang/LLVM, CMake 3.24+, Vulkan SDK 1.3+
git clone https://github.com/krixsan/Basara-4-Sumeragi-Native-PC.git
cd Basara-4-Sumeragi-Native-PC

# Kompilasi langsung menggunakan skrip MSYS2 CLANG64
./win_build.sh
```

---

## Pernyataan Hukum & Hak Cipta

Proyek ini adalah inisiatif kompatibilitas dan preservasi non-komersial buatan komunitas.
- **Sengoku Basara (戦国BASARA)** dan **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)** adalah merek dagang terdaftar milik **CAPCOM Co., Ltd.**
- Repositori dan file rilis ini **sama sekali tidak mendistribusikan aset game berhak cipta, file audio, video sinematik, tekstur, maupun biner game asli**.
- Pengguna wajib menyediakan salinan game resmi mereka sendiri yang diperoleh secara sah dari piringan fisik atau digital PlayStation 4.
- Seluruh kode yang ada dalam repositori ini dilisensikan semata-mata untuk riset teknis, interoperabilitas, dan preservasi game.
