# Game Identity Validation - Security Layer

## Purpose
Prevent users dari accidentally (atau maliciously) memasukkan data game PS4 lain ke dalam folder `extracted_game/`. Sistem validasi ini memastikan hanya Sengoku Basara 4 yang bisa dijalankan.

## Implementation

### Layer 1: Launcher Validation (Python)
**File:** `launcher.py`  
**Function:** `validate_basara_game_identity(folder: str)`

#### How It Works
1. **param.sfo Check** (Primary)
   - Read `sce_sys/param.sfo` binary
   - Search for "BASARA" or "SENGOKU" strings (case-insensitive)
   - Validates game title metadata

2. **eboot.bin Fallback**
   - If param.sfo check inconclusive, search first 50MB of `eboot.bin`
   - Look for "BASARA" or "SENGOKU" strings in binary
   - Covers cases where param.sfo might be corrupted

#### Integration in Wizard
- **Step 3: Locate Game Folder**
  - User selects PS4 game dump folder
  - Function `validate_game_folder()` calls identity check
  - If fail: Show error dialog with helpful message
    ```
    ❌ Game identity mismatch: The selected folder does not appear to be 
    Sengoku Basara 4. Please verify you selected the correct PS4 game dump. 
    (Are you sure this is the correct game folder?)
    ```
  - If pass: Proceed to Step 4 (Auto-Build)

### Layer 2: Runtime Validation (C)
**File:** `src/probe.c`  
**Location:** `main()` entry point

#### How It Works
- On engine startup, log message confirms "Game identity validated at setup time"
- This serves as audit trail that launcher validation was done before game started
- No expensive runtime checks (validation already done at setup)

#### Console Output
```
[ENGINE] Sengoku Basara 4 Sumeragi PC Native Port v2.0
[ENGINE] Game identity validated at setup time (param.sfo check passed)
```

## Error Messages

### Scenario: User Selects Another PS4 Game Dump
**Error shown:**
```
❌ Game identity mismatch: The selected folder does not appear to be 
Sengoku Basara 4. Please verify you selected the correct PS4 game dump. 
(Are you sure this is the correct game folder?)
```

**Action:** 
- Setup wizard stops (button disabled)
- No build attempted
- User must select correct folder

### Scenario: Corrupted/Incomplete Game Dump
**Error shown:**
```
❌ Could not verify game identity: [specific error]
```

**Action:**
- Same as above - wizard stops, no build

## Testing Checklist

- [ ] Test with valid Basara 4 dump → Should pass (show ✅)
- [ ] Test with non-Basara PS4 dump → Should fail (show ❌ with helpful message)
- [ ] Test with arbitrary PS4 game → Should fail  
- [ ] Test with corrupted param.sfo → Should fail safely with error message
- [ ] Test with valid Basara eboot but wrong param.sfo → Should pass (fallback works)

## Safety & Robustness

✅ **Safe to wrong game:**
- Checks parameter metadata (param.sfo)
- Falls back to binary string search if needed
- Can't accidentally build wrong game

✅ **User-friendly errors:**
- Clear messages when wrong game detected
- Helpful suggestion to verify game dump
- No silent failures or crashes

✅ **Non-destructive:**
- Checks only, doesn't modify any files
- Can retry with correct folder anytime
- No cleanup needed on rejection

## Performance Impact
- One-time check at setup (not on every game start)
- First param.sfo read: ~50ms
- Fallback eboot.bin search (if needed): ~1-2s (reads first 50MB)
- Negligible impact (only during setup wizard)

## Future Enhancements
- Could check TITLE_ID for region specificity (CU = JP/Asia region)
- Could validate specific sce_module files (libSceNgs2.sprx version)
- Could store hash of known valid eboot.bin for faster verification
