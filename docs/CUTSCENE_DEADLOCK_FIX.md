# Cutscene Deadlock Fix - Auto-Skip Safety Net

## Problem
Game freezes di cutscene perkenalan karakter (setelah pilih karakter). User harus manual pencet tombol "Skip" untuk lanjut.

## Root Cause
Main thread game loop call `GetVideoData()` berulang-ulang, tapi decoder thread macet atau tidak produce frame. Game stuck tunggu frame yang tidak pernah datang.

**Titik deadlock potensial:**
1. `VideoDecoderThread` wait forever di `m_video_buffers_cv` jika buffer kosong
2. `AudioDecoderThread` wait forever di `m_audio_buffers_cv` jika buffer kosong  
3. Game main thread loop `GetVideoData()` return false terus-menerus

## Solution: Watchdog Thread (Auto-Skip)

### Implementation
Tambahkan **Watchdog Thread** yang monitor frame delivery:
- Cek setiap 500ms
- Jika tidak ada frame delivered selama **3000ms** (3 detik)
- Auto force-stop cutscene dengan `m_state.OnError()`
- Game otomatis lanjut tanpa harus pencet Skip

### Files Modified
1. **avplayer_source.h**
   - Added: `Kernel::Thread m_watchdog_thread{}`
   - Added: `std::atomic<u64> m_frames_delivered{0}`
   - Added: `void WatchdogThread(std::stop_token stop)`

2. **avplayer_source.cpp**
   - `GetVideoData()`: Increment `m_frames_delivered` setiap frame delivered
   - `GetAudioData()`: Increment `m_frames_delivered` setiap frame delivered
   - `Start()`: Launch `m_watchdog_thread`
   - `Stop()`: Stop `m_watchdog_thread`
   - `WatchdogThread()`: Monitor loop dengan 3s timeout

### How It Works
```
Timeline:
0ms    - Cutscene starts, decoder threads running
100ms  - Frame delivered → reset watchdog timer
200ms  - Frame delivered → reset watchdog timer
...
[DEADLOCK OCCURS - no more frames]
3000ms - Watchdog detects: no frames for 3000ms
3000ms - Auto force-stop: m_state.OnError()
3001ms - Game unblocked, lanjut ke gameplay
```

### Log Output
```
[AV_WATCHDOG] DEADLOCK DETECTED: No frames delivered for 3000 ms. Auto-stopping cutscene.
```

## Testing
1. Start game, pilih karakter
2. Cutscene perkenalan mulai
3. Jika decoder macet → watchdog auto-stop setelah 3s
4. Game langsung lanjut ke gameplay (tidak perlu pencet Skip manual)

## Alternative Approaches Considered
1. ❌ Timeout di `ajm_batch_wait()` - Tidak efektif, masalahnya di video decoder bukan audio
2. ❌ Timeout 200ms di decoder wait - Terlalu agresif, bisa skip frame normal yang lambat
3. ✅ Watchdog 3s - Balance antara toleransi normal lag dan deteksi deadlock

## Safety
- Watchdog hanya aktif saat playback (tidak freeze jika paused/EOF)
- 3s timeout cukup lama untuk shader compile atau stage load spike
- Force-stop via `OnError()` adalah safe path (sama dengan error normal)

## Performance Impact
- Watchdog thread sleep 500ms per check → minimal CPU usage
- Atomic counter increment per frame → negligible overhead
