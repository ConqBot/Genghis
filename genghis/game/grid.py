import dataclasses
import re
import sys
from typing import List, Tuple, Optional, Dict

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import maximum_filter

from __init__ import PLAYER_COLORS_HEX, TileType
from genghis.replays.deserialize import Replay, convert_coordinates, deserialize


def random_city_positions(number_cities: int, grid: 'Grid') -> NDArray[np.int64]:
    """
    Generate random positions for cities on the grid.

    Args:
        number_cities: Number of cities to place
        grid: Grid object containing tile types

    Returns:
        Array of shape (number_cities, 2) containing [y, x] coordinates
    """
    available_positions = np.argwhere(grid.types == TileType.PLAIN)
    selected_indices = np.random.choice(len(available_positions), size=number_cities, replace=False)
    return available_positions[selected_indices]


# Configure numpy printing options
np.set_printoptions(threshold=np.inf, linewidth=np.inf)


@dataclasses.dataclass
class GridParameters:
    """Parameters for configuring grid generation."""

    # Grid dimensions (random range)
    min_width: Optional[int] = None
    min_height: Optional[int] = None
    max_width: Optional[int] = None
    max_height: Optional[int] = None

    # Fixed grid dimensions
    width: Optional[int] = None
    height: Optional[int] = None

    # Random seed for reproducibility
    seed: Optional[int] = None

    # Number of players
    num_players: Optional[int] = None

    # City configuration
    minimum_city_value: int = 40
    maximum_city_value: int = 50
    gio_city_density: Optional[float] = None
    uniform_city_density: Optional[float] = None
    min_uniform_city_density: Optional[float] = None
    max_uniform_city_density: Optional[float] = None
    num_cities: Optional[int] = None
    min_number_cities: Optional[int] = None
    max_number_cities: Optional[int] = None

    # Mountain configuration
    gio_mountain_density: Optional[float] = None
    uniform_mountain_density: Optional[float] = None
    min_uniform_mountain_density: Optional[float] = None
    max_uniform_mountain_density: Optional[float] = None
    num_mountains: Optional[int] = None
    min_number_mountains: Optional[int] = None
    max_number_mountains: Optional[int] = None

    # Swamp configuration
    gio_swamp_ratio: Optional[float] = None
    num_swamps: Optional[int] = None
    min_number_swamps: Optional[int] = None
    max_number_swamps: Optional[int] = None

    # Desert configuration
    gio_desert_ratio: Optional[float] = None
    num_deserts: Optional[int] = None
    min_number_deserts: Optional[int] = None
    max_number_deserts: Optional[int] = None

    # Player positioning
    general_positions: Optional[List[Tuple[int, int]]] = None
    teams: Optional[List[List[int]]] = None  # List of player indices for teams

    # Fairness parameter
    uniform_fairness: Optional[float] = None


class Grid:
    """Represents a game grid with terrain, armies, and ownership."""

    def __init__(self,
                 min_width: Optional[int] = None,
                 min_height: Optional[int] = None,
                 max_width: Optional[int] = None,
                 max_height: Optional[int] = None,
                 width: Optional[int] = None,
                 height: Optional[int] = None,
                 gio_city_density: Optional[float] = None,
                 gio_mountain_density: Optional[float] = None,
                 uniform_city_density: Optional[float] = None,
                 uniform_mountain_density: Optional[float] = None,
                 general_positions: Optional[List[Tuple[int, int]]] = None,
                 seed: Optional[int] = None,
                 players: Optional[int] = None,
                 minimum_city_value: int = 40,
                 maximum_city_value: int = 50,
                 minimum_manhattan: Optional[int] = None):
        """
        Initialize a new game grid.

        Args:
            min_width: Minimum grid width (if random)
            min_height: Minimum grid height (if random)
            max_width: Maximum grid width (if random)
            max_height: Maximum grid height (if random)
            width: Fixed grid width
            height: Fixed grid height
            gio_city_density: Density for GIO city generation
            gio_mountain_density: Density for GIO mountain generation
            uniform_city_density: Density for uniform city generation
            uniform_mountain_density: Density for uniform mountain generation
            general_positions: List of specific general positions
            seed: Random seed for reproducibility
            players: Number of players
            minimum_city_value: Minimum army value for cities
            maximum_city_value: Maximum army value for cities
            minimum_manhattan: Minimum Manhattan distance between generals
        """
        if seed is not None:
            np.random.seed(seed)

        # Validate width/height parameters
        assert (min_width is None and max_width is None) or \
               (min_width is not None and max_width is not None), \
            "Either both or neither of min_width and max_width must be defined."
        assert (min_height is None and max_height is None) or \
               (min_height is not None and max_height is not None), \
            "Either both or neither of min_height and max_height must be defined."

        # Set grid dimensions
        self.width = width if min_width is None else np.random.randint(min_width, max_width)
        self.height = height if min_height is None else np.random.randint(min_height, max_height)

        # Validate and set player count
        if players is not None and general_positions is not None:
            assert len(general_positions) == players, "general_positions must have length players."
        self.num_players = players if players is not None else len(general_positions)

        self.city_boundaries = (minimum_city_value, maximum_city_value)
        self.minimum_general_distance_manhattan = minimum_manhattan if minimum_manhattan is not None else 0

        # Initialize grid arrays
        self.types: NDArray[np.uint8] = np.full(self.dimensions, TileType.PLAIN, dtype=np.uint8)
        self.armies: NDArray[np.int64] = np.full(self.dimensions, 0, dtype=np.int64)
        self.owners: NDArray[np.int8] = np.full(self.dimensions, -1, dtype=np.int8)
        self.lights: NDArray[np.bool] = np.full(self.dimensions, False, dtype=np.bool)

        # Local helper functions for quantity calculations
        def _calculate_num_cities_gio() -> int:
            return round(5 + (self.num_players * (2 + np.random.rand())))

        def _calculate_num_mountains_gio() -> int:
            return round(self.width * self.height * 0.2 + 0.08 * np.random.rand())

        def _calculate_num_cities_uniform() -> int:
            return round(uniform_city_density * self.width * self.height)

        def _calculate_num_mountains_uniform() -> int:
            return round(uniform_mountain_density * self.width * self.height)

        # Place terrain features
        self._place_generals(self.num_players)
        self._place_cities(_calculate_num_cities_gio() if gio_city_density is not None
                           else _calculate_num_cities_uniform())
        self._place_mountains(_calculate_num_mountains_gio() if gio_mountain_density is not None
                              else _calculate_num_mountains_uniform())
        self._place_swamps(3)

    @property
    def dimensions(self) -> Tuple[int, int]:
        """Return grid dimensions as (height, width)."""
        return self.height, self.width

    def _place_swamps(self, num_swamps: int) -> None:
        """
        Place swamp tiles on the grid.

        Args:
            num_swamps: Number of swamp tiles to place
        """
        available_positions = np.argwhere(self.types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_swamps, replace=False)
        selected_positions = available_positions[selected_indices]
        self.types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.SWAMP

    def _place_mountains(self, num_mountains: int) -> None:
        """
        Place mountain tiles on the grid.

        Args:
            num_mountains: Number of mountain tiles to place
        """
        available_positions = np.argwhere(self.types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_mountains, replace=False)
        selected_positions = available_positions[selected_indices]
        self.types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.MOUNTAIN

    def _place_cities(self, num_cities: int) -> None:
        """
        Place city tiles with random army values on the grid.

        Args:
            num_cities: Number of city tiles to place
        """
        available_positions = np.argwhere(self.types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_cities, replace=False)
        selected_positions = available_positions[selected_indices]
        self.types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.CITY
        self.armies[selected_positions[:, 0], selected_positions[:, 1]] = np.random.randint(
            low=self.city_boundaries[0],
            high=self.city_boundaries[1],
            size=num_cities
        )

    def _place_generals(self, num_generals: int) -> None:
        """
        Place general tiles with initial army values and ownership.

        Args:
            num_generals: Number of general tiles to place
        """
        available_positions = np.argwhere(self.types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_generals, replace=False)
        selected_positions = available_positions[selected_indices]
        self.types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.GENERAL
        self.armies[selected_positions[:, 0], selected_positions[:, 1]] = 1
        self.owners[selected_positions[:, 0], selected_positions[:, 1]] = np.arange(len(selected_positions))

    def _compute_vision_mask_traditional(self, player_index: int) -> NDArray[np.bool]:
        """
        Compute visibility mask for a player.

        Args:
            player_index: Index of the player to compute vision for

        Returns:
            Boolean array indicating visible tiles
        """
        return np.bool(maximum_filter(self.owners == player_index, size=3) | self.lights)

    def perspective(self, player_index: int) -> None:
        """
        Calculate player's perspective of the grid (incomplete implementation).

        Args:
            player_index: Index of the player to compute perspective for
        """
        vision_mask = self._compute_vision_mask_traditional(player_index)
        owners = np.where(vision_mask, self.owners, -2)
        armies = np.where(vision_mask, self.armies, 0)

        terrain_rules: Dict[TileType, TileType] = {
            TileType.GENERAL: TileType.PLAIN,
            TileType.DESERT: TileType.PLAIN,
            TileType.CITY: TileType.MOUNTAIN,
            TileType.OBSERVATORY: TileType.MOUNTAIN,
            TileType.LOOKOUT: TileType.MOUNTAIN
        }

        original_types = np.array(list(terrain_rules.keys()))
        invisible_types = np.array(list(terrain_rules.values()))
        is_defined_type = np.isin(self.types, original_types)
        type_indices = np.searchsorted(original_types, self.types)
        type_indices = np.clip(type_indices, 0, len(original_types) - 1)
        converted_values = invisible_types[type_indices]
        mapped_values = np.where(is_defined_type, converted_values, self.types)

        types = np.where(
            vision_mask,
            self.types,  # Keep original if visible
            mapped_values  # Use converted value if invisible
        )

    def __str__(self) -> str:
        """Return a formatted string representation of the grid."""

        def color(index: Optional[int] = None, hex: Optional[str] = None) -> str:
            """
            Generate ANSI color code from index or hex value.

            Args:
                index: Player index for color lookup
                hex: Hex color code

            Returns:
                ANSI escape sequence for the color
            """
            if index is not None:
                color_hex = PLAYER_COLORS_HEX[index]
                hexint = int(color_hex, 16)
            else:
                hexint = int(hex, 16)
            return f"\x1B[38;2;{hexint >> 16};{hexint >> 8 & 0xFF};{hexint & 0xFF}m"

        def end_color() -> str:
            """Return ANSI code to reset color."""
            return "\x1B[0m"

        def replace_ansi(thing: str) -> str:
            """
            Remove ANSI escape sequences from a string.

            Args:
                thing: String containing potential ANSI codes

            Returns:
                String with ANSI codes removed
            """
            return re.sub(r'(\033|\x1b)\[[0-9;]*m', '', thing)

        height, width = self.types.shape

        def format_tile(x: int, y: int) -> Tuple[int, str, int]:
            """
            Format a single tile's representation.

            Args:
                x: X-coordinate of the tile
                y: Y-coordinate of the tile

            Returns:
                Tuple of (owner, symbol, armies)
            """
            owner = self.owners[y, x]
            armies = self.armies[y, x]
            tile_type = TileType(self.types[y, x])
            tile_symbols = {
                TileType.MOUNTAIN: "MNT",
                TileType.GENERAL: "G",
                TileType.CITY: "C",
                TileType.SWAMP: "S",
                TileType.DESERT: "D"
            }
            return owner, tile_symbols.get(tile_type, ""), armies

        # Build grid representation
        board_grid = [[format_tile(x, y) for x in range(width)] for y in range(height)]
        to_print_board = []
        to_print_colors = []

        for y in range(height):
            row = []
            colors = []
            for x in range(width):
                owner = board_grid[y][x][0]
                colors.append(color(hex="4b4b4b") if owner == -1 else color(index=owner))

                symbol, armies = board_grid[y][x][1], board_grid[y][x][2]
                if symbol and armies:
                    row.append(f"\033[1m{symbol}/{armies}\033[22m")
                elif symbol:
                    row.append(symbol)
                elif armies:
                    row.append(str(armies))
                else:
                    row.append("")
            to_print_board.append(row)
            to_print_colors.append(colors)

        def get_formatted_grid(grid: List[List[str]], colors: List[List[str]]) -> str:
            """
            Format the grid with proper spacing and colors.

            Args:
                grid: 2D list of tile strings
                colors: 2D list of color codes

            Returns:
                Formatted string representation of the grid
            """
            num_cols = max(len(row) for row in grid)
            col_widths = [0] * num_cols
            for row in grid:
                for col, item in enumerate(row):
                    clean_item = replace_ansi(item)
                    col_widths[col] = max(col_widths[col], len(clean_item))

            col_header = " " * 4 + " " * col_widths[0]
            col_header += " ".join(f"{i:^{col_widths[i]}}  " for i in range(num_cols))
            result = col_header + "\n"

            for y, (row, color_row) in enumerate(zip(grid, colors)):
                formatted_row = [
                    f"{color_row[x]}[{item.ljust(col_widths[x])}]"
                    for x, item in enumerate(row)
                ]
                result += f'{y:^3}| ' + " ".join(formatted_row) + end_color() + "\n"

            return result.rstrip()

        return f"Grid ({height}x{width}, {self.num_players} players)\n" + \
            get_formatted_grid(to_print_board, to_print_colors)


