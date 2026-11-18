"""GoldHEN cheat data for Sengoku Basara 4 Sumeragi, CUSA01159 update 01.02."""
import struct
from pathlib import Path

try:
    from basara4_dlc import _parse_sfo
except ImportError:
    try:
        from launcher.basara4_dlc import _parse_sfo
    except ImportError:
        def _parse_sfo(data): return {}

BASE_ADDRESS = 0x400000
SUPPORTED_VERSION = "01.02"
AUTHOR = "Q8Despair / Ported for PC by Krixsan"
SOURCE_URL = "https://github.com/GoldHEN/GoldHEN_Cheat_Repository/blob/main/json/CUSA01159_01.02.json"

# Verified free zero-filled region in Segment 0 of out/eboot.elf (0x106F5FA..0x106F7C7).
_CAVE_START = 0x106F600
_CAVE_LIMIT = 0x106F7C8
_cave_cursor = _CAVE_START


def _calc_jump(from_addr, to_addr, hook_len=6):
    if hook_len < 5:
        raise ValueError(f"hook_len {hook_len} < 5")
    disp = to_addr - (from_addr + 5)
    return b"\xE9" + struct.pack("<i", disp) + b"\x90" * (hook_len - 5)


def _alloc_cave(builder):
    """Allocate the next free cave slot inside _CAVE_START.._CAVE_LIMIT."""
    global _cave_cursor
    addr = _cave_cursor
    data = builder(addr)
    end = addr + len(data)
    if end > _CAVE_LIMIT:
        raise RuntimeError(
            f"Code cave overflow: 0x{end:X} exceeds safe limit 0x{_CAVE_LIMIT:X}"
        )
    _cave_cursor = end
    return addr, data


def _jcc_rel8(opcode, skipped_body):
    """Emit a 2-byte short conditional jump skipping `skipped_body`."""
    return bytes((opcode, len(skipped_body))) + skipped_body


def _make_profile_disp_cave(hook_addr, hook_len, field_off, value, reg_mov_prefix):
    """Build a hook + cave that sets [rax+field_off] = value and loads register."""
    val_le = struct.pack("<I", value)
    def _build(cave):
        body = (
            b"\xC7\x80" + struct.pack("<i", field_off) + val_le
            + reg_mov_prefix + val_le
        )
        return body + _calc_jump(cave + len(body), hook_addr + hook_len, 5)
    cave_addr, cave_bytes = _alloc_cave(_build)
    return (
        (cave_addr, cave_bytes.hex(), "00" * len(cave_bytes)),
        (hook_addr, _calc_jump(hook_addr, cave_addr, hook_len).hex(), None),
    )


def _make_simple_store_cave(hook_addr, hook_len, store_prefix, value_bytes=None):
    """Build a hook + cave that runs `store_prefix (+ optional value_bytes)` then jumps back."""
    payload = store_prefix + (value_bytes or b"")
    def _build(cave):
        return payload + _calc_jump(cave + len(payload), hook_addr + hook_len, 5)
    cave_addr, cave_bytes = _alloc_cave(_build)
    return cave_addr, cave_bytes, _calc_jump(hook_addr, cave_addr, hook_len)


# ==============================================================================
# Verified Code Caves & Hooks for CUSA01159 v1.02 (Inside Segment 0: 0x0..0x12bd788)
# ==============================================================================

# 1. Special Coin (Tenka Medals) x999,999 in Battle
_COIN_VALUE = 999999  # 0x000F423F
_coin_hook = 0x582B0
_coin_cave, _coin_cave_bytes, _coin_hook_bytes = _make_simple_store_cave(
    _coin_hook, 7, b"\xC7\x87\xE8\x02\x00\x00", struct.pack("<I", _COIN_VALUE)
)

# 2. Gold: populate [profile+0xdc] = 9,999,999 on Shop list & Forge HUD
_GOLD_VALUE = 9999999  # 0x0098967F
(_gold_shop_cave_w, _gold_shop_hook_w) = _make_profile_disp_cave(
    0x531BDE, 6, 0xDC, _GOLD_VALUE, b"\xB8"
)
(_gold_forge_cave_w, _gold_forge_hook_w) = _make_profile_disp_cave(
    0x55D6D1, 7, 0xDC, _GOLD_VALUE, b"\x41\xBD"
)

# 3. Weapon Points (cap = 99,999 = 0x1869F verified at 0x529EA0)
_WP_VALUE = 99999
(_wp_disp_cave_w, _wp_disp_hook_w) = _make_profile_disp_cave(
    0x55B402, 6, 0xE4, _WP_VALUE, b"\xBA"
)
_wp_hook = 0x560FC6
_wp_cave, _wp_cave_bytes, _wp_hook_bytes = _make_simple_store_cave(
    _wp_hook, 6, b"\xB8" + struct.pack("<I", _WP_VALUE) + b"\x89\x81\xE4\x00\x00\x00"
)

# 4. Weapon Rank Points (cap = 999 = 0x3E7 verified at 0x529928 / 0x529F62)
_WRP_VALUE = 999
(_wrp_disp_cave_w, _wrp_disp_hook_w) = _make_profile_disp_cave(
    0x55B41C, 6, 0xE8, _WRP_VALUE, b"\xBA"
)
_wrp_hook = 0x55E6A1
_wrp_cave, _wrp_cave_bytes, _wrp_hook_bytes = _make_simple_store_cave(
    _wrp_hook, 6, b"\xBA" + struct.pack("<I", _WRP_VALUE) + b"\x89\x90\xE8\x00\x00\x00"
)

# 5. Growth Points (Inro): 999,999 on Dojo open & stat/level purchase
_GROWTH_VALUE = 999999  # 0x000F423F
_growth_stat_hook = 0x5026D8
_growth_stat_cave, _growth_stat_cave_bytes, _growth_stat_hook_bytes = _make_simple_store_cave(
    _growth_stat_hook, 7, b"\x41\xC7\x85\xB4\x06\x00\x00", struct.pack("<I", _GROWTH_VALUE)
)
_growth_level_hook = 0x5028D4
_growth_level_cave, _growth_level_cave_bytes, _growth_level_hook_bytes = _make_simple_store_cave(
    _growth_level_hook, 7, b"\x41\xC7\x85\xB4\x06\x00\x00", struct.pack("<I", _GROWTH_VALUE)
)

# 6. Infinite Health (cCharaStatus: bitmask [rdi+0x148] & 3 matches P1/P2/Tag Partner)
# 6a. cCharaStatus::SetLife (0x1B2130): clamp new HP esi = mLifeMax ([rdi+0x3b4])
def _build_hp_set(cave):
    head = b"\x8B\x87\xB4\x03\x00\x00"              # mov eax, [rdi+0x3b4]
    chk_pl = b"\xF6\x87\x48\x01\x00\x00\x03"        # test byte ptr [rdi+0x148], 3
    if_pos = _jcc_rel8(0x7E, b"\x89\xC6")           # jle skip; mov esi, eax
    pl_body = b"\x85\xC0" + if_pos                  # test eax, eax
    body = head + chk_pl + _jcc_rel8(0x74, pl_body) # je back
    return body + _calc_jump(cave + len(body), 0x1B2136, 5)


# 6b. cCharaStatus::AddLife (0x1B2280): force eax = mLifeMax and delta esi = 0 for players
def _build_hp_add(cave):
    head = b"\x8B\x87\xB0\x03\x00\x00"              # mov eax, [rdi+0x3b0]
    chk_pl = b"\xF6\x87\x48\x01\x00\x00\x03"        # test byte ptr [rdi+0x148], 3
    set_full = b"\x89\xC8\x31\xF6"                  # mov eax, ecx; xor esi, esi
    pl_body = b"\x8B\x8F\xB4\x03\x00\x00\x85\xC9" + _jcc_rel8(0x7E, set_full)
    body = head + chk_pl + _jcc_rel8(0x74, pl_body)
    return body + _calc_jump(cave + len(body), 0x1B2286, 5)


# 6c. cCharaStatus::GetLifeRate (0x1B2390): auto-heal mLife & mLifeOld to mLifeMax on HUD/ratio query
def _build_hp_rate(cave):
    chk_pl = b"\xF6\x87\x48\x01\x00\x00\x03"        # test byte ptr [rdi+0x148], 3
    heal = (
        b"\x89\x87\xB0\x03\x00\x00"                 # mov [rdi+0x3b0], eax
        b"\x89\x87\xC0\x03\x00\x00"                 # mov [rdi+0x3c0], eax
    )
    pl_body = b"\x8B\x87\xB4\x03\x00\x00\x85\xC0" + _jcc_rel8(0x7E, heal)
    orig = b"\xC5\xFA\x2A\x87\xB0\x03\x00\x00"      # vcvtsi2ss xmm0, xmm0, [rdi+0x3b0]
    body = chk_pl + _jcc_rel8(0x74, pl_body) + orig
    return body + _calc_jump(cave + len(body), 0x1B2398, 5)


# 6d. Percentage HP drain guard (0x1B5C90): return 0 immediately if target is player
def _build_hp_pct(cave):
    chk_pl = b"\xF6\x87\x48\x01\x00\x00\x03"        # test byte ptr [rdi+0x148], 3
    early_ret = b"\x31\xC0\xC3"                     # xor eax, eax; ret
    orig = b"\xF6\x87\x49\x01\x00\x00\x42"          # test byte ptr [rdi+0x149], 0x42
    body = chk_pl + _jcc_rel8(0x74, early_ret) + orig
    return body + _calc_jump(cave + len(body), 0x1B5C97, 5)


_hp_set_hook = 0x1B2130
_hp_set_cave, _hp_set_cave_bytes = _alloc_cave(_build_hp_set)
_hp_set_hook_bytes = _calc_jump(_hp_set_hook, _hp_set_cave, 6)

_hp_add_hook = 0x1B2280
_hp_add_cave, _hp_add_cave_bytes = _alloc_cave(_build_hp_add)
_hp_add_hook_bytes = _calc_jump(_hp_add_hook, _hp_add_cave, 6)

_hp_rate_hook = 0x1B2390
_hp_rate_cave, _hp_rate_cave_bytes = _alloc_cave(_build_hp_rate)
_hp_rate_hook_bytes = _calc_jump(_hp_rate_hook, _hp_rate_cave, 8)

_hp_pct_hook = 0x1B5C90
_hp_pct_cave, _hp_pct_cave_bytes = _alloc_cave(_build_hp_pct)
_hp_pct_hook_bytes = _calc_jump(_hp_pct_hook, _hp_pct_cave, 7)

# 7. Infinite Basara & Boost (Iki / Sengoku Drive) Gauge
# 7a. cCharaStatus::SetBasaraGauge (0x1B2AE0): clamp new value esi = mBasaraMax ([rdi+0x3dc])
def _build_bsr_set(cave):
    chk_pl = b"\xF6\x87\x48\x01\x00\x00\x03"        # test byte ptr [rdi+0x148], 3
    pl_body = b"\x8B\x87\xDC\x03\x00\x00\x85\xC0" + _jcc_rel8(0x7E, b"\x89\xC6")
    orig = b"\x55\x48\x89\xE5\x41\x57"              # push rbp; mov rbp, rsp; push r15
    body = chk_pl + _jcc_rel8(0x74, pl_body) + orig
    return body + _calc_jump(cave + len(body), 0x1B2AE6, 5)


# 7b. cCharaStatus::AddBasaraGauge (0x1B2B70, called every frame in uPlayer::Update): keep gauge full
def _build_bsr_add(cave):
    chk_pl = b"\xF6\x87\x48\x01\x00\x00\x03"        # test byte ptr [rdi+0x148], 3
    set_full = (
        b"\x89\x87\xD8\x03\x00\x00"                 # mov [rdi+0x3d8], eax
        b"\x31\xF6"                                 # xor esi, esi
    )
    pl_body = b"\x8B\x87\xDC\x03\x00\x00\x85\xC0" + _jcc_rel8(0x7E, set_full)
    orig = b"\x55\x48\x89\xE5\x41\x57"              # push rbp; mov rbp, rsp; push r15
    body = chk_pl + _jcc_rel8(0x74, pl_body) + orig
    return body + _calc_jump(cave + len(body), 0x1B2B76, 5)


# 7c. sPlCtrl::UpdateVoltage Boost Gauge (0x74D81): fill P1 & P2 [r15+r14*4+0x654] = [r15+0x65c]
def _build_volt_gauge(cave):
    clr_neg = b"\x43\xC7\x84\xB7\xE4\x05\x00\x00\x00\x00\x00\x00"  # mov dword ptr [r15+r14*4+0x5e4], 0
    chk_delta = (
        b"\x43\x89\x84\xB7\x54\x06\x00\x00"         # mov [r15+r14*4+0x654], eax
        b"\x43\x83\xBC\xB7\xE4\x05\x00\x00\x00"     # cmp dword ptr [r15+r14*4+0x5e4], 0
    ) + _jcc_rel8(0x7D, clr_neg)                    # jge keep_pos_delta
    body = (
        b"\x41\x8B\x87\x5C\x06\x00\x00\x85\xC0"     # mov eax, [r15+0x65c]; test eax, eax
        + _jcc_rel8(0x7E, chk_delta)                # jle orig
        + b"\x43\x8B\x84\xB7\x54\x06\x00\x00"       # orig: mov eax, [r15+r14*4+0x654]
    )
    return body + _calc_jump(cave + len(body), 0x74D89, 5)


_bsr_set_hook = 0x1B2AE0
_bsr_set_cave, _bsr_set_cave_bytes = _alloc_cave(_build_bsr_set)
_bsr_set_hook_bytes = _calc_jump(_bsr_set_hook, _bsr_set_cave, 6)

_bsr_add_hook = 0x1B2B70
_bsr_add_cave, _bsr_add_cave_bytes = _alloc_cave(_build_bsr_add)
_bsr_add_hook_bytes = _calc_jump(_bsr_add_hook, _bsr_add_cave, 6)

_volt_gauge_hook = 0x74D81
_volt_gauge_cave, _volt_gauge_cave_bytes = _alloc_cave(_build_volt_gauge)
_volt_gauge_hook_bytes = _calc_jump(_volt_gauge_hook, _volt_gauge_cave, 8)


CHEATS = {
    "gold": {
        "name": "Max Gold (9,999,999) & Won't Decrease",
        "description": "Gold langsung menjadi 9.999.999 saat membuka Shop/Forge dan tidak berkurang saat belanja atau upgrade",
        "writes": (
            # Populate Gold to 9,999,999 immediately when opening Shop or Weapon Forge.
            _gold_shop_cave_w,
            (_gold_shop_hook_w[0], _gold_shop_hook_w[1], "8B80DC000000"),
            _gold_forge_cave_w,
            (_gold_forge_hook_w[0], _gold_forge_hook_w[1], "448BA8DC000000"),
            # Shop purchase: set ecx to 9,999,999 directly & skip negative clamp
            (0x529A86, "B97F9698009090", "412B8E70070000"),
            (0x529A8D, "90909090", "410F48CF"),
            # Weapon upgrade cost deduction: sub ecx, [rbx+0x84c] -> NOP
            (0x56950A, "909090909090", "2B8B4C080000"),
            # General spending deduction: sub esi, edx -> NOP
            (0x4EFDCC, "9090", "29D6"),
        ),
    },
    "special_coin": {
        "name": "Special Coin x999999 in Battle",
        "description": "Koin spesial (Tenka Medals) langsung menjadi 999.999 saat diperoleh di battle",
        "writes": (
            (_coin_cave, _coin_cave_bytes.hex(), "00" * len(_coin_cave_bytes)),
            (_coin_hook, _coin_hook_bytes.hex(), "F001B7E8020000"),
        ),
    },
    "growth_points": {
        "name": "Growth Points Max (999,999)",
        "description": "Poin pertumbuhan karakter (Inro) langsung 999.999 di Dojo, tidak berkurang, dan selalu lolos cek poin",
        "writes": (
            # Fill Growth Points to 999,999 immediately on entering Character Growth (Dojo).
            (0x4FEF28, "B83F420F0090", "8B80E0000000"),
            # Force every growth-point check to pass, even from 0.
            (0x502186, "39DB9090909090", "41399DB4060000"),
            (0x5021BA, "39DB9090909090", "41399DB4060000"),
            (0x502266, "B83F420F009090", "418B85B4060000"),
            (0x5022A1, "B83F420F009090", "418B85B4060000"),
            (0x502327, "B83F420F009090", "418B85B4060000"),
            # xor eax, eax; inc eax so jle after call 0x2e0b0 never fires even if eax had bit 31 set
            (0x50279E, "31C0FFC090909090", "4183BDB406000000"),
            # Deduction sites: force max points and skip the subtraction.
            (_growth_stat_cave, _growth_stat_cave_bytes.hex(), "00" * len(_growth_stat_cave_bytes)),
            (_growth_stat_hook, _growth_stat_hook_bytes.hex(), "412985B4060000"),
            (_growth_level_cave, _growth_level_cave_bytes.hex(), "00" * len(_growth_level_cave_bytes)),
            (_growth_level_hook, _growth_level_hook_bytes.hex(), "412985B4060000"),
        ),
    },
    "weapon_points": {
        "name": "Max Weapon Points (99,999)",
        "description": "Weapon Points (Toishi) otomatis terisi 99.999 di Weapon Forge dan tidak berkurang saat upgrade",
        "writes": (
            _wp_disp_cave_w,
            (_wp_disp_hook_w[0], _wp_disp_hook_w[1], "8B90E4000000"),
            (_wp_cave, _wp_cave_bytes.hex(), "00" * len(_wp_cave_bytes)),
            (_wp_hook, _wp_hook_bytes.hex(), "8981E4000000"),
        ),
    },
    "weapon_rank_points": {
        "name": "Max Weapon Rank Points (999)",
        "description": "Weapon Rank Points (Tamahagane) otomatis terisi 999 di Weapon Forge dan tidak berkurang saat upgrade",
        "writes": (
            _wrp_disp_cave_w,
            (_wrp_disp_hook_w[0], _wrp_disp_hook_w[1], "8B90E8000000"),
            (_wrp_cave, _wrp_cave_bytes.hex(), "00" * len(_wrp_cave_bytes)),
            (_wrp_hook, _wrp_hook_bytes.hex(), "8990E8000000"),
        ),
    },
    "infinite_health": {
        "name": "Infinite Health (Zero Damage & Auto-Heal)",
        "description": "Player 1 & Partner/2P tidak menerima damage dan HP selalu dipulihkan ke nilai maksimum",
        "writes": (
            (_hp_set_cave, _hp_set_cave_bytes.hex(), "00" * len(_hp_set_cave_bytes)),
            (_hp_add_cave, _hp_add_cave_bytes.hex(), "00" * len(_hp_add_cave_bytes)),
            (_hp_rate_cave, _hp_rate_cave_bytes.hex(), "00" * len(_hp_rate_cave_bytes)),
            (_hp_pct_cave, _hp_pct_cave_bytes.hex(), "00" * len(_hp_pct_cave_bytes)),
            (_hp_set_hook, _hp_set_hook_bytes.hex(), "8B87B4030000"),
            (_hp_add_hook, _hp_add_hook_bytes.hex(), "8B87B0030000"),
            (_hp_rate_hook, _hp_rate_hook_bytes.hex(), "C5FA2A87B0030000"),
            (_hp_pct_hook, _hp_pct_hook_bytes.hex(), "F6874901000042"),
        ),
    },
    "infinite_basara": {
        "name": "Infinite Basara & Boost Gauge",
        "description": "Basara Gauge dan Boost (Iki / Sengoku Drive) selalu penuh dan tidak habis saat dipakai (1P & 2P)",
        "writes": (
            (_bsr_set_cave, _bsr_set_cave_bytes.hex(), "00" * len(_bsr_set_cave_bytes)),
            (_bsr_add_cave, _bsr_add_cave_bytes.hex(), "00" * len(_bsr_add_cave_bytes)),
            (_volt_gauge_cave, _volt_gauge_cave_bytes.hex(), "00" * len(_volt_gauge_cave_bytes)),
            (_bsr_set_hook, _bsr_set_hook_bytes.hex(), "554889E54157"),
            (_bsr_add_hook, _bsr_add_hook_bytes.hex(), "554889E54157"),
            (_volt_gauge_hook, _volt_gauge_hook_bytes.hex(), "438B84B754060000"),
            # Keep active Boost timer [r15+0x5ec] at 0.0f while Boost is running (cutscene/end [r15+0x652] still stops cleanly)
            (0x750FD, "C5F857C09090909090", "C4C17A5887EC050000"),
        ),
    },
}


def normalize_selection(cheat_ids):
    if not isinstance(cheat_ids, (list, tuple)):
        raise ValueError("Cheat selection must be a list of cheat IDs")
    selected = list(cheat_ids)
    if any(not isinstance(cheat_id, str) for cheat_id in selected):
        raise ValueError("Cheat IDs must be text")
    if len(selected) != len(set(selected)):
        raise ValueError("Cheat selection contains duplicates")
    unknown = sorted(set(selected) - set(CHEATS))
    if unknown:
        raise ValueError(f"Unknown cheat selection: {', '.join(unknown)}")
    return selected


def validate_selection(cheat_ids):
    normalized = normalize_selection(cheat_ids)
    return normalized


def compile_cheats(selected_cheats, game_version="01.02", eboot_image=None, segments=None):
    normalized = validate_selection(selected_cheats)
    compiled_writes = []

    for cheat_id in normalized:
        cheat = CHEATS[cheat_id]
        for entry in cheat["writes"]:
            offset = entry[0]
            patch_hex = entry[1]
            orig_hex = entry[2] if len(entry) > 2 else ""

            patch_data = bytes.fromhex(patch_hex)
            orig_data = bytes.fromhex(orig_hex) if orig_hex else b""

            if eboot_image and orig_data:
                # eboot_image is the raw binary image payload (where vaddr 0 is at offset 0)
                actual = eboot_image[offset:offset + len(orig_data)]
                if actual != orig_data:
                    raise ValueError(
                        f"Cheat '{cheat['name']}' mismatch at 0x{offset:X}: "
                        f"expected {orig_hex}, got {actual.hex().upper()}"
                    )

            compiled_writes.append((offset, patch_data))

    return compiled_writes


# ==============================================================================
# Multi-Language Localization (ID, EN, JA, ZH, ES, PT, RU)
# ==============================================================================

CHEAT_UI_I18N = {
    "id": {
        "win_title": "Sengoku Basara 4 — Pengelola Cheat GoldHEN",
        "header": "⚔️ Cheat GoldHEN · CUSA01159 · Update 01.02",
        "subtitle": "Pilih cheat yang diinginkan. Seluruh patch memori v1.02 telah teruji aman tanpa crash.",
        "empty": "(Daftar cheat kosong)",
        "sel_all": "☑ Pilih Semua",
        "sel_none": "☐ Lepas Semua",
        "save": "💾 Simpan Cheat",
        "cancel": "Batal",
        "err_missing": "Modul cheats (basara4_cheats.py) tidak ditemukan!",
    },
    "en": {
        "win_title": "Sengoku Basara 4 — GoldHEN Cheats Manager",
        "header": "⚔️ GoldHEN Cheats · CUSA01159 · Update 01.02",
        "subtitle": "Select the cheats you want to enable. All v1.02 memory hooks are verified crash-free.",
        "empty": "(No cheats available)",
        "sel_all": "☑ Select All",
        "sel_none": "☐ Clear All",
        "save": "💾 Save Cheats",
        "cancel": "Cancel",
        "err_missing": "Cheats module (basara4_cheats.py) was not found!",
    },
    "ja": {
        "win_title": "戦国BASARA4 皇 — GoldHEN チート管理",
        "header": "⚔️ GoldHEN チート · CUSA01159 · Ver 01.02",
        "subtitle": "有効にしたいチートを選択してください。Ver 1.02 向けメモリパッチは安定動作を確認済みです。",
        "empty": "（利用可能なチートがありません）",
        "sel_all": "☑ すべて選択",
        "sel_none": "☐ すべて解除",
        "save": "💾 設定を保存",
        "cancel": "キャンセル",
        "err_missing": "チートモジュール (basara4_cheats.py) が見つかりません！",
    },
    "zh": {
        "win_title": "战国BASARA4 皇 — GoldHEN 金手指管理",
        "header": "⚔️ GoldHEN 金手指 · CUSA01159 · 版本 01.02",
        "subtitle": "勾选需要启用的金手指功能。所有 v1.02 内存补丁均已验证稳定不崩溃。",
        "empty": "（金手指列表为空）",
        "sel_all": "☑ 全选",
        "sel_none": "☐ 全不选",
        "save": "💾 保存设置",
        "cancel": "取消",
        "err_missing": "未找到金手指模块 (basara4_cheats.py)！",
    },
    "es": {
        "win_title": "Sengoku Basara 4 — Gestor de Trucos GoldHEN",
        "header": "⚔️ Trucos GoldHEN · CUSA01159 · Actualización 01.02",
        "subtitle": "Selecciona los trucos que deseas activar. Todos los parches v1.02 están verificados sin fallos.",
        "empty": "(Lista de trucos vacía)",
        "sel_all": "☑ Seleccionar todo",
        "sel_none": "☐ Limpiar todo",
        "save": "💾 Guardar trucos",
        "cancel": "Cancelar",
        "err_missing": "¡No se encontró el módulo de trucos (basara4_cheats.py)!",
    },
    "pt": {
        "win_title": "Sengoku Basara 4 — Gerenciador de Trapaças GoldHEN",
        "header": "⚔️ Trapaças GoldHEN · CUSA01159 · Atualização 01.02",
        "subtitle": "Selecione as trapaças desejadas. Todos os patches de memória v1.02 são seguros e sem travamentos.",
        "empty": "(Lista de trapaças vazia)",
        "sel_all": "☑ Marcar tudo",
        "sel_none": "☐ Desmarcar tudo",
        "save": "💾 Salvar trapaças",
        "cancel": "Cancelar",
        "err_missing": "Módulo de trapaças (basara4_cheats.py) não encontrado!",
    },
    "ru": {
        "win_title": "Sengoku Basara 4 — Менеджер читов GoldHEN",
        "header": "⚔️ Читы GoldHEN · CUSA01159 · Патч 01.02",
        "subtitle": "Выберите нужные читы. Все патчи памяти v1.02 проверены и работают без вылетов.",
        "empty": "(Список читов пуст)",
        "sel_all": "☑ Выбрать все",
        "sel_none": "☐ Снять все",
        "save": "💾 Сохранить читы",
        "cancel": "Отмена",
        "err_missing": "Модуль читов (basara4_cheats.py) не найден!",
    },
}

CHEAT_I18N = {
    "gold": {
        "id": (
            "Gold Maksimum (9.999.999) & Tidak Berkurang",
            "Gold langsung terisi 9.999.999 saat membuka Shop/Forge dan tidak berkurang saat belanja atau upgrade.",
        ),
        "en": (
            "Max Gold (9,999,999) & Never Decreases",
            "Instantly sets Gold to 9,999,999 when opening the Shop/Forge and prevents any deduction when buying or upgrading.",
        ),
        "ja": (
            "小判 MAX (9,999,999) ＆ 減少なし",
            "バサラ屋や鍛冶屋を開くと所持金が 9,999,999 両になり、買い物や強化をしても減りません。",
        ),
        "zh": (
            "金钱最大 (9,999,999) 且不减",
            "打开商店或锻造屋时金钱直接变为 9,999,999，购买物品与强化武器不消耗金钱。",
        ),
        "es": (
            "Oro Máximo (9,999,999) y No Disminuye",
            "Fija el oro en 9,999,999 al abrir la tienda/forja y evita que baje al comprar o mejorar.",
        ),
        "pt": (
            "Ouro Máximo (9.999.999) e Não Diminui",
            "Define o ouro para 9.999.999 ao abrir a loja/forja e impede qualquer gasto ao comprar ou melhorar.",
        ),
        "ru": (
            "Максимум золота (9 999 999) и без трат",
            "Мгновенно даёт 9 999 999 золота в магазине и кузнице; золото не тратится при покупках и улучшении.",
        ),
    },
    "special_coin": {
        "id": (
            "Koin Spesial (Tenka Medal) x999.999 di Pertempuran",
            "Tenka Medal langsung menjadi 999.999 begitu diperoleh saat bertarung.",
        ),
        "en": (
            "Special Coins (Tenka Medals) x999,999 in Battle",
            "Sets Tenka Medals directly to 999,999 as soon as you collect one in battle.",
        ),
        "ja": (
            "天貨メダル MAX (999,999)",
            "合戦中に天貨メダルを獲得すると即座に 999,999 枚になります。",
        ),
        "zh": (
            "战斗中天货通宝 x999,999",
            "在合战中获得天货通宝时，数量直接变为 999,999 枚。",
        ),
        "es": (
            "Monedas Especiales (Medallas Tenka) x999,999",
            "Aumenta las Medallas Tenka a 999,999 al obtenerlas en batalla.",
        ),
        "pt": (
            "Moedas Especiais (Medalhas Tenka) x999.999",
            "Define as Medalhas Tenka para 999.999 assim que obtidas em batalha.",
        ),
        "ru": (
            "Особые монеты (медали Тэнка) x999 999 в бою",
            "Сразу устанавливает 999 999 медалей Тэнка при получении монеты в сражении.",
        ),
    },
    "growth_points": {
        "id": (
            "Poin Pertumbuhan Karakter / Inro Maksimum (999.999)",
            "Poin Inro otomatis penuh 999.999 di Dojo, tidak berkurang, dan bisa dipakai meski dari 0.",
        ),
        "en": (
            "Max Growth Points / Inro (999,999)",
            "Fills Character Growth Points (Inro) to 999,999 in the Dojo, prevents deduction, and bypasses zero-point checks.",
        ),
        "ja": (
            "印籠（武将強化ポイント）MAX (999,999)",
            "道場で印籠が 999,999 になり、レベルアップやステータス強化をしても減りません。",
        ),
        "zh": (
            "印笼（武将成长点数）最大 (999,999)",
            "进入道场时印笼直接满 999,999，升级与强化属性不消耗点数。",
        ),
        "es": (
            "Puntos de Crecimiento / Inro al Máximo (999,999)",
            "Fija los puntos Inro en 999,999 en el Dojo y evita que disminuyan al subir de nivel o estadísticas.",
        ),
        "pt": (
            "Pontos de Crescimento / Inro no Máximo (999.999)",
            "Preenche os pontos Inro em 999.999 no Dojo e impede redução ao evoluir o personagem.",
        ),
        "ru": (
            "Максимум очков развития / Инро (999 999)",
            "Даёт 999 999 очков развития в Додзё и отключает их расход при прокачке уровня и характеристик.",
        ),
    },
    "weapon_points": {
        "id": (
            "Poin Senjata / Toishi Maksimum (99.999)",
            "Poin tempa senjata (Toishi) langsung penuh 99.999 di Weapon Forge dan tidak pernah berkurang.",
        ),
        "en": (
            "Max Weapon Points / Whetstones (99,999)",
            "Automatically sets Weapon Points (Toishi) to 99,999 in the Weapon Forge and prevents deduction on upgrade.",
        ),
        "ja": (
            "砥石（武器強化ポイント）MAX (99,999)",
            "武器強化画面で砥石が自動的に 99,999 になり、強化しても消費されません。",
        ),
        "zh": (
            "砥石（武器强化点数）最大 (99,999)",
            "在武器锻造界面自动拥有 99,999 砥石，强化武器时不消耗。",
        ),
        "es": (
            "Puntos de Arma / Piedras de Afilar al Máximo (99,999)",
            "Establece los puntos de arma (Toishi) en 99,999 en la forja y evita que bajen al mejorar.",
        ),
        "pt": (
            "Pontos de Arma / Amoladores no Máximo (99.999)",
            "Define os pontos de arma (Toishi) para 99.999 na forja e impede consumo ao melhorar.",
        ),
        "ru": (
            "Максимум очков оружия / Тоиси (99 999)",
            "Автоматически даёт 99 999 точильных камней (Тоиси) в кузнице без расхода при улучшении.",
        ),
    },
    "weapon_rank_points": {
        "id": (
            "Poin Rank Senjata / Tamahagane Maksimum (999)",
            "Material upgrade rank senjata (Tamahagane) otomatis terisi 999 di Weapon Forge dan tidak berkurang.",
        ),
        "en": (
            "Max Weapon Rank Points / Tamahagane (999)",
            "Automatically sets Weapon Rank Points (Tamahagane) to 999 in the Weapon Forge and prevents deduction.",
        ),
        "ja": (
            "玉鋼（レアリティ強化）MAX (999)",
            "武器強化画面で玉鋼が自動的に 999 個になり、段階強化をしても減りません。",
        ),
        "zh": (
            "玉钢（武器稀有度突破）最大 (999)",
            "在武器锻造界面自动拥有 999 玉钢，突破武器稀有度时不消耗。",
        ),
        "es": (
            "Puntos de Rango de Arma / Tamahagane al Máximo (999)",
            "Fija el Tamahagane en 999 en la forja de armas y evita que se gaste al subir el rango.",
        ),
        "pt": (
            "Pontos de Rank de Arma / Tamahagane no Máximo (999)",
            "Define o Tamahagane para 999 na forja de armas sem consumir ao evoluir a raridade.",
        ),
        "ru": (
            "Максимум очков ранга оружия / Тамахаганэ (999)",
            "Автоматически даёт 999 Тамахаганэ в кузнице и не тратит их при повышении ранга оружия.",
        ),
    },
    "infinite_health": {
        "id": (
            "Darah Kebal / Infinite HP (Tanpa Damage & Auto-Heal)",
            "Player 1, Partner Tag, dan Player 2 tidak menerima damage serta HP selalu dipulihkan penuh.",
        ),
        "en": (
            "Infinite Health (Zero Damage & Auto-Heal)",
            "Player 1, Tag Partner, and Player 2 take zero damage and automatically stay at full HP.",
        ),
        "ja": (
            "体力無限（ノーダメージ＆自動全快）",
            "1P・2P・戦友の受けるダメージを無効化し、体力を常に最大値に保ちます。",
        ),
        "zh": (
            "无限体力（无伤与自动回满）",
            "1P、2P 与战友免疫一切伤害，体力槽始终保持满值。",
        ),
        "es": (
            "Salud Infinita (Cero Daño y Autocuración)",
            "El Jugador 1, compañero y Jugador 2 no reciben daño y mantienen siempre la vida al máximo.",
        ),
        "pt": (
            "Vida Infinita (Zero Dano e Autocura)",
            "Jogador 1, parceiro e Jogador 2 não recebem dano e permanecem sempre com o HP cheio.",
        ),
        "ru": (
            "Бесконечное здоровье (без урона и автолечение)",
            "Игрок 1, напарник и Игрок 2 не получают урона, а шкала здоровья всегда остаётся полной.",
        ),
    },
    "infinite_basara": {
        "id": (
            "Basara & Boost Gauge Penuh Terus (Infinite Gauge)",
            "Gauge jurus Basara dan mode Iki / Sengoku Drive selalu penuh dan tidak habis dipakai (1P & 2P).",
        ),
        "en": (
            "Infinite Basara & Boost (Sengoku Drive) Gauge",
            "Keeps both Basara Gauge and Boost / Iki Gauge permanently full and active for 1P & 2P.",
        ),
        "ja": (
            "バサラ＆粋（戦国ドライブ）ゲージ無限",
            "1P・2Pのバサラゲージと粋の至りゲージが常に満タンになり、発動中も減りません。",
        ),
        "zh": (
            "无限 BASARA 与粹（战国驱动）气槽",
            "1P 与 2P 的 BASARA 技槽及粹之至气槽始终保持满值，开启后不会耗尽。",
        ),
        "es": (
            "Barra Basara e Impulso (Sengoku Drive) Infinitos",
            "Mantiene llenas las barras de Basara y Sengoku Drive sin agotarse para 1J y 2J.",
        ),
        "pt": (
            "Barra Basara e Boost (Sengoku Drive) Infinitos",
            "Mantém as barras de Basara e Sengoku Drive sempre cheias e sem acabar (1P e 2P).",
        ),
        "ru": (
            "Бесконечная шкала Басара и Усиления (Sengoku Drive)",
            "Шкалы Басара и усиления (Ики) всегда полны и не расходуются для 1-го и 2-го игроков.",
        ),
    },
}


def _norm_lang(lang):
    s = (lang or "id").strip().lower()
    for code in ("id", "en", "ja", "zh", "es", "pt", "ru"):
        if s.startswith(code):
            return code
    if s.startswith("in"):
        return "id"
    if s.startswith("jp"):
        return "ja"
    if s.startswith("cn"):
        return "zh"
    if s.startswith("br"):
        return "pt"
    return "en"


def get_cheat_text(cheat_id, lang="id"):
    """Return (localized_name, localized_description) for a cheat ID."""
    code = _norm_lang(lang)
    entry = CHEAT_I18N.get(cheat_id, {})
    if code in entry:
        return entry[code]
    if "en" in entry:
        return entry["en"]
    raw = CHEATS.get(cheat_id, {})
    return raw.get("name", cheat_id), raw.get("description", "")


def get_cheat_ui_text(key, lang="id"):
    """Return localized UI chrome text for the Cheats Manager window."""
    code = _norm_lang(lang)
    tbl = CHEAT_UI_I18N.get(code, CHEAT_UI_I18N["en"])
    return tbl.get(key) or CHEAT_UI_I18N["en"].get(key, key)
