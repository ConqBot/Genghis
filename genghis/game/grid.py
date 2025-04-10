import dataclasses
import re
import sys

import numpy
import numpy as np
from scipy.ndimage import maximum_filter

from __init__ import PLAYER_COLORS_HEX, TileType
from genghis.replays.deserialize import Replay, convert_coordinates, deserialize


def random_city_positions(number_cities, grid):
    available_positions = np.argwhere(grid.types == TileType.PLAIN)
    selected_indices = np.random.choice(len(available_positions), size=number_cities, replace=False)
    selected_positions = available_positions[selected_indices]
    return selected_positions

np.set_printoptions(threshold=np.inf, linewidth=np.inf)

@dataclasses.dataclass
class GridParameters:

    # random width/height
    min_width: int = None
    min_height: int = None
    max_width: int = None
    max_height: int = None

    # Parametric width/height
    width: int = None
    height: int = None

    # Random seed
    seed: int = None

    # Number of players
    num_players: int = None


    ### CITIES

    # City values
    minimum_city_value: int = 40
    maximum_city_value: int = 50

    # GIO city generation
    gio_city_density: float = None

    # Uniform generation
    uniform_city_density: float = None
    min_uniform_city_density: float = None
    max_uniform_city_density: float = None

    # Total number of cities (lower/upper bound)
    num_cities: int = None
    min_number_cities: int = None
    max_number_cities: int = None

    ### MOUNTAINS

    # GIO mountain generation
    gio_mountain_density: float = None

    # Uniform generation
    uniform_mountain_density: float = None
    min_uniform_mountain_density: float = None
    max_uniform_mountain_density: float = None

    # Total number of cities (lower/upper bound)
    num_mountains: int = None
    min_number_mountains: int = None
    max_number_mountains: int = None


    ### SWAMPS AND DESERTS (both replace normal tiles)

    # GIO swamp generation (replace normal tiles)
    gio_swamp_ratio: float = None

    # Total number of swamps (lower/upper bound)
    num_swamps: int = None
    min_number_swamps: int = None
    max_number_swamps: int = None

    # GIO desert generation (replace normal tiles)
    gio_desert_ratio: float = None

    # Total number of deserts (lower/upper bound)
    num_deserts: int = None
    min_number_deserts: int = None
    max_number_deserts: int = None

    ### LOOKOUTS AND OBSERVATORIES

    # TBA

    # Provide explicit general positions
    general_positions: list[tuple[int, int]] = None
    teams: list[list[int]] = None  # List of lists of player indices for teams. Will also tweak generals to spawn closer together. Conflicts with num_players
    # If not provided, assume a free for all

    ### FAIRNESS

    uniform_fairness: float = None


















class Grid:
    def __init__(self, min_width=None, min_height=None,
                 max_width=None, max_height=None,
                 width=None, height=None,
                 gio_city_density=None, gio_mountain_density=None, uniform_city_density=None, uniform_mountain_density=None,
                 general_positions=None, seed=None, players=None, minimum_city_value=40, maximum_city_value=50, minimum_manhattan=None):

        if seed is not None:
            numpy.random.seed(seed)
        assert (min_width is None and max_width is None) or (min_width is not None and max_width is not None),\
            "Either both or neither of min_width and max_width must be defined."
        assert (min_height is None and max_height is None) or (min_height is not None and max_height is not None),\
            "Either both or neither of min_height and max_height must be defined."

        if min_width is None:
            assert width is not None, "Width must be defined if min_width and max_width are None."
            self.width = width
        else:
            self.width = numpy.random.randint(min_width, max_width)

        if min_height is None:
            assert height is not None, "Height must be defined if min_height and max_height are None."
            self.height = height
        else:
            self.height = numpy.random.randint(min_height, max_height)

        if players is not None and general_positions is not None:
            assert len(general_positions) == players, "general_positions must have length players."
        if players is not None:
            self.num_players = players
        else:
            self.num_players = len(general_positions)

        self.city_boundaries = (minimum_city_value, maximum_city_value)

        self.types = np.full(self.dimensions, TileType.PLAIN, dtype=np.uint8)
        self.armies = np.full(self.dimensions, 0, dtype=np.uint16)
        self.owners = np.full(self.dimensions, -1, dtype=np.int8)
        self.lights = np.full(self.dimensions, False, dtype=np.bool)

        if minimum_manhattan is not None:
            self.minimum_general_distance_manhattan = minimum_manhattan
        else:
            self.minimum_general_distance_manhattan = 0


        def _calculate_num_cities_gio():
            return round(5 + (self.num_players * (2 + np.random.rand())))

        def _calculate_num_mountains_gio():
            return round(self.width * self.height * 0.2 + 0.08 * np.random.rand())

        def _calculate_num_cities_uniform():
            return round(uniform_city_density * self.width * self.height )

        def _calculate_num_mountains_uniform():
            return round(uniform_mountain_density * self.width * self.height)

        self._place_generals(self.num_players)

        if gio_city_density is not None:
            self._place_cities(_calculate_num_cities_gio())
        else:
            self._place_cities(_calculate_num_cities_uniform())

        if gio_mountain_density is not None:
            self._place_mountains(_calculate_num_mountains_gio())
        else:
            self._place_mountains(_calculate_num_mountains_uniform())

        self._place_swamps(3)

    @property
    def dimensions(self):
        return self.height, self.width


    def _place_swamps(self, num_swamps: int):
        available_positions = np.argwhere(self.types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_swamps, replace=False)
        selected_positions = available_positions[selected_indices]
        self.types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.SWAMP

    def _place_mountains(self, num_mountains: int) -> None:
        # mountain generation at 1.0: 116/396, 100/378, 95/360, 92/342
        available_positions = np.argwhere(self.types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_mountains, replace=False)
        selected_positions = available_positions[selected_indices]
        self.types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.MOUNTAIN

    def _place_cities(self, num_cities: int) -> None:
        available_positions = np.argwhere(self.types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_cities, replace=False)
        selected_positions = available_positions[selected_indices]
        self.types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.CITY
        self.armies[selected_positions[:, 0], selected_positions[:, 1]] = np.random.randint(low=self.city_boundaries[0],
                                                                                                  high=self.city_boundaries[1], size=num_cities)

    def _place_generals(self, num_generals: int) -> None:
        available_positions = np.argwhere(self.types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_generals, replace=False)
        selected_positions = available_positions[selected_indices]
        self.types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.GENERAL
        self.armies[selected_positions[:, 0], selected_positions[:, 1]] = 1
        self.owners[selected_positions[:, 0], selected_positions[:, 1]] = np.arange(len(selected_positions))
        return

    def _compute_vision_mask_traditional(self, player_index):
        return np.bool(maximum_filter(self.owners == player_index, size=3) | self.lights)

    def perspective(self, player_index):
        vision_mask = self._compute_vision_mask_traditional(player_index)
        owners = np.where(vision_mask, self.owners, -2)
        armies = np.where(vision_mask, self.armies, 0)

        terrain_rules = {  # How to convert invisible tiles
            TileType.GENERAL: TileType.PLAIN,
            TileType.DESERT: TileType.PLAIN,
            TileType.CITY: TileType.MOUNTAIN,
            TileType.OBSERVATORY: TileType.MOUNTAIN,
            TileType.LOOKOUT: TileType.MOUNTAIN

        }

        # Create arrays from dictionary
        original_types = np.array(list(terrain_rules.keys()))
        invisible_types = np.array(list(terrain_rules.values()))

        # Create a mask for all defined terrain types
        is_defined_type = np.isin(self.types, original_types)

        # Map terrain values to their invisible conversions
        # First, create an index mapping for each value
        type_indices = np.searchsorted(original_types, self.types)
        # Clip indices to valid range to avoid out-of-bounds
        type_indices = np.clip(type_indices, 0, len(original_types) - 1)

        # Get the converted values for all positions
        converted_values = invisible_types[type_indices]

        # Ensure only defined types get mapped correctly
        mapped_values = np.where(
            is_defined_type,
            converted_values,
            self.types  # Keep undefined types as original
        )

        # Final result: keep visible values, use converted values for invisible
        types = np.where(
            vision_mask,
            self.types,  # Keep original if visible
            mapped_values  # Use converted value if invisible
        )


    def __str__(self):
        # Define color functions and constants from LocalGame


        def color(index=None, hex=None):
            if index is not None:
                color_hex = PLAYER_COLORS_HEX[index]
                hexint = int(color_hex, 16)
            else:
                hexint = int(hex, 16)
            return "\x1B[38;2;{};{};{}m".format(hexint >> 16, hexint >> 8 & 0xFF, hexint & 0xFF)

        def end_color():
            return "\x1B[0m"

        # Use actual array dimensions
        height, width = self.types.shape

        # Helper to format a tile
        def format_tile(x, y):
            owner = self.owners[y, x]
            armies = self.armies[y, x]
            tile_type = TileType(self.types[y, x])
            if tile_type == TileType.MOUNTAIN:
                return owner, "MNT", armies
            elif tile_type == TileType.GENERAL:
                return owner, "G", armies
            elif tile_type == TileType.CITY:
                return owner, "C", armies
            elif tile_type == TileType.SWAMP:
                return owner, "S", armies
            elif tile_type == TileType.DESERT:
                return owner, "D", armies
            else:
                return owner, "", armies

        # Build the grid representation
        board_grid = []
        for y in range(height):
            row = [format_tile(x, y) for x in range(width)]
            board_grid.append(row)

        to_print_board = []
        to_print_colors = []
        for y in range(height):
            to_print_row = []
            to_print_color = []
            for x in range(width):
                owner = board_grid[y][x][0]
                if owner == -1:
                    to_print_color.append(color(hex="4b4b4b"))  # Gray for unowned
                else:
                    to_print_color.append(color(index=owner))

                add_to_print = ""
                if board_grid[y][x][1] and board_grid[y][x][2]:  # Type and army
                    add_to_print += f"\033[1m{board_grid[y][x][1]}/{board_grid[y][x][2]}\033[22m"
                elif board_grid[y][x][1]:  # Type only
                    add_to_print += board_grid[y][x][1]
                elif board_grid[y][x][2]:  # Army only
                    add_to_print += str(board_grid[y][x][2])

                to_print_row.append(add_to_print)
            to_print_board.append(to_print_row)
            to_print_colors.append(to_print_color)

        # Adapted _get_formatted_grid with corrected padding
        def get_formatted_grid(grid, colors):
            num_cols = max(len(row) for row in grid)
            col_widths = [0] * num_cols

            # Calculate maximum content width (excluding ANSI codes)
            def replace_ansi(thing):
                return re.sub(r'(\033|\x1b)\[[0-9;]*m', '', thing)

            for row in grid:
                for col, item in enumerate(row):
                    clean_item = replace_ansi(item)
                    col_widths[col] = max(col_widths[col], len(clean_item))


            # Column header with adjusted spacing
            col_header = " " * 4 + " " * col_widths[0]  # Space for row number column
            col_header += " ".join(f"{i:^{col_widths[i]}}  " for i in range(num_cols))

            result = col_header + "\n"

            # Format each row with proper padding
            for y, row in enumerate(grid):
                formatted_row = []
                for x, item in enumerate(row):
                    clean_item = replace_ansi(item)
                    # Pad content to content width, then wrap in brackets
                    padded_item = clean_item.ljust(col_widths[x])
                    formatted_item = f"{colors[y][x]}[{padded_item}]"
                    # Ensure total width by padding the entire cell if needed
                    formatted_item = formatted_item.ljust(col_widths[x])
                    formatted_row.append(formatted_item)
                result += f'{y:^3}| ' + " ".join(formatted_row) + end_color() + "\n"

            return result.rstrip()

        # Return the formatted grid as a string
        return f"Grid ({height}x{width}, {self.num_players} players)\n" + get_formatted_grid(to_print_board,
                                                                                             to_print_colors)

class ReplayGrid(Grid):
    def __init__(self, replay):

        self.replay = replay


        square_conversion = {TileType.CITY: replay.city_mask,
                             TileType.MOUNTAIN: replay.mountain_mask,
                             TileType.GENERAL: replay.general_mask}

        dimensions = replay.height, replay.width

        types = np.full(dimensions, TileType.PLAIN, dtype=np.uint8)
        armies = np.full(dimensions, 0, dtype=np.uint16)
        owners = np.full(dimensions, -1, dtype=np.int8)
        lights = np.full(dimensions, False, dtype=np.bool)

        for square_type in square_conversion.keys():
            types[square_conversion[square_type]] = square_type

        # Set initial army state
        split_city_mask = np.where(replay.city_mask)
        city_army_values = replay.city_army_mask[split_city_mask]  # 1D array of non-zero values
        city_mask_rows, city_mask_cols = split_city_mask
        armies[city_mask_rows, city_mask_cols] = city_army_values
        armies[replay.general_mask] = 1

        for player in replay.players:
            player_general_x, player_general_y = convert_coordinates(player.general, replay.width, replay.height)
            owners[player_general_x, player_general_y] = player.index

        self.num_players = np.sum(types == TileType.GENERAL)
        self.width = types.shape[1]
        self.height = types.shape[0]
        self.types = types
        self.armies = armies
        self.owners = owners
        self.lights = lights










