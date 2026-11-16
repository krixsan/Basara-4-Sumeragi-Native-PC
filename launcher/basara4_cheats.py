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
AUTHOR = "Q8Despair"
SOURCE_URL = "https://github.com/GoldHEN/GoldHEN_Cheat_Repository/blob/main/json/CUSA01159_01.02.json"


def _calc_jump(from_addr, to_addr, hook_len=6):
    disp = to_addr - (from_addr + 5)
    return b"\xE9" + struct.pack("<i", disp) + b"\x90" * (hook_len - 5)


# Verified Memory Patches for CUSA01159 v1.02:
# (v1.02 virtual addresses match eboot_image mapped segments; Segment 0 is 0x0 .. 0x12bd788).
_wp_hook = 0x560FC6
_wp_cave = 0x106F600
_wp_hook_bytes = _calc_jump(_wp_hook, _wp_cave, 6)
_wp_cave_bytes = bytes.fromhex("B8999909008981E4000000") + _calc_jump(_wp_cave + 11, _wp_hook + 6, 5)

_wrp_hook = 0x55E6A1
_wrp_cave = 0x106F620
_wrp_hook_bytes = _calc_jump(_wrp_hook, _wrp_cave, 6)
_wrp_cave_bytes = bytes.fromhex("BA990000008990E8000000") + _calc_jump(_wrp_cave + 11, _wrp_hook + 6, 5)

CHEATS = {
    "gold": {
        "name": "Gold Won't Decrease",
        "description": "Gold tidak berkurang saat membeli senjata/item di shop",
        "writes": (
            (0x529A86, "90909090909090", "412B8E70070000"),
        ),
    },
    "special_coin": {
        "name": "Special Coin x99999 in Battle",
        "description": "Koin spesial langsung menjadi 999.999 saat didapatkan di battle",
        "writes": (
            (0x582C1, "9090", "7C0E"),
        ),
    },
    "growth_points": {
        "name": "Growth Points Won't Decrease",
        "description": "Poin pertumbuhan karakter tidak berkurang saat upgrade level/stats",
        "writes": (
            (0x5028D4, "90909090909090", "412985B4060000"),
        ),
    },
    "weapon_points": {
        "name": "Max Weapon Points on Upgrade",
        "description": "Poin senjata langsung maksimal (629.145) saat upgrade",
        "writes": (
            (_wp_cave, _wp_cave_bytes.hex(), "00" * len(_wp_cave_bytes)),
            (_wp_hook, _wp_hook_bytes.hex(), "8981E4000000"),
        ),
    },
    "weapon_rank_points": {
        "name": "Max Weapon Rank Points on Upgrade",
        "description": "Poin rank senjata langsung maksimal (153) saat upgrade rank",
        "writes": (
            (_wrp_cave, _wrp_cave_bytes.hex(), "00" * len(_wrp_cave_bytes)),
            (_wrp_hook, _wrp_hook_bytes.hex(), "8990E8000000"),
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
    return normalize_selection(cheat_ids)


def compile_cheats(cheat_ids, game_version, image, load_segments):
    selected = validate_selection(cheat_ids)
    if not selected:
        return []
    if game_version and game_version != SUPPORTED_VERSION:
        raise ValueError(
            f"These cheats require game update {SUPPORTED_VERSION}; detected {game_version or 'unknown'}")

    writes = []
    for cheat_id in selected:
        cheat = CHEATS[cheat_id]
        for offset, patch_hex, expected_hex in cheat["writes"]:
            expected = bytes.fromhex(expected_hex)
            patch_data = bytes.fromhex(patch_hex)

            # Verification against image
            if offset + len(expected) <= len(image):
                actual = image[offset:offset + len(expected)]
                if actual != expected:
                    raise ValueError(
                        f"Cheat '{cheat['name']}' mismatch at offset {offset:#x}: "
                        f"expected {expected.hex()}, found {actual.hex()}")

            # Check that offset is within load_segments
            if load_segments:
                is_mapped = any(
                    addr <= offset and (offset + len(patch_data)) <= (addr + size)
                    for addr, size, flags in load_segments
                )
                if not is_mapped:
                    raise ValueError(
                        f"Cheat '{cheat['name']}' target {offset:#x} is outside mapped load segments")

            writes.append((offset, patch_data))

    writes.sort(key=lambda w: w[0])
    for prev, curr in zip(writes, writes[1:]):
        if curr[0] < prev[0] + len(prev[1]):
            raise ValueError("The selected cheat patches overlap in memory")

    return writes


def game_version(game_dir):
    sfo_path = Path(game_dir) / "sce_sys" / "param.sfo"
    if not sfo_path.is_file():
        return SUPPORTED_VERSION
    try:
        values = _parse_sfo(sfo_path.read_bytes())
        return values.get("APP_VER", SUPPORTED_VERSION)
    except Exception:
        return SUPPORTED_VERSION
