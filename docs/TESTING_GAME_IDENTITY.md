# Game Identity Validation - Testing Guide

## Pre-Test Setup
- [ ] Backup current `basara_pc.exe` and `Basara4_Launcher.exe`
- [ ] Build complete with game identity validation added
- [ ] Have test dumps ready:
  - Sengoku Basara 4 (valid)
  - Another PS4 title (invalid, different game)
  - Incomplete/corrupted dump (invalid)

## Test Case 1: Valid Basara 4 Dump
**Expected:** Setup wizard accepts folder and proceeds

1. [ ] Launch `Basara4_Launcher.exe`
2. [ ] Click "Get Started" → Setup Wizard
3. [ ] Navigate to Step 3 ("Locate Game Folder")
4. [ ] Browse to valid Basara 4 dump folder (contains `eboot.bin`, `sce_sys/param.sfo`, `sce_module/`)
5. [ ] Observe status:
   - [ ] Should show: `✅ Valid game folder` (GREEN)
   - [ ] Should show: `Game identity verified: Sengoku Basara 4`
   - [ ] Next button should be ENABLED
6. [ ] Click "Next" → Continue to build step
7. [ ] **PASS** if build proceeds normally

## Test Case 2: Other PS4 Game Dump
**Expected:** Setup wizard rejects folder with clear error

1. [ ] Launch `Basara4_Launcher.exe`
2. [ ] Click "Get Started" → Setup Wizard
3. [ ] Navigate to Step 3 ("Locate Game Folder")
4. [ ] Browse to other game dump folder
5. [ ] Observe status:
   - [ ] Should show: `❌ Game identity mismatch` (RED)
   - [ ] Should show helpful message mentioning verification of correct game dump
   - [ ] Next button should be DISABLED
6. [ ] Try clicking Next: Button should not respond
7. [ ] **PASS** if user can only proceed after selecting correct Basara folder

## Test Case 3: Random PS4 Game (e.g., Knack, GT Sport)
**Expected:** Setup wizard rejects with game identity error

1. [ ] Same as Test Case 2 but with different game
2. [ ] Should show `❌ Game identity mismatch` error
3. [ ] Next button disabled
4. [ ] **PASS** if rejection works for any non-Basara game

## Test Case 4: Corrupted/Incomplete Dump
**Expected:** Setup wizard rejects with appropriate error

Scenarios:
- [ ] Missing `param.sfo` → Should show "param.sfo not found"
- [ ] Empty/truncated `param.sfo` → Should show "Could not verify game identity"
- [ ] Missing `sce_module/` → Should show existing error (before identity check)
- [ ] eboot.bin too small → Should show existing validation error

**PASS** if all scenarios show clear errors without crashing

## Test Case 5: Valid Basara + Corrupted param.sfo (Fallback)
**Scenario:** param.sfo cannot be read, but eboot.bin contains "BASARA"  
**Expected:** Validation passes via eboot.bin fallback

1. [ ] Have valid Basara dump but corrupt param.sfo
2. [ ] Select folder
3. [ ] Should still show `✅ Verified via eboot.bin` (or similar)
4. [ ] **PASS** if fallback to eboot.bin search works

## Test Case 6: Runtime Log Verification
**Expected:** Engine logs confirmation message on startup

1. [ ] Complete wizard with valid Basara dump
2. [ ] Click "PLAY GAME"
3. [ ] Game starts (wait for console/log window)
4. [ ] Check console output:
   - [ ] Should show: `[ENGINE] Sengoku Basara 4 Sumeragi PC Native Port v2.0`
   - [ ] Should show: `[ENGINE] Game identity validated at setup time (param.sfo check passed)`
5. [ ] **PASS** if both messages appear

## Regression Tests
- [ ] 2-Player mode still works (after build)
- [ ] Audio plays correctly (no new issues)
- [ ] Performance mode toggle works
- [ ] Telemetry still functioning
- [ ] Launcher settings persist to basara.ini

## Success Criteria
✅ All test cases pass (no crashes, clear error messages)  
✅ Launcher rejects non-Basara games with helpful feedback  
✅ Valid Basara dumps proceed through wizard normally  
✅ No regression in existing features  
✅ Runtime engine logs validation confirmation  

## Failure Recovery
If validation test fails:
1. [ ] Check console for error message
2. [ ] Verify test dump is actually valid Basara 4
3. [ ] Check if param.sfo contains "BASARA" or "SENGOKU" (search in hex editor)
4. [ ] Report with: error message + test dump details
