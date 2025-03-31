from enum import IntEnum

import numpy
import numpy as np


class TileType(IntEnum):
    PLAIN = 0
    MOUNTAIN = 1
    CITY = 2
    GENERAL = 3

np.set_printoptions(linewidth=np.inf)
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

        self._grid_types = np.full(self.dimensions, TileType.PLAIN, dtype=np.uint8)
        self._grid_armies = np.full(self.dimensions, 0, dtype=np.uint16)
        self._grid_owners = np.full(self.dimensions, -1, dtype=np.int8)

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
        print(self._grid_armies)
        print(self._grid_types)

    @property
    def dimensions(self):
        return self.width, self.height



    def _place_mountains(self, num_mountains: int) -> None:
        # mountain generation at 1.0: 116/396, 100/378, 95/360, 92/342
        available_positions = np.argwhere(self._grid_types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_mountains, replace=False)
        selected_positions = available_positions[selected_indices]
        self._grid_types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.MOUNTAIN

    def _place_cities(self, num_cities: int) -> None:
        available_positions = np.argwhere(self._grid_types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_cities, replace=False)
        selected_positions = available_positions[selected_indices]
        self._grid_types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.CITY
        self._grid_armies[selected_positions[:, 0], selected_positions[:, 1]] = np.random.randint(low=self.city_boundaries[0],
                                                                                                  high=self.city_boundaries[1], size=num_cities)

    def _place_generals(self, num_generals: int) -> None:
        available_positions = np.argwhere(self._grid_types == TileType.PLAIN)
        selected_indices = np.random.choice(len(available_positions), size=num_generals, replace=False)
        selected_positions = available_positions[selected_indices]
        self._grid_types[selected_positions[:, 0], selected_positions[:, 1]] = TileType.GENERAL
        self._grid_armies[selected_positions[:, 0], selected_positions[:, 1]] = 1
        return



g = Grid(width=25, height=25, players=2, uniform_city_density=0.02, uniform_mountain_density=0.3)