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


def _calc_jump(from_addr, to_addr, hook_len=6):
    disp = to_addr - (from_addr + 5)
    return b"\xE9" + struct.pack("<i", disp) + b"\x90" * (hook_len - 5)


# ==============================================================================
# Verified Code Caves & Hooks for CUSA01159 v1.02 (Inside Segment 0: 0x0..0x12bd788)
# ==============================================================================

# Special Coin (Tenka Medals) x999,999 in Battle
_coin_hook = 0x582B0
_coin_cave = 0x106F600
_coin_hook_bytes = _calc_jump(_coin_hook, _coin_cave, 7)
# Cave: mov dword ptr [rdi+0x2e8], 999999 (0x0F423F) -> jmp back to 0x582B7
_coin_cave_bytes = bytes.fromhex("C787E80200003F420F00") + _calc_jump(_coin_cave + 10, _coin_hook + 7, 5)

# Weapon Points: Set to Max (629,145) on Upgrade
_wp_hook = 0x560FC6
_wp_cave = 0x106F620
_wp_hook_bytes = _calc_jump(_wp_hook, _wp_cave, 6)
# Cave: mov eax, 629145 (0x099999) -> mov [rcx+0xe4], eax -> jmp back to 0x560FCC
_wp_cave_bytes = bytes.fromhex("B8999909008981E4000000") + _calc_jump(_wp_cave + 11, _wp_hook + 6, 5)

# Weapon Rank Points: Set to Max (153) on Upgrade
_wrp_hook = 0x55E6A1
_wrp_cave = 0x106F640
_wrp_hook_bytes = _calc_jump(_wrp_hook, _wrp_cave, 6)
# Cave: mov edx, 153 (0x99) -> mov [rax+0xe8], edx -> jmp back to 0x55E6A7
_wrp_cave_bytes = bytes.fromhex("BA990000008990E8000000") + _calc_jump(_wrp_cave + 11, _wrp_hook + 6, 5)

# Infinite Health: Zero Damage Code Cave at 0x106F660
# Hook at 0x27D64A replaces vsubss (4b) + vmovss [r15+0x2560], xmm2 (9b) = 13 bytes
_hp_hook = 0x27D64A
_hp_cave = 0x106F660
_hp_hook_bytes = _calc_jump(_hp_hook, _hp_cave, 13)
# Cave instructions:
#   vxorps xmm0, xmm0, xmm0              (4 bytes: C5F857C0)
#   vsubss xmm2, xmm2, xmm0              (4 bytes: C5EA5CD0)
#   vmovss [r15+0x2560], xmm2            (9 bytes: C4C17A119760250000)
#   jmp back to 0x27D657                 (5 bytes: E9...)
_hp_cave_bytes = (
    bytes.fromhex("C5F857C0") +
    bytes.fromhex("C5EA5CD0") +
    bytes.fromhex("C4C17A119760250000") +
    _calc_jump(_hp_cave + 17, _hp_hook + 13, 5)
)


CHEATS = {
    "gold": {
        "name": "Max Gold (9,999,999) & Won't Decrease",
        "description": "Gold menjadi 9.999.999 saat belanja di shop dan tidak pernah berkurang saat upgrade",
        "writes": (
            # Shop purchase: set ecx to 9,999,999 directly
            (0x529A86, "B97F9698009090", "412B8E70070000"),
            # Shop purchase: NOP cmovs ecx, r15d so ecx is guaranteed 9,999,999
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
        "name": "Growth Points Won't Decrease",
        "description": "Poin pertumbuhan karakter (Inro) tidak berkurang saat upgrade level atau stats",
        "writes": (
            # Stat upgrade point deduction
            (0x5026D8, "90909090909090", "412985B4060000"),
            # Level upgrade point deduction
            (0x5028D4, "90909090909090", "412985B4060000"),
        ),
    },
    "weapon_points": {
        "name": "Max Weapon Points on Upgrade",
        "description": "Poin senjata langsung maksimal (629.145) saat melakukan upgrade senjata",
        "writes": (
            (_wp_cave, _wp_cave_bytes.hex(), "00" * len(_wp_cave_bytes)),
            (_wp_hook, _wp_hook_bytes.hex(), "8981E4000000"),
        ),
    },
    "weapon_rank_points": {
        "name": "Max Weapon Rank Points on Upgrade",
        "description": "Poin rank senjata langsung maksimal (153) saat melakukan upgrade rank",
        "writes": (
            (_wrp_cave, _wrp_cave_bytes.hex(), "00" * len(_wrp_cave_bytes)),
            (_wrp_hook, _wrp_hook_bytes.hex(), "8990E8000000"),
        ),
    },
    "infinite_health": {
        "name": "Infinite Health (Zero Damage Code Cave)",
        "description": "Karakter tidak menerima damage saat diserang (Damage di-zero-kan via Code Cave)",
        "writes": (
            (_hp_cave, _hp_cave_bytes.hex(), "00" * len(_hp_cave_bytes)),
            (_hp_hook, _hp_hook_bytes.hex(), "C5EA5CD0C4C17A119760250000"),
            (0x2875D0, "9090909090", "C5FA5C4328"),
            (0x266DC7, "9090909090", "C5FA5C4328"),
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
