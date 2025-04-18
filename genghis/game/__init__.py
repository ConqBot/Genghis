from enum import IntEnum


class TileType(IntEnum):
    FOG_OBSTACLE = -2
    FOG = -1
    PLAIN = 0
    MOUNTAIN = 1
    CITY = 2
    GENERAL = 3
    DESERT = 4
    SWAMP = 5
    LOOKOUT = 6
    OBSERVATORY = 7

PLAYER_COLORS_HEX = [
            "ff0000", "2792FF", "008000", "008080", "FA8C01",
            "f032e6", "800080", "9B0101", "B3AC32", "9A5E24",
            "1031FF", "594CA5", "85A91C", "FF6668",
            "B47FCA", "B49971"
        ]
EFFECT_RECENT_MOVE_START_POSITION = "\033[51m"
EFFECT_RECENT_MOVE_END_POSITION = "\033[7m"
EFFECT_DISABLE_RECENT_MOVE = "\033[27m\033[54m"