## 🚀 Highlights
Update v2.1.0 membawa stabilitas maksimal, perbaikan *crash* kritis, dan *Crash Reporter* kelas Enterprise.

### 🛠️ Critical Fixes
- **Fixed Stack Buffer Overflow (CWE-121)**: Memperbaiki *crash* fatal (`guest stack protector detected corruption`) saat memuat teks di *Stage Select* atau *Roulette*.
- **Universal Text Parser Bypass**: Menambahkan *runtime trampoline patch* (`patches.bin`) yang melakukan *bounds-check* pada parser teks guest. Aman dari teks panjang atau *missing tags* tanpa mengubah file asli game.
- **Fixed AvPlayer Shutdown Deadlock & UAF**: Memperbaiki *race condition* pada thread `AvWatchdog` saat video *cutscene* ditutup.

### ⚡ Performance
- **80+ FPS Unlocked**: Optimasi pada *patch* FPS dan hilangnya *stutter* akibat *error handling* teks.

### 🎨 Enterprise-Grade Crash Reporter
- **Modern Dark UI (CustomTkinter)**: UI crash dialog baru dengan *syntax highlighting*.
- **Minidump Auto-Parser**: Otomatis membaca file `.dmp` dan menampilkan Modul + RIP (Instruction Pointer) yang *crash*.
- **One-Click Crash Bundle**: Otomatis mengompresi `.dmp`, `.log`, dan laporan `.txt` menjadi satu file `.zip` yang siap di-*upload* ke GitHub.
- **Hardware Telemetry**: Mencatat RAM, Page File, dan GPU saat *crash* terjadi.

### ⚠️ Known Issues
- **Character Transition Freeze**: Masih ada *freeze* saat memuat cutscene transisi karakter (misal sebelum masuk *Stage Select*). Saat ini game tidak akan *hang* permanen karena *Watchdog* akan otomatis men-*skip* cutscene tersebut. Perbaikan untuk `sceAvPlayerDisableStream` akan hadir di v2.1.1.
