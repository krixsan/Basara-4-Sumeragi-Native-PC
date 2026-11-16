"""GoldHEN cheat data for Sengoku Basara 4 Sumeragi, CUSA01159 update 01.02.

NOTE: In-game cheats are currently DISABLED to prevent memory corruption / 0xC0000005
crash on update v1.02 (bad patch entry / write access fault).
FPS Limiter and Font Canary patches in basara4_patches.py remain 100% active and stable.
"""
import struct
import sys
from pathlib import Path

try:
    from basara4_dlc import _parse_sfo
except ImportError:
    try:
        from launcher.basara4_dlc import _parse_sfo
    except ImportError:
        def _parse_sfo(data):
            if len(data) < 20:
                raise ValueError("param.sfo is truncated")
            magic, _version, key_offset, data_offset, count = struct.unpack_from("<4sIIII", data)
            if magic != b"\0PSF" or count > 4096:
                raise ValueError("invalid param.sfo")
            values = {}
            for index in range(count):
                key_at, _format, length, _maximum, value_at = struct.unpack_from(
                    "<HHIII", data, 20 + index * 16)
                key_start = key_offset + key_at
                key_end = data.find(b"\0", key_start, data_offset)
                value_start = data_offset + value_at
                value_end = value_start + length
                if key_start >= data_offset or key_end < 0 or value_end > len(data):
                    raise ValueError("param.sfo entry is out of bounds")
                key = data[key_start:key_end].decode("utf-8", "replace")
                value = data[value_start:value_end].split(b"\0", 1)[0].decode("utf-8", "replace")
                values[key] = value
            return values

BASE_ADDRESS = 0x400000
SUPPORTED_VERSION = "01.02"
AUTHOR = "Q8Despair"
SOURCE_URL = "https://github.com/GoldHEN/GoldHEN_Cheat_Repository/blob/main/json/CUSA01159_01.02.json"

# ==============================================================================
# CHEAT DEFINITIONS (DISABLED: Incompatible hardcoded offsets causing 0xC0000005)
# ==============================================================================
# To re-enable in the future, accurate dynamic pattern signatures matching v1.02
# eboot segments must be used instead of static image cave offsets.
DISABLED_CHEATS = {
    "gold": {
        "name": "Gold Won't Decrease (Disabled on v1.02)",
        "writes": (
            (0x16BF800, "B89999990990E98CA226FF", "0000000000000000000000"),
            (0x929A91, "E96A5DD90090", "8988DC000000"),
        ),
    },
    "special_coin": {
        "name": "Special coin x99999 in battle (Disabled on v1.02)",
        "writes": (
            (0x12BF9E0, "C787E80200003F420F00E9C888D9FE", "000000000000000000000000000000"),
            (0x582B0, "E92B7726019090", "F001B7E8020000"),
        ),
    },
    "growth_points": {
        "name": "Growth points won't decrease x10 (Disabled on v1.02)",
        "writes": (
            (0x12BF800, "B89999990990E9D03024FF", "0000000000000000000000"),
            (0x5028D4, "E927CFDB009090", "412985B4060000"),
        ),
    },
    "weapon_points": {
        "name": "Weapon points won't decrease x10 (Disabled on v1.02)",
        "writes": (
            (0x12BF80D, "B89999090090E9B4172AFF", "0000000000000000000000"),
            (0x560FC6, "E942E8D50090", "8981E4000000"),
        ),
    },
    "weapon_rank_points": {
        "name": "Weapon rank points won't decrease (Disabled on v1.02)",
        "writes": (
            (0x12BF80D, "B89900000090E98FEE29FF", "0000000000000000000000"),
            (0x55E6A1, "E96711D60090", "8990E8000000"),
        ),
    },
}

# Active cheats dictionary is intentionally empty to protect memory stability
CHEATS = {}


def normalize_selection(cheat_ids):
    # Cheats are globally disabled on v1.02 to avoid bad patch entries
    return []


def validate_selection(cheat_ids):
    return []


def compile_cheats(cheat_ids, game_version, image, load_segments):
    # Returns 0 writes - completely safe from 0xC0000005 crash
    return []


def _allocate_caves(image, load_segments, lengths):
    return []


def game_version(game_dir):
    sfo_path = Path(game_dir) / "sce_sys" / "param.sfo"
    try:
        values = _parse_sfo(sfo_path.read_bytes())
    except (OSError, ValueError, struct.error) as error:
        raise ValueError(f"Cannot verify cheat compatibility from {sfo_path}: {error}") from error
    title_id = values.get("TITLE_ID")
    if title_id != "CUSA01159":
        raise ValueError(f"These cheats require CUSA01159; detected {title_id or 'unknown title'}")
    return values.get("APP_VER", "")


if __name__ == '__main__':
    print(f"Basara 4 GoldHEN Cheats Manager (CUSA01159 update {SUPPORTED_VERSION})")
    print(f"Author: {AUTHOR}")
    print(f"Status: In-game cheats currently DISABLED on v1.02 to prevent 0xC0000005 crash.")
    print(f"Active cheats ({len(CHEATS)}): none")
