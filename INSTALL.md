# Panduan Instalasi (Wajib Dibaca!)

> **Berlaku untuk Sengoku Basara 4 Sumeragi PC Native Port v1.8+**
>
> Panduan ini dibuat untuk pengguna yang **bukan programmer**. Ikuti urutannya dari atas ke bawah. Kalau kamu hanya mengambil `eboot.bin`, game akan gagal, crash, atau suaranya kresek. Penyebabnya hampir selalu satu: folder `sce_module` tidak ikut.

---

## 🚨 PERINGATAN MERAH — BACA DULU!

> ## <span style="color:#d32f2f">🚨 JANGAN HANYA MENGAMBIL FILE EBOOT.BIN! 🚨</span>
>
> **Kamu harus mengekstrak SELURUH isi folder game dari PS4-mu.**
>
> `eboot.bin` hanyalah file utama. Game juga butuh:
> - 📁 `sce_module` → modul audio & sistem (contoh: `libSceNgs2.sprx`, `libSceAjm.sprx`)
> - 📁 `sce_sys` → metadata game (`param.sfo`, icon, dll.)
> - 📁 `nativePS4` atau `data` → aset game (model, suara, stage, movie, dll.)
>
> Kalau salah satu folder di atas tidak ada, **jangan lanjut**. Ekstrak ulang dump PS4-mu dengan lengkap.

### ❌ Salah vs ✅ Benar

```text
❌ SALAH — cuma mengambil satu file
Folder Game PS4/
 └── eboot.bin

✅ BENAR — seluruh folder game ikut
Folder Game PS4/  (contoh: CUSA12345)
 ├── eboot.bin
 ├── sce_module/
 ├── sce_sys/
 └── nativePS4/   (atau data/)
```

---

## 📋 Apa yang Kamu Butuhkan (Prerequisites)

Sebelum mulai, pastikan semua ini sudah siap:

- [ ] **Dump game PS4 milikmu sendiri** (legal). Tidak ada file game yang dibundel di proyek ini.
- [ ] **Folder game lengkap** dari PS4, bukan hanya `eboot.bin`.
- [ ] **Rilis v1.8 atau lebih baru**: `Basara4_Sumeragi_PC_v1.8.zip` dari tab [Releases](../../releases).
- [ ] **Windows 10 1809+ / Windows 11 64-bit**.
- [ ] **Vulkan 1.3** dan **VC++ 2015–2022 x64** (link ada di [README.md](README.md#system-requirements)).
- [ ] Ruang kosong minimal **500 MB** untuk engine dan cache. Data game tetap dipakai di tempat aslinya, tidak disalin 20+ GB.

### 📁 Struktur Folder Game yang Benar

```text
📁 Folder Game PS4 Kamu (contoh: CUSA12345)
 ├── 📄 eboot.bin        <-- File utama game
 ├── 📁 sce_module       <-- WAJIB! (libSceNgs2.sprx, libSceAjm.sprx, dll. untuk audio)
 ├── 📁 sce_sys          <-- WAJIB! (param.sfo, icon0.png, dll.)
 └── 📁 nativePS4        <-- WAJIB! (aset game; di beberapa dump tampil sebagai "data")
```

> 💡 **Catatan nama folder:** untuk Basara 4 Sumeragi, folder aset biasanya bernama **`nativePS4`**. Di dump lain kadang bernama **`data`**. Launcher menerima salah satu selama isinya aset game lengkap.

### 📦 Isi `sce_module` yang Harus Ada

Folder `sce_module` **tidak boleh kosong**. Minimal harus ada modul sistem PS4 seperti:

```text
sce_module/
 ├── libSceNgs2.sprx     <-- audio mixer (WAJIB untuk suara)
 ├── libSceAjm.sprx      <-- audio codec (WAJIB untuk suara)
 ├── libSceFiber.sprx
 ├── libSceUlt.sprx
 ├── ulobjmgr.sprx
 ├── libc.prx
 └── libSceFios2.prx
```

Jangan mengubah nama file. Kalau folder ini hilang, audio akan putus-putus, kresek, atau game crash saat masuk stage.

---

## 🛠️ Langkah Instalasi (Step-by-Step)

### Langkah 1 — Download dan Ekstrak Rilis v1.8

1. Buka tab **[Releases](../../releases)**.
2. Download **`Basara4_Sumeragi_PC_v1.8.zip`** (atau versi terbaru).
3. Ekstrak **seluruh isi ZIP** ke folder biasa, misalnya:

   ```text
   D:\Games\Basara4_Sumeragi_PC\
   ```

4. **Jangan** menjalankan launcher langsung dari dalam ZIP.
5. **Jangan** ekstrak ke `C:\Program Files` atau folder yang dilindungi Windows. Gunakan folder seperti `D:\Games\...` agar launcher bisa menulis cache dan modul.

Setelah diekstrak, kamu akan melihat:

```text
Basara4_Sumeragi_PC/
 ├── Basara4_Launcher.exe   <-- buka file ini
 ├── basara_pc.exe
 ├── basara.ini
 ├── out/
 └── ...
```

---

### Langkah 2 — Buka `Basara4_Launcher.exe`

1. Klik dua kali **`Basara4_Launcher.exe`**.
2. Kalau Windows SmartScreen muncul:
   - Klik **More info**.
   - Klik **Run anyway**.
   - Hanya lakukan ini kalau file diunduh dari halaman Release resmi proyek.
3. Launcher akan mengecek Vulkan, VC++ Redist, versi Windows, dan ruang disk.
4. Kalau ada dependensi yang kurang, ikuti tombol download resmi yang muncul.

---

### Langkah 3 — Klik **Setup Wizard**

1. Di jendela launcher, klik tombol **⚡ Setup Wizard** (ikon tongkat sihir).
2. Wizard 5 langkah akan terbuka.
3. Baca dan setujui pernyataan legal/fair-use.
4. Klik **Get Started**.

> Kalau wizard tidak muncul otomatis, klik tombol **Setup Wizard** di toolbar launcher. Kamu juga bisa membukanya lagi kapan saja.

---

### Langkah 4 — PENTING: Pilih **FOLDER GAME**, Bukan `eboot.bin`

Saat wizard membuka jendela pemilihan:

1. Arahkan ke **folder yang langsung berisi `eboot.bin`**, misalnya:

   ```text
   D:\PS4 Dump\CUSA12345\
   ```

2. Pastikan di dalam folder itu terlihat:
   - `eboot.bin`
   - `sce_module`
   - `sce_sys`
   - `nativePS4` (atau `data`)
3. Klik **Select Folder**.
4. **JANGAN** klik dua kali `eboot.bin`. **JANGAN** memilih file `eboot.bin` saja.

Launcher akan memvalidasi folder secara otomatis:

- ✅ Kalau lengkap: muncul **“Valid game folder”** dan tombol **Next** aktif.
- ❌ Kalau `sce_module` tidak ada: launcher **menolak** dan menampilkan pesan error. Itu artinya folder yang kamu pilih belum lengkap.

> 📌 Folder game **dipakai langsung** oleh launcher. Kamu tidak perlu menyalin 20+ GB ke folder port. Path-nya disimpan di `basara.ini` sebagai `game_dir=...`.

---

### Langkah 5 — Tunggu Auto-Build, lalu Klik **PLAY**

1. Klik **Next**. Launcher akan menjalankan **Auto-Build**.
2. Tunggu sekitar **15–30 detik** (bisa lebih lama di HDD). **Jangan tutup jendela wizard.**
3. Proses ini membuat:
   - `out/boot-linked.bin`
   - `out/content.bin`
   - `out/import_names.txt`
   - patch FPS
4. Setelah muncul **“🎉 Setup Completed Successfully!”**, klik:
   - **⚔️ Play Now** untuk langsung main, atau
   - **Back to Launcher** lalu klik **PLAY GAME**.

Status launcher yang benar akan terlihat seperti:

```text
✅ System Verified — Ready to Play
```

---

## ✅ Checklist Sebelum Klik PLAY

Centang semuanya dulu:

- [ ] Folder game berisi `eboot.bin`.
- [ ] Folder `sce_module` ada dan **tidak kosong**.
- [ ] Folder `sce_sys` berisi `param.sfo`.
- [ ] Folder `nativePS4` atau `data` berisi aset game.
- [ ] Yang dipilih di wizard adalah **folder**, bukan file `eboot.bin`.
- [ ] Auto-Build selesai tanpa error.
- [ ] Status launcher **Ready to Play**.

Kalau ada satu saja yang belum, kembali ke [Troubleshooting](#-troubleshooting-solusi-masalah).

---

## 🔧 Troubleshooting (Solusi Masalah)

### 1. Suara Kresek, Putus-Putus, atau Hilang

**Penyebab paling umum:** folder `sce_module` tidak ikut terpilih atau tidak ter-copy.

**Solusi:**

1. Klik tombol **🔧 REPAIR & PLAY** di launcher.
2. Kalau diminta memilih folder, pilih lagi **folder game lengkap** (yang berisi `eboot.bin` + `sce_module` + `sce_sys` + `nativePS4`/`data`).
3. Tunggu proses repair selesai. Launcher akan menyinkronkan ulang modul audio seperti `libSceNgs2.sprx` dan `libSceAjm.sprx`.
4. Setelah selesai, game akan dibuka otomatis.

Kalau tetap kresek:

- Pastikan `sce_module/libSceNgs2.sprx` dan `sce_module/libSceAjm.sprx` benar-benar ada.
- Pastikan folder game tidak dipindah atau di-rename setelah setup.
- Jalankan ulang **Setup Wizard** dan pilih folder game lagi.

---

### 2. Launcher Bilang **“sce_module folder is missing”**

Artinya folder yang kamu pilih bukan folder game lengkap.

**Solusi:**

- Jangan pilih `eboot.bin`.
- Jangan pilih subfolder yang hanya berisi `eboot.bin`.
- Pilih folder yang **langsung** berisi `eboot.bin`, `sce_module`, `sce_sys`, dan `nativePS4`/`data`.
- Kalau folder `sce_module` memang tidak ada, ekstrak ulang dump PS4-mu. Folder itu tidak bisa dibuat kosong-kosong; isinya modul sistem dari dump.

---

### 3. Launcher Bilang **“sce_sys/param.sfo is missing”**

Folder `sce_sys` belum lengkap.

**Solusi:**

- Pastikan `sce_sys/param.sfo` ada.
- Ekstrak ulang seluruh folder game dari dump PS4.
- Jangan hanya menyalin `eboot.bin` dan `sce_module`.

---

### 4. Launcher Bilang **“Game data folder (nativePS4 or data) is missing”**

Ini berarti dump-mu belum lengkap. Game tidak punya aset untuk dimainkan.

**Solusi:**

- Pastikan folder `nativePS4` (Basara 4) atau `data` ada dan berisi aset game.
- Ekstrak ulang dump PS4 secara lengkap.
- Jangan memindahkan folder aset keluar dari folder game.

---

### 5. Launcher Bilang **“eboot.bin is not valid”**

File `eboot.bin` rusak, terpotong, masih terenkripsi, atau bukan file yang benar.

**Solusi:**

- Dump ulang `eboot.bin` dari PS4 milikmu.
- Pastikan file berukuran lebih dari 10 MB.
- Jangan menggunakan `eboot.bin` dari region/versi game yang tidak cocok.

---

### 6. Auto-Build Gagal karena Modul Tidak Lengkap

Pesan contoh:

```text
Missing audio/system modules: libSceNgs2.sprx, libSceAjm.sprx
```

**Solusi:**

1. Pastikan folder `sce_module` dari dump ikut terpilih.
2. Klik **🔧 REPAIR & PLAY**.
3. Kalau masih gagal, letakkan file `11.00_sys_modules.zip` (atau arsip modul PS4 yang sesuai) di folder launcher, lalu ulangi repair.
4. Jangan mencampur modul dari firmware/region yang tidak cocok.

---

### 7. Game Crash atau Black Screen Saat Dibuka

Ini biasanya bukan masalah `eboot.bin`, tetapi dependensi atau driver.

**Solusi:**

- Pastikan **Vulkan 1.3** terpasang dan driver GPU terbaru.
- Pasang **VC++ 2015–2022 Redistributable (x64)**.
- Cek `user/logs/basara.log` dan `user/crashes/`.
- Coba jalankan launcher dari folder biasa (bukan `Program Files`).
- Tutup overlay/RTSS yang bisa mengganggu Vulkan.

---

### 8. Folder Game Dipindah atau Di-rename

Launcher menyimpan path di `basara.ini` (`game_dir=...`). Kalau folder dipindah, path lama menjadi tidak valid.

**Solusi:**

- Buka **Setup Wizard** lagi.
- Pilih folder game yang baru.
- Tunggu Auto-Build, lalu PLAY.

---

### 9. Controller Tidak Terdeteksi

- Controller XInput (Xbox, PS4/PS5 via DS4Windows/Steam) biasanya langsung bekerja.
- Untuk controller DirectInput generik, klik **🎮 Gamepad** di launcher dan buat mapping.

---

## ❓ FAQ Singkat

### Apakah aku harus menyalin seluruh folder game ke folder port?

**Tidak.** Launcher memakai folder game yang kamu pilih secara langsung. Data game tidak disalin 20+ GB. Tapi jangan pindahkan atau hapus folder itu setelah setup.

### Apakah boleh memilih folder `app0`?

**Boleh**, asalkan folder `app0` itu **langsung berisi** `eboot.bin`, `sce_module`, `sce_sys`, dan `nativePS4`/`data`. Yang dilarang adalah memilih file `eboot.bin` saja.

### Kenapa `sce_module` begitu penting?

Karena `sce_module` berisi modul audio dan sistem PS4. Tanpa modul seperti `libSceNgs2.sprx` dan `libSceAjm.sprx`, audio tidak bisa diproses dengan benar. Hasilnya: suara kresek, putus-putus, atau crash.

### Apakah launcher mengunduh file game?

**Tidak.** Launcher hanya membangun `out/boot-linked.bin` dan profil dari file yang kamu sediakan sendiri. Tidak ada aset Capcom yang dibundel atau diunduh.

### Apakah bisa langsung memakai file ISO?

**Tidak.** Kamu perlu mengekstrak/melakukan dump isi game terlebih dahulu sehingga menjadi folder dengan `eboot.bin`, `sce_module`, `sce_sys`, dan aset game.

### Apakah panduan ini berlaku untuk region lain?

Port ini ditujukan untuk **Sengoku Basara 4 Sumeragi**. Gunakan dump yang cocok dengan versi game yang didukung. Kalau `eboot.bin` tidak valid, kemungkinan region/versinya tidak cocok.

---

## 📌 Ringkasan Cepat

```text
1. Download & ekstrak rilis v1.8.
2. Buka Basara4_Launcher.exe.
3. Klik Setup Wizard.
4. Pilih FOLDER game lengkap (eboot.bin + sce_module + sce_sys + nativePS4/data).
5. Tunggu Auto-Build, lalu PLAY.
```

**Kunci utamanya:** pilih **folder**, bukan `eboot.bin`. Pastikan **`sce_module`** ikut. Kalau suara kresek, klik **🔧 REPAIR & PLAY**.

---

## ⚖️ Catatan Legal

Proyek ini **tidak menyertakan** file game, `eboot.bin`, `sce_module`, aset Capcom, atau kunci enkripsi apa pun. Kamu wajib menggunakan dump dari game PS4 yang **kamu miliki sendiri secara legal**. Panduan ini hanya menjelaskan cara memakai dump milikmu di PC.

*Sengoku Basara 4 Sumeragi adalah merek dagang CAPCOM CO., LTD. Proyek ini adalah inisiatif pelestarian independen dan tidak berafiliasi dengan Capcom.*
