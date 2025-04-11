import time

import numpy as np
from line_profiler import profile
from numpy._typing import NDArray

from __init__ import TileType
from genghis.game.game import LocalGame
from genghis.game.grid import Grid
from genghis.replays.deserialize import Replay, convert_coordinates


class ReplayGrid(Grid):
    """Grid initialized from a replay object."""

    def __init__(self, replay: Replay):
        """
        Initialize grid from a replay.

        Args:
            replay: Replay object containing game state
        """
        self.replay = replay

        square_conversion = {
            TileType.CITY: replay.city_mask,
            TileType.MOUNTAIN: replay.mountain_mask,
            TileType.GENERAL: replay.general_mask
        }

        dimensions = (replay.height, replay.width)

        # Initialize grid arrays
        self.types: NDArray[np.uint8] = np.full(dimensions, TileType.PLAIN, dtype=np.uint8)
        self.armies: NDArray[np.uint16] = np.full(dimensions, 0, dtype=np.uint16)
        self.owners: NDArray[np.int8] = np.full(dimensions, -1, dtype=np.int8)
        self.lights: NDArray[np.bool] = np.full(dimensions, False, dtype=np.bool)

        # Set terrain types
        for square_type, mask in square_conversion.items():
            self.types[mask] = square_type

        # Set initial army values
        city_positions = np.where(replay.city_mask)
        self.armies[city_positions] = replay.city_army_mask[city_positions]
        self.armies[replay.general_mask] = 1

        # Set initial ownership
        for player in replay.players:
            x, y = convert_coordinates(player.general, replay.width, replay.height)
            self.owners[x, y] = player.index

        # Set grid properties
        self.num_players = np.sum(self.types == TileType.GENERAL)
        self.width = self.types.shape[1]
        self.height = self.types.shape[0]

class ReplayGame(LocalGame):
    def __init__(self, grid: ReplayGrid):
        super().__init__(grid)
        self.history = [(self.grid.types, self.grid.armies, self.grid.owners)]
        self._turn = 0



    @property
    def turn(self):
        return self._turn

    @turn.setter
    def turn(self, new_turn):
        # Ensure the new turn value is actually valid
        if not (type(new_turn) == int and new_turn >= 0):
            raise TypeError("Turn value must be an integer greater than 0")

        # If the turn we are requesting is 10, we need at least 11 items in the list
        if len(self.history) > new_turn:
            self.types, self.armies, self.owners = self.history[new_turn]
        else:  # We can't retrieve the cached gamestate, which means that we need to simulate forward
            simulator_types, simulator_armies, simulator_owners = self.history[-1]
            starting_turn = len(self.history) - 1  # The turn ID of the gamestate

            self._turn = starting_turn  # Set turn for move simulator
            moves = {}
            for move in self.grid.replay.moves:
                if move.turn not in moves:
                    moves[move.turn] = [move]
                else:
                    moves[move.turn].append(move)

            for turn in range(starting_turn, new_turn):
                if turn in moves:  # There is a move for this turn, pass em in
                    self.process_turn(moves[turn])
                    self.history.append((self.grid.types, self.grid.armies, self.grid.owners))
                else:
                    self.process_turn()
                    self.history.append((self.grid.types, self.grid.armies, self.grid.owners))





r = ReplayGrid(Replay(filename="../replays/vQKnym89k.gior"))
print(r)


r = ReplayGrid(Replay(filename="../replays/vQKnym89k.gior"))
print(r)

rg = ReplayGame(r)


print(rg.display_board())
t = time.time()
rg.turn = 95*2
print(rg.display_board())
print(time.time() - t)
