import pprint
import re

import numpy as np
from enum import Enum
import random
import time

from numba import njit

from __init__ import TileType
from genghis.game.move import Move
from grid import Grid

PLAYER_COLORS_HEX =["red:ff0000", "lightblue:2792FF", "green:008000", "teal:008080", "orange:FA8C01",
                    "pink:f032e6", "purple:800080", "maroon:9B0101", "yellow:B3AC32", "brown:9A5E24",
                    "blue:1031FF", "purpleblue:594CA5", "yellowgreen:85A91C", "lightred:FF6668",
                    "lightpurple:B47FCA", "lightbrown:B49971"]  # Ripped from gio.js

EFFECT_RECENT_MOVE_START_POSITION = "\033[51m"
EFFECT_RECENT_MOVE_END_POSITION = "\033[7m"
EFFECT_DISABLE_RECENT_MOVE = "\033[27m\033[54m"


def color(index=None, hex=None):
     if index is not None:
         color = PLAYER_COLORS_HEX[index].split(":")[1]
         hexint = int(color, 16)
     else:
         hexint = int(hex, 16)
     return "\x1B[38;2;{};{};{}m".format(hexint >> 16, hexint >> 8 & 0xFF, hexint & 0xFF)

def end_color():
    return "\x1B[0m"



class LocalGame:
    def __init__(self, grid: Grid):
        self.grid = grid
        self._turn = 0
        self.height = self.grid.height
        self.width = self.grid.width
        self.num_players = self.grid.num_players


        self.most_recent_start_move_squares = []
        self.most_recent_end_move_squares = []
        self.adjacent_indices = self._precompute_adjacents()
        self.priority_player = random.randint(0, self.grid.num_players - 1)



    def _precompute_adjacents(self):
        adjacents = np.full((self.height, self.width, 4, 2), -1, dtype=np.int16)
        directions = [(-1, 0), (0, 1), (1, 0), (0, -1)]

        for y in range(self.height):
            for x in range(self.width):
                for i, (dy, dx) in enumerate(directions):
                    new_y, new_x = y + dy, x + dx
                    if 0 <= new_x < self.width and 0 <= new_y < self.height:
                        adjacents[y, x, i] = [new_y, new_x]
        return adjacents



    @staticmethod
    @njit
    def _is_valid_move(start_x, start_y, end_x, end_y, player,
                       board_owners, board_armies, board_types):
        if (board_owners[start_x, start_y] != player or
                board_armies[start_x, start_y] < 2 or
                board_types[end_x, end_y] == TileType.MOUNTAIN.value):

            return False
        return True

    def generate_valid_moves(self, player):
        owned = self.grid.owners == player
        enough_armies = self.grid.armies >= 2
        valid_starts = np.where(owned & enough_armies)
        start_coords = list(zip(valid_starts[0], valid_starts[1]))
        if not start_coords:
            return []

        valid_moves = _generate_valid_moves_numba(
            player,
            np.array(start_coords, dtype=np.int16),
            self.adjacent_indices,
            self.grid.owners,
            self.grid.armies,
            self.grid.types
        )

        classified_valid_moves = []
        for move in valid_moves:
            classified_valid_moves.append(Move(move[0], False, move[1], move[2], move[3], move[4]))
        return classified_valid_moves

    @staticmethod
    @njit
    def _make_move(start_x, start_y, end_x, end_y, player, split,
                   board_armies, board_owners, board_types):
        if split:
            attack_armies = board_armies[start_x, start_y] // 2  # Split rounds down
        else:
            attack_armies = board_armies[start_x, start_y] - 1
        defend_armies = board_armies[end_x, end_y]
        is_attacking_same = board_owners[end_x, end_y] == player

        board_armies[start_x, start_y] -= attack_armies

        if is_attacking_same:
            board_armies[end_x, end_y] += attack_armies
        else:

            if attack_armies > defend_armies:
                board_armies[end_x, end_y] = attack_armies - defend_armies
                board_owners[end_x, end_y] = player
                if board_types[end_x, end_y] == TileType.GENERAL.value:  # If taking a general, they become a city.
                    board_types[end_x, end_y] = TileType.CITY.value
            elif attack_armies < defend_armies:
                board_armies[end_x, end_y] = defend_armies - attack_armies
            else:
                board_armies[end_x, end_y] = 0
                board_owners[end_x, end_y] = player
        return True

    def make_move(self, start_x, start_y, end_x, end_y, player, split):
        if not self._is_valid_move(start_x, start_y, end_x, end_y, player,
                                   self.grid.owners, self.grid.armies, self.grid.types):
            return False
        return self._make_move(start_x, start_y, end_x, end_y, player, split,
                               self.grid.armies, self.grid.owners, self.grid.types)



    def update_armies(self):
        # Flatten the arrays for indexing
        board_armies_flat = self.grid.armies.ravel()
        board_types_flat = self.grid.types.ravel()
        board_owners_flat = self.grid.owners.ravel()

        # Compute masks and get flat indices
        general_indices = np.where(board_types_flat == TileType.GENERAL.value)[0] if self._turn % 2 == 0 else np.array(
            [], dtype=np.int64)
        owned_indices = np.where((board_owners_flat != -1) & (board_types_flat != TileType.DESERT.value))[0]\
            if self._turn % 50 == 0 else np.array([], dtype=np.int64)
        city_owned_indices = np.where((board_types_flat == TileType.CITY.value) & (board_owners_flat != -1) & (self._turn % 2 == 0))[0]
        swamp_owned_indices = np.where((board_types_flat == TileType.SWAMP.value) & (board_owners_flat != -1))[0]
        # Update armies using Numba with indices


        for idx in owned_indices:  # Add 1 to all triggered army (if we are on the end of a round)
            board_armies_flat[idx] += 1
        # Update owned cities

        for idx in general_indices:
            board_armies_flat[idx] += 1

        for idx in city_owned_indices:
            board_armies_flat[idx] += 1

        # Decrement armies in swamp owned
        for idx in swamp_owned_indices:
            board_armies_flat[idx] -= 1

        # Find all swamp squares where there are 0 army and it is still "owned"
        swamp_zero_indices = np.where((board_types_flat == TileType.SWAMP.value) & (board_owners_flat != -1) & (board_armies_flat == 0))[0]

        for idx in swamp_zero_indices:  # Remove ownership from empty swamps
            board_owners_flat[idx] = -1




    def process_turn(self, moves=None):
        if moves is None:
            moves = []  # Everyone CAN pass if they want to

        current_priority = self.priority_player

        self.most_recent_start_move_squares = []
        self.most_recent_end_move_squares = []
        for _ in range(self.num_players):
            for move in moves:
                player_id, start_x, start_y, end_x, end_y, split = move.player_index, move.start[0], move.start[1], move.end[0], move.end[1], move.split

                if player_id == current_priority:
                    self.make_move(start_x, start_y, end_x, end_y, player_id, split)
                    self.most_recent_start_move_squares.append([start_y, start_x])
                    self.most_recent_end_move_squares.append([end_y, end_x])

            current_priority = (current_priority + 1) % self.num_players

        self.priority_player = (self.priority_player + 1) % self.num_players

        self._turn += 1
        self.update_armies()

    def _format_tile(self, x, y):
        owner = self.grid.owners[y, x]
        armies = self.grid.armies[y, x]
        tile_type = TileType(self.grid.types[y, x])
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

    def _get_formatted_grid(self, grid, colors):
        # Find the longest item in the grid to determine padding

        num_cols = max(len(row) for row in grid)
        col_widths = [0] * num_cols

        # Calculate maximum width needed for each column
        def replace_ansi(thing):
            return re.sub(r'(\033|\x1b)\[[0-9;]*m', '', thing)

        for row in grid:
            for col, item in enumerate(row):
                col_widths[col] = max(col_widths[col], len(str(replace_ansi(item))))
        col_header = " " * (4 + col_widths[0] // 2)  # Space for row number column

        col_header += " ".join(f"{i:^{col_widths[i]+1}} " for i in range(num_cols))
        print(col_header)


        return_value = ""
        # Print each row with padded item

        for y, row in enumerate(grid):
            # Create a formatted string for each item with consistent padding
            #formatted_row = [f"{colors[y][x]}[{str(item):<{max_length}}]" for x, item in enumerate(row)]
            def l(x, item):
                return col_widths[x]+(len(item)-len(replace_ansi(item)))
            def get_square_effect(x,y):
                if [x,y] in self.most_recent_start_move_squares:
                    return EFFECT_RECENT_MOVE_START_POSITION
                elif [x,y] in self.most_recent_end_move_squares:
                    return EFFECT_RECENT_MOVE_END_POSITION

                return ""
            formatted_row = [f"{colors[y][x]}{get_square_effect(x,y)}[{str(item):<{l(x, item)}}]{EFFECT_DISABLE_RECENT_MOVE}" for x, item in enumerate(row)]
            # Join all items in the row with a space
            return_value += f'{y:^3}| ' + " ".join(formatted_row) + end_color() + EFFECT_DISABLE_RECENT_MOVE + "\n"

        return return_value[:-1]

    def display_board(self):

        board_grid = []
        for y in range(self.height):
            row = [self._format_tile(x, y) for x in range(self.width)]
            board_grid.append(row)


        to_print_board = []
        to_print_colors = []
        for y in range(self.height):
            to_print_row = []
            to_print_color = []
            for x in range(self.width):

                owner = board_grid[y][x][0]
                if owner == -1:
                    to_print_color.append(color(hex="4b4b4b"))
                else:
                    to_print_color.append(color(index=owner))

                add_to_print = ""

                if board_grid[y][x][1] and board_grid[y][x][2]:  # If type enabled and army
                    add_to_print += f"\033[1m{board_grid[y][x][1]}/{board_grid[y][x][2]}\033[22m"
                elif board_grid[y][x][1]:
                    add_to_print += board_grid[y][x][1]
                elif board_grid[y][x][2]:
                    add_to_print += str(board_grid[y][x][2])



                to_print_row.append(add_to_print)
            to_print_board.append(to_print_row)
            to_print_colors.append(to_print_color)

        #pprint.pprint(to_print_board)
        print(self._get_formatted_grid(to_print_board, to_print_colors))



    def benchmark(self, num_turns=100, seed=42, display_every=None):
        print(f"\nRunning benchmark for {num_turns} turns with seed {seed}...")


        start_time = time.time()
        total_moves = 0
        for player in range(self.num_players):
            moves = self.generate_valid_moves(player)
            total_moves += len(moves)
        move_gen_time = time.time() - start_time
        print(f"Move generation for {self.num_players} players ({total_moves} moves): {move_gen_time:.4f} seconds")

        start_time = time.time()
        for turn in range(num_turns):
            if display_every is not None and turn % display_every == 0:
                print("\x1b[A"*27)
                self.display_board()
            moves = []
            for player in range(self.num_players):
                player_moves = self.generate_valid_moves(player)
                if player_moves:
                    random_move = np.random.randint(0, len(player_moves))
                    moves.append(player_moves[random_move])  # Instead of random.choice
            self.process_turn(moves)
        turn_process_time = time.time() - start_time
        print(f"Processed {num_turns} turns: {turn_process_time:.4f} seconds")
        print(f"Average time per turn: {turn_process_time / num_turns:.6f} seconds")

        return move_gen_time, turn_process_time

@njit
def _generate_valid_moves_numba(player, start_coords, adjacent_indices,
                                board_owners, board_armies, board_types):
    moves = []
    for i in range(len(start_coords)):
        start_y, start_x = start_coords[i]
        for j in range(4):
            end_y, end_x = adjacent_indices[start_x, start_y, j]
            if end_y == -1:
                continue
            if (board_owners[start_x, start_y] == player and
                    board_armies[start_x, start_y] >= 2 and
                    board_types[end_x, end_y] != TileType.MOUNTAIN.value):
                moves.append((player, start_x, start_y, end_x, end_y))
    return moves


if __name__ == "__main__":
    game = LocalGame(Grid(width=18, height=20, players=16, uniform_city_density=0.02, uniform_mountain_density=0.15))
    game.display_board()

    move_time, turn_time = game.benchmark(1000, 1000, 1)
    print("\nAfter benchmark:")
    game.display_board()