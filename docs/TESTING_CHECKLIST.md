# Testing Checklist - Cutscene Deadlock Fix

## Pre-Test Setup
- [ ] Build `basara_pc.exe` sukses
- [ ] Copy `basara_pc.exe` ke root directory
- [ ] Backup `basara_pc.exe` lama (jika ada)

## Test Case 1: Normal Cutscene (No Deadlock)
**Expected:** Cutscene play normal, tidak auto-skip

1. [ ] Launch game
2. [ ] Pilih karakter (contoh: Date Masamune)
3. [ ] Cutscene perkenalan mulai
4. [ ] Watch for: Frame delivered setiap 16-33ms (60-30 FPS)
5. [ ] Expected: Cutscene play sampai selesai normal
6. [ ] Expected: Tidak ada log `[AV_WATCHDOG] DEADLOCK DETECTED`

## Test Case 2: Deadlock Detection (Safety Net) — v2.1.1 WATCHDOG TIMEOUT INCREASED
**Expected:** Watchdog triggers ONLY after 10s of no frame delivery (increased from 3s)

**Note**: With fixes in v2.1.1, watchdog should rarely trigger. This tests the safety net only.

Simulate deadlock (if possible):
1. [ ] Launch game with debug logging enabled
2. [ ] Look for: `[Lib_AvPlayer] Watchdog Thread started` message at startup
3. [ ] IF watchdog triggers (unlikely with v2.1.1 fixes):
   - [ ] Should wait ≥10 seconds before firing (not 3s as in v2.0)
   - [ ] Log shows: `[AV_WATCHDOG] DEADLOCK DETECTED: No frames delivered for 10000+ ms`
   - [ ] Game auto-stops cutscene and continues to gameplay
   - **IMPORTANT**: Watchdog timeout increased to 10s to accommodate shader compile spikes

## Test Case 3: Manual Skip Still Works
**Expected:** User masih bisa skip manual sebelum 3s timeout

1. [ ] Launch game
2. [ ] Pilih karakter
3. [ ] Saat cutscene play, press Skip button
4. [ ] Expected: Skip langsung (tidak tunggu watchdog timeout)

## Test Case 4: Performance Check
**Expected:** No performance regression

1. [ ] Launch game
2. [ ] Play 5 menit (berbagai cutscene dan gameplay)
3. [ ] Monitor CPU usage: watchdog thread < 1% CPU
4. [ ] Monitor memory: no leaks
5. [ ] Monitor log: tidak ada spam `[AV_WATCHDOG]` di normal operation

## Test Case 5: Regression Test - Other Features
**Expected:** Existing features masih jalan

- [ ] 2-Player mode masih works
- [ ] Save/Load masih works
- [ ] Audio playback normal
- [ ] FPS counter toggle works
- [ ] Performance mode toggle works

## Log Keywords to Watch — v2.1.1

### ✅ EXPECTED (Normal Operation)
```
[Lib_AvPlayer] Watchdog Thread started (auto-skip cutscene freeze)
[Lib_AvPlayer] Watchdog Thread exited normally
[Lib_AvPlayer] Audio Decoder Thread started
[Lib_AvPlayer] Audio Decoder Thread exited normally
[Lib_AvPlayer] Demuxer Thread started
```

### ⚠️ ACCEPTABLE (Audio Clock Drift Fallback — NEW in v2.1.1)
```
[AV_TIMING] Audio clock drift >1s detected, using wall clock (audio=Xms, wall=Yms, drift=Zms)
```
**Interpretation**: Audio pipeline timestamp was abnormal (>1s drift), switched to wall-clock timing. This is the fix for deadlock prevention and should NOT freeze playback.

### ❌ FAILURE (Watchdog Triggered — Indicates Unresolved Bug)
```
[AV_WATCHDOG] DEADLOCK DETECTED: No frames delivered for 10000+ ms. Auto-stopping cutscene.
[Lib_AvPlayer] Watchdog detected deadlock: no frames for 10000+ ms. Force-stopping playback.
```
**Note**: In v2.1.1, this should be extremely rare (only after 10s of silence). If triggered:
- Expected: Game continues to gameplay after watchdog intervention
- Problem: Indicates deeper sync issue; collect logs and debug further

### 🔴 CRITICAL (Crash/Hang)
```
[Lib_AvPlayer] Could not seek video stream to start: error = X
[Lib_AvPlayer] Could not convert audio frame to S16 format
[Lib_AvPlayer] Demuxer error: Could not read AV frame
```
**Action**: Game should error gracefully; logs should show OnError() called before freeze.

## Success Criteria — v2.1.1 TARGET

### PRIMARY (Must Pass)
- [ ] **Zero watchdog triggers** during normal cutscene playback (entire game)
  - Search logs for: `[AV_WATCHDOG] DEADLOCK DETECTED`
  - Must find: **ZERO** instances
- [ ] All cutscenes play smoothly to completion
- [ ] Manual skip (if game supports) still works
- [ ] Game continues to gameplay after cutscene ends

### SECONDARY (Monitor)
- [ ] **Audio clock drift fallback OK** — may see `[AV_TIMING]` messages
  - This is expected: indicates audio clock drift >1s, using wall clock fallback
  - Should NOT block or freeze playback
- [ ] No performance regression vs v2.0
- [ ] No memory leaks (extended play session)

### REGRESSION TEST (v2.0 vs v2.1.1)
- [ ] v2.0: Cutscenes froze at ~3s with watchdog auto-skip
- [ ] v2.1.1: Cutscenes complete without any watchdog triggers
- [ ] **Expected improvement**: 0 watchdog events vs 1-5 in v2.0

## Rollback Plan (Jika Ada Issue)
1. Restore backup `basara_pc.exe` lama
2. Report issue ke developer
3. Revert commit: `git revert HEAD`
