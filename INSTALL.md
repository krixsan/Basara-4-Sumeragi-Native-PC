# Panduan Instalasi (Wajib Dibaca!)

> **Berlaku untuk Sengoku Basara 4 Sumeragi PC Native Port v2.0+**
>
> Panduan ini dibuat untuk pengguna yang **bukan programmer**. Ikuti urutan langkah demi langkah secara teliti. Jika kamu hanya mengambil file `eboot.bin`, game akan gagal berjalan, crash, atau suaranya kresek karena kehilangan modul sistem audio di folder `sce_module`.

---

## 🚨 Peringatan Penting — Baca Sebelum Memulai!

> **JANGAN HANYA MENGAMBIL FILE EBOOT.BIN!**
>
> **Kamu wajib mengekstrak SELURUH folder game dari dump PS4 milikmu sendiri.**
>
> File `eboot.bin` hanyalah file eksekusi utama. Game juga membutuhkan:
> - `sce_module` — modul audio & sistem penting (`libSceNgs2.sprx`, `libSceAjm.sprx`, dll.)
> - `sce_sys` — metadata game (`param.sfo`, ikon tampilan, dll.)
> - `nativePS4` (atau `data`) — aset utama game (model 3D, audio panggung, cutscene)
>
> Jika salah satu folder di atas tidak ada, **jangan lanjutkan**. Ekstrak ulang dump game PS4 milikmu secara lengkap.

### Struktur Folder yang Salah vs Benar

```text
❌ SALAH — Hanya mengambil satu file saja
Folder Game PS4/
 └── eboot.bin

✅ BENAR — Seluruh struktur folder game disertakan
Folder Game PS4/  (contoh: CUSA12345)
 ├── eboot.bin
 ├── sce_module/
 ├── sce_sys/
 └── nativePS4/   (atau data/)
```

---

## Persyaratan Awal (Prerequisites)

Sebelum mulai, pastikan hal-hal berikut sudah siap di komputermu:

- Dump game PS4 milikmu sendiri secara legal (tidak ada file game yang dibundel di proyek ini).
- Folder game lengkap dari PS4 (`eboot.bin`, `sce_module`, `sce_sys`, dan `nativePS4`/`data`).
- File rilis terbaru: `Basara4_Sumeragi_PC_v2.0.zip` dari halaman Releases resmi.
- Sistem Operasi Windows 10 (Build 1809+) atau Windows 11 64-bit.
- Runtime Vulkan 1.3 dan Microsoft Visual C++ 2015–2022 x64 terpasang.
- Ruang penyimpanan kosong minimal 500 MB untuk engine dan cache (data game dibaca langsung dari lokasi aslinya).

### Struktur Folder Game yang Valid

```text
Folder Game PS4 (contoh: CUSA12345)
 ├── eboot.bin        <-- File eksekusi utama game
 ├── sce_module/      <-- WAJIB: modul audio & kernel
 ├── sce_sys/         <-- WAJIB: metadata dan ikon
 └── nativePS4/       <-- WAJIB: aset data game (kadang bernama "data")
```

---

## Langkah Instalasi Lengkap

### Langkah 1 — Unduh dan Ekstrak Paket Rilis v2.0

1. **Buka** tab Releases pada repository.
2. **Unduh** file paket distribusi **`Basara4_Sumeragi_PC_v2.0.zip`**.
3. **Ekstrak seluruh isi ZIP** ke direktori biasa, misalnya:
   ```text
   D:\Games\Basara4_Sumeragi_PC\
   ```
4. **Penting:** Jangan menjalankan game langsung dari dalam file ZIP yang belum diekstrak.
5. **Hindari** mengekstrak ke folder terproteksi seperti `C:\Program Files` agar engine memiliki izin menulis cache dan modul.

### Langkah 2 — Jalankan `Basara4_Launcher.exe`

1. **Buka file** **`Basara4_Launcher.exe`**.
2. **Jika Windows SmartScreen muncul**, klik **More info** lalu pilih **Run anyway**.
3. **Pemeriksaan Sistem Otomatis**: Launcher akan memverifikasi keberadaan Vulkan 1.3, Visual C++ Redistributable, dan versi OS.
4. **Jika ada dependensi yang kurang**, gunakan tombol unduhan resmi yang disediakan langsung di launcher.

### Langkah 3 — Buka Setup Wizard

1. **Klik tombol ⚡ Setup Wizard** di bar menu launcher.
2. **Baca dan setujui** pernyataan fair-use dan kepatuhan hukum.
3. **Klik tombol Get Started** untuk membuka pemilihan direktori game.

### Langkah 4 — Pilih FOLDER Game PS4 Lengkap

1. **Arahkan dialog pemilihan** ke folder utama game PS4 milikmu (folder yang langsung memuat `eboot.bin`, `sce_module`, `sce_sys`, dan `nativePS4`).
2. **Pilih foldernya**, lalu klik **Select Folder**.
3. **Penting:** Jangan klik dua kali pada file `eboot.bin` di dalam folder tersebut. Kamu harus memilih foldernya.
4. **Verifikasi Otomatis**:
   - Jika folder lengkap: Launcher menampilkan status **Valid game folder** dan tombol **Next** aktif.
   - Jika `sce_module` tidak ditemukan: Launcher akan menolak proses dan meminta folder yang lengkap.

### Langkah 5 — Proses Auto-Build dan Selesai

1. **Klik Next** untuk memulai proses linking modul sistem.
2. **Tunggu 15–30 detik** hingga modul audio dan executable tersambung secara otomatis ke direktori `out/`.
3. **Setelah status menunjukkan Setup Completed**, klik **⚔️ Play Now** atau kembali ke launcher utama dan klik **INITIALIZE & PLAY**.

---

## Checklist Sebelum Memulai Permainan

Pastikan seluruh poin berikut telah terpenuhi sebelum menjalankan game:

- [ ] Folder game berisi `eboot.bin` asli yang tidak rusak.
- [ ] Folder `sce_module` tersedia dan memuat modul audio (`libSceNgs2.sprx`, `libSceAjm.sprx`).
- [ ] Folder `sce_sys` memuat file `param.sfo`.
- [ ] Folder aset `nativePS4` atau `data` lengkap.
- [ ] Pemilihan folder pada wizard mengarah ke folder induk, bukan file tunggal.
- [ ] Auto-Build berhasil menyelesaikan kompilasi ke folder `out/`.
- [ ] Status launcher menunjukkan **Ready to Play**.

---

## Panduan Penyelesaian Masalah (Troubleshooting)

### 1. Suara Kresek, Putus-Putus, atau Hening
- **Penyebab:** Modul audio di dalam `sce_module` tidak terbaca atau folder game dipindahkan setelah instalasi awal.
- **Solusi:**
  1. Klik tombol **🔧 REPAIR & PLAY** di jendela launcher.
  2. Arahkan kembali ke folder game PS4 yang lengkap.
  3. Biarkan launcher melakukan linking ulang library audio.

### 2. Pesan Error "sce_module folder is missing"
- **Penyebab:** Folder yang dipilih bukan folder dump lengkap, melainkan hanya salinan file `eboot.bin`.
- **Solusi:** Pastikan memilih folder yang memuat folder `sce_module/` di dalamnya. Jika dump tidak memiliki folder ini, lakukan dump ulang game dari konsol PS4 milikmu.

### 3. Layar Hitam (Black Screen) atau Crash saat Start
- **Penyebab:** Driver GPU belum diperbarui atau library runtime Vulkan / Visual C++ belum terpasang.
- **Solusi:**
  1. Perbarui driver GPU NVIDIA / AMD / Intel ke versi yang mendukung Vulkan 1.3+.
  2. Pasang [Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).
  3. Matikan overlay pihak ketiga (seperti RivaTuner / RTSS) jika terjadi crash rendering.

---

## Catatan Legal

Proyek ini tidak menyertakan file game berhak cipta, file eksekusi game, aset grafis atau audio, maupun kunci dekripsi milik pihak ketiga. Seluruh proses porting memanfaatkan aset legal yang disediakan secara mandiri oleh pengguna dari game fisik atau digital milik pribadi.

*Sengoku Basara 4 Sumeragi adalah merek dagang terdaftar milik CAPCOM CO., LTD.*
