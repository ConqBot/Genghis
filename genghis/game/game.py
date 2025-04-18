import numpy as np
from enum import Enum
import random
import time
from numba import njit, prange
from line_profiler import profile
import re
from __init__ import EFFECT_DISABLE_RECENT_MOVE, EFFECT_RECENT_MOVE_END_POSITION, EFFECT_RECENT_MOVE_START_POSITION, \
    PLAYER_COLORS_HEX, TileType
from genghis.game.move import Move
from grid import Grid


def color(index=None, hex=None):
    if index is not None:
        color = PLAYER_COLORS_HEX[index]
        hexint = int(color, 16)
    else:
        hexint = int(hex, 16)
    return "\x1B[38;2;{};{};{}m".format(hexint >> 16, hexint >> 8 & 0xFF, hexint & 0xFF)


def end_color():
    return "\x1B[0m"


@njit
def _precompute_adjacents(height, width):
    adjacents = np.full((height * width * 4, 2), -1, dtype=np.int16)
    directions = [(-1, 0), (0, 1), (1, 0), (0, -1)]  # (dy, dx)

    for y in prange(height):
        for x in prange(width):
            base_idx = (y * width + x) * 4
            for i, (dy, dx) in enumerate(directions):
                new_y, new_x = y + dy, x + dx
                if 0 <= new_x < width and 0 <= new_y < height:
                    adjacents[base_idx + i] = [new_y, new_x]
    return adjacents


@njit
def _execute_move(move, owners, armies, types, height, width):
    player, start_y, start_x, end_y, end_x, split = move
    start_idx = start_y * width + start_x
    end_idx = end_y * width + end_x

    attack_armies = armies[start_idx] // 2 if split else armies[start_idx] - 1
    defend_armies = armies[end_idx]
    is_attacking_same = owners[end_idx] == player
    captured_general = -1

    armies[start_idx] -= attack_armies

    if is_attacking_same:
        armies[end_idx] += attack_armies
    else:
        if attack_armies > defend_armies:
            armies[end_idx] = attack_armies - defend_armies
            if types[end_idx] == TileType.GENERAL.value:
                types[end_idx] = TileType.CITY.value
                captured_general = owners[end_idx]
            owners[end_idx] = player
        elif attack_armies < defend_armies:
            armies[end_idx] = defend_armies - attack_armies
        else:
            armies[end_idx] = 0  # Ownership DOES not change

    return captured_general


class LocalGame:
    def __init__(self, grid: Grid):
        self.grid = grid
        self._turn = 0
        self.height = grid.height
        self.width = grid.width
        self.num_players = grid.num_players
        self.max_moves_per_turn = self.height * self.width
        self.moves_buffer = np.zeros((self.max_moves_per_turn, 6),
                                    dtype=np.int16)  # [player, start_y, start_x, end_y, end_x, split]
        self.move_counts = np.zeros(self.num_players, dtype=np.int32)
        self.adjacent_indices = _precompute_adjacents(self.height, self.width)
        self.priority_player = random.randint(0, self.num_players - 1)
        self.owners_flat = self.grid.owners.ravel()
        self.armies_flat = self.grid.armies.ravel()
        self.types_flat = self.grid.types.ravel()
        self.most_recent_start_move_squares = []
        self.most_recent_end_move_squares = []

    @staticmethod
    @njit
    def _generate_and_validate_moves(player, start_coords, adjacent_indices,
                                    owners, armies, types, moves_buffer, height, width):
        move_count = 0
        n_starts = len(start_coords)
        idx_base = 0

        for i in prange(n_starts):
            start_y, start_x = start_coords[i]
            idx_base = (start_y * width + start_x) * 4
            if owners[start_y * width + start_x] != player or armies[start_y * width + start_x] < 2:
                continue

            for j in range(4):
                end_y, end_x = adjacent_indices[idx_base + j]
                if end_y != -1 and types[end_y * width + end_x] != TileType.MOUNTAIN.value:
                    moves_buffer[move_count] = [player, start_y, start_x, end_y, end_x, 0]
                    move_count += 1
        return move_count

    def generate_valid_moves(self, player):
        owned = self.grid.owners == player
        enough_armies = self.grid.armies >= 2
        y_starts, x_starts = np.where(owned & enough_armies)
        start_coords = np.column_stack((y_starts, x_starts))
        if len(start_coords) == 0:
            return []

        move_count = self._generate_and_validate_moves(
            player, start_coords, self.adjacent_indices,
            self.owners_flat, self.armies_flat, self.types_flat,
            self.moves_buffer, self.height, self.width
        )

        valid_moves = [Move(player, False, move[1], move[2], move[3], move[4])
                       for move in self.moves_buffer[:move_count]]
        return valid_moves

    def make_move(self, start_y, start_x, end_y, end_x, player, split):
        move = np.array([player, start_y, start_x, end_y, end_x, split], dtype=np.int16)
        if not self._generate_and_validate_moves(player, np.array([[start_y, start_x]]),
                                                 self.adjacent_indices, self.owners_flat,
                                                 self.armies_flat, self.types_flat,
                                                 self.moves_buffer, self.height, self.width):
            return False

        captured_general = _execute_move(move, self.owners_flat, self.armies_flat,
                                        self.types_flat, self.height, self.width)

        if captured_general != -1:
            mask = self.owners_flat == captured_general
            self.owners_flat[mask] = player
            self.armies_flat[mask] = (self.armies_flat[mask] + 1) // 2
        return True

    @staticmethod
    @njit
    def _update_armies_flat(armies, types, owners, turn, size):
        for i in prange(size):
            owner = owners[i]
            if owner != -1:
                tile_type = types[i]
                if turn % 50 == 0 and tile_type != TileType.DESERT.value:
                    armies[i] += 1
                if turn % 2 == 0:
                    if tile_type == TileType.GENERAL.value or tile_type == TileType.CITY.value:
                        armies[i] += 1
                if tile_type == TileType.SWAMP.value:
                    armies[i] = max(0, armies[i] - 1)
                    if armies[i] == 0:
                        owners[i] = -1

    def update_armies(self):
        self._update_armies_flat(self.armies_flat, self.types_flat, self.owners_flat,
                                 self._turn, self.height * self.width)

    @staticmethod
    @njit
    def _process_turn_internal(moves_buffer, move_counts, num_players, owners, armies, types, height, width):
        total_moves = np.sum(move_counts)
        current_move_idx = 0

        for player in range(num_players):
            for _ in range(move_counts[player]):
                if current_move_idx < total_moves:
                    captured_general = _execute_move(moves_buffer[current_move_idx], owners, armies, types, height,
                                                    width)
                    if captured_general != -1:
                        for i in prange(height * width):
                            if owners[i] == captured_general:
                                owners[i] = moves_buffer[current_move_idx][0]
                                armies[i] = (armies[i] + 1) // 2
                    current_move_idx += 1

    def process_turn(self, moves=None):
        if moves is None:
            moves = []

        self.move_counts.fill(0)
        total_moves = 0
        self.most_recent_start_move_squares = []
        self.most_recent_end_move_squares = []

        for i, move in enumerate(moves):
            if i >= self.max_moves_per_turn:
                break
            player = move.player_index
            self.moves_buffer[i] = [player, move.start[0], move.start[1],
                                   move.end[0], move.end[1], move.split]
            self.move_counts[player] += 1
            total_moves += 1
            self.most_recent_start_move_squares.append((move.start[0], move.start[1]))
            self.most_recent_end_move_squares.append((move.end[0], move.end[1]))

        self._process_turn_internal(self.moves_buffer, self.move_counts,
                                   self.num_players, self.owners_flat, self.armies_flat,
                                   self.types_flat, self.height, self.width)

        self.priority_player = (self.priority_player + 1) % self.num_players
        self._turn += 1
        self.update_armies()

    def _format_tile(self, y, x):
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
        num_cols = max(len(row) for row in grid)
        col_widths = [0] * num_cols

        def replace_ansi(thing):
            return re.sub(r'(\033|\x1b)\[[0-9;]*m', '', thing)

        for row in grid:
            for col, item in enumerate(row):
                col_widths[col] = max(col_widths[col], len(str(replace_ansi(item))))
        col_header = " " * (4 + col_widths[0] // 2)
        col_header += " ".join(f"{i:^{col_widths[i] + 1}} " for i in range(num_cols))
        print(col_header)

        return_value = ""
        for y, row in enumerate(grid):
            def l(x, item):
                return col_widths[x] + (len(item) - len(replace_ansi(item)))

            def get_square_effect(y, x):
                if (y, x) in self.most_recent_start_move_squares:
                    return EFFECT_RECENT_MOVE_START_POSITION
                elif (y, x) in self.most_recent_end_move_squares:
                    return EFFECT_RECENT_MOVE_END_POSITION
                return ""

            formatted_row = [
                f"{colors[y][x]}{get_square_effect(y, x)}[{str(item):<{l(x, item)}}]{EFFECT_DISABLE_RECENT_MOVE}" for
                x, item in enumerate(row)]
            return_value += f'{y:^3}| ' + " ".join(formatted_row) + end_color() + EFFECT_DISABLE_RECENT_MOVE + "\n"

        return return_value[:-1]

    def display_board(self):
        board_grid = []
        for y in range(self.height):
            row = [self._format_tile(y, x) for x in range(self.width)]
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
                if board_grid[y][x][1] and board_grid[y][x][2]:
                    add_to_print += f"\033[1m{board_grid[y][x][1]}/{board_grid[y][x][2]}\033[22m"
                elif board_grid[y][x][1]:
                    add_to_print += board_grid[y][x][1]
                elif board_grid[y][x][2]:
                    add_to_print += str(board_grid[y][x][2])

                to_print_row.append(add_to_print)
            to_print_board.append(to_print_row)
            to_print_colors.append(to_print_color)

        print(self._get_formatted_grid(to_print_board, to_print_colors))

    def benchmark(self, num_turns=100, seed=42, display_every=None):
        print(f"\nRunning benchmark for {num_turns} turns with seed {seed}...")
        np.random.seed(seed)

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
                print("\x1b[A" * 27)
                self.display_board()
            moves = []
            for player in range(self.num_players):
                player_moves = self.generate_valid_moves(player)
                if player_moves:
                    random_move = np.random.randint(0, len(player_moves))
                    moves.append(player_moves[random_move])
                    print(player_moves[random_move])
            self.process_turn(moves)
        turn_process_time = time.time() - start_time
        print(f"Processed {num_turns} turns: {turn_process_time:.4f} seconds")
        print(f"Average time per turn: {turn_process_time / num_turns:.6f} seconds")

        return move_gen_time, turn_process_time


class OnlineGame(LocalGame):
    """
    Online game. Basically just patches data and creates observations from data into the internal Grid class.
    Mostly taking strakam's IO_GameState code for this one
    """

    def patch(self, data):
        self.turn = data["turn"]
        self.map = self.apply_diff(self.map, data["map_diff"])
        self.cities = self.apply_diff(self.cities, data["cities_diff"])
        self.generals = data["generals"]
        self.scores = data["scores"]
        if "stars" in data:
            self.stars = data["stars"]

    def apply_diff(self, old: list[int], diff: list[int]) -> list[int]:
        i = 0
        new: list[int] = []
        while i < len(diff):
            if diff[i] > 0:  # matching
                new.extend(old[len(new) : len(new) + diff[i]])
            i += 1
            if i < len(diff) and diff[i] > 0:  # applying diffs
                new.extend(diff[i + 1 : i + 1 + diff[i]])
                i += diff[i]
            i += 1
        return new




if __name__ == "__main__":
    game = LocalGame(Grid(width=18, height=20, players=16, uniform_city_density=0.02, uniform_mountain_density=0.15))
    game.display_board()
    move_time, turn_time = game.benchmark(1000, 1000, 1)
    game.display_board()
    del game
    print('ok')