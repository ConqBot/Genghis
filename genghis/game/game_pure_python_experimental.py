import random
import time
import re
from enum import Enum
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


def precompute_adjacents(height, width):
    adjacents = [[[-1, -1] for _ in range(4)] for _ in range(height * width)]
    directions = [(-1, 0), (0, 1), (1, 0), (0, -1)]

    for y in range(height):
        for x in range(width):
            base_idx = y * width + x
            for i, (dy, dx) in enumerate(directions):
                new_y, new_x = y + dy, x + dx
                if 0 <= new_x < width and 0 <= new_y < height:
                    adjacents[base_idx][i] = [new_y, new_x]
    return adjacents


def execute_move(move, owners, armies, types, height, width):
    player, start_x, start_y, end_x, end_y, split = move
    start_idx = start_y * width + start_x
    end_idx = end_y * width + end_x

    # Validate move
    if (armies[start_idx] < 2 or
            start_x < 0 or start_x >= width or start_y < 0 or start_y >= height or
            end_x < 0 or end_x >= width or end_y < 0 or end_y >= height):
        print(f"Invalid move: {move}, armies={armies[start_idx]}, grid bounds={width}x{height}")
        return -1

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
            armies[end_idx] = 0
            owners[end_idx] = player

    return captured_general


class LocalGame:
    def __init__(self, grid: Grid):
        self.grid = grid
        self._turn = 0
        self.height = grid.height
        self.width = grid.width
        self.num_players = grid.num_players
        self.move_counts = [0] * self.num_players
        self.adjacent_indices = precompute_adjacents(self.height, self.width)
        self.priority_player = random.randint(0, self.num_players - 1)
        self.owners_flat = [grid.owners[y][x] for y in range(self.height) for x in range(self.width)]
        self.armies_flat = [grid.armies[y][x] for y in range(self.height) for x in range(self.width)]
        self.types_flat = [grid.types[y][x] for y in range(self.height) for x in range(self.width)]
        self.most_recent_start_move_squares = []
        self.most_recent_end_move_squares = []

    def sync_flat_to_grid(self):
        """Sync flat lists back to grid arrays for display."""
        for y in range(self.height):
            for x in range(self.width):
                idx = y * self.width + x
                self.grid.owners[y][x] = self.owners_flat[idx]
                self.grid.armies[y][x] = self.armies_flat[idx]
                self.grid.types[y][x] = self.types_flat[idx]

    def generate_and_validate_moves(self, player, start_coords, adjacent_indices, owners, armies, types):
        valid_moves = []

        for start_y, start_x in start_coords:
            idx_base = start_y * self.width + start_x
            if owners[idx_base] != player or armies[idx_base] < 2:
                continue

            for j in range(4):
                end_y, end_x = adjacent_indices[idx_base][j]
                if end_y == -1:
                    continue
                end_idx = end_y * self.width + end_x
                if types[end_idx] != TileType.MOUNTAIN.value:
                    valid_moves.append([player, start_x, start_y, end_x, end_y, 0])

        return valid_moves

    def generate_valid_moves(self, player):
        start_coords = []
        for y in range(self.height):
            for x in range(self.width):
                idx = y * self.width + x
                if self.owners_flat[idx] == player and self.armies_flat[idx] >= 2:
                    start_coords.append([y, x])

        move_list = self.generate_and_validate_moves(
            player, start_coords, self.adjacent_indices,
            self.owners_flat, self.armies_flat, self.types_flat
        )

        valid_moves = [
            Move(player, False, move[1], move[2], move[3], move[4])
            for move in move_list
        ]
        return valid_moves

    def make_move(self, start_x, start_y, end_x, end_y, player, split):
        move = [player, start_x, start_y, end_x, end_y, split]
        valid_moves = self.generate_and_validate_moves(
            player, [[start_y, start_x]], self.adjacent_indices,
            self.owners_flat, self.armies_flat, self.types_flat
        )
        if move not in valid_moves:
            print(f"Move {move} not in valid moves: {valid_moves}")
            return False

        captured_general = execute_move(
            move, self.owners_flat, self.armies_flat, self.types_flat, self.height, self.width
        )

        if captured_general != -1:
            for i in range(self.height * self.width):
                if self.owners_flat[i] == captured_general:
                    self.owners_flat[i] = player
                    self.armies_flat[i] = (self.armies_flat[i] + 1) // 2

        self.sync_flat_to_grid()
        return True

    def update_armies(self):
        size = self.height * self.width
        for i in range(size):
            owner = self.owners_flat[i]
            if owner != -1:
                tile_type = self.types_flat[i]
                if self._turn % 50 == 0 and tile_type != TileType.DESERT.value:
                    self.armies_flat[i] += 1
                if self._turn % 2 == 0:
                    if tile_type == TileType.GENERAL.value or tile_type == TileType.CITY.value:
                        self.armies_flat[i] += 1
                if tile_type == TileType.SWAMP.value:
                    self.armies_flat[i] = max(0, self.armies_flat[i] - 1)
                    if self.armies_flat[i] == 0:
                        self.owners_flat[i] = -1
        self.sync_flat_to_grid()

    def process_turn_internal(self, moves, move_counts, num_players, owners, armies, types):
        for player in range(num_players):
            for i in range(move_counts[player]):
                if i < len(moves[player]):
                    captured_general = execute_move(
                        moves[player][i], owners, armies, types, self.height, self.width
                    )
                    if captured_general != -1:
                        for j in range(self.height * self.width):
                            if owners[j] == captured_general:
                                owners[j] = moves[player][i][0]
                                armies[j] = (armies[j] + 1) // 2

    def process_turn(self, moves=None):
        if moves is None:
            moves = []

        self.move_counts = [0] * self.num_players
        self.most_recent_start_move_squares = []
        self.most_recent_end_move_squares = []

        player_moves = [[] for _ in range(self.num_players)]
        for move in moves:
            player = move.player_index
            move_tuple = [player, move.start[0], move.start[1], move.end[0], move.end[1], move.split]
            # Validate move before adding
            valid_moves = self.generate_and_validate_moves(
                player, [[move.start[1], move.start[0]]], self.adjacent_indices,
                self.owners_flat, self.armies_flat, self.types_flat
            )
            if move_tuple in valid_moves:
                player_moves[player].append(move_tuple)
                self.move_counts[player] += 1
                self.most_recent_start_move_squares.append((move.start[1], move.start[0]))
                self.most_recent_end_move_squares.append((move.end[1], move.end[0]))
            else:
                print(f"Skipping invalid move for player {player}: {move_tuple}")

        self.process_turn_internal(
            player_moves, self.move_counts, self.num_players,
            self.owners_flat, self.armies_flat, self.types_flat
        )

        self.priority_player = (self.priority_player + 1) % self.num_players
        self._turn += 1
        self.update_armies()

    def _format_tile(self, x, y):
        owner = self.grid.owners[y][x]
        armies = self.grid.armies[y][x]
        tile_type = TileType(self.grid.types[y][x])
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

            def get_square_effect(x, y):
                if (y, x) in self.most_recent_start_move_squares:
                    return EFFECT_RECENT_MOVE_START_POSITION
                elif (y, x) in self.most_recent_end_move_squares:
                    return EFFECT_RECENT_MOVE_END_POSITION
                return ""

            formatted_row = [
                f"{colors[y][x]}{get_square_effect(x, y)}[{str(item):<{l(x, item)}}]{EFFECT_DISABLE_RECENT_MOVE}"
                for x, item in enumerate(row)
            ]
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
        random.seed(seed)

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
                    random_move = random.randint(0, len(player_moves) - 1)
                    moves.append(player_moves[random_move])
            self.process_turn(moves)
        turn_process_time = time.time() - start_time
        print(f"Processed {num_turns} turns: {turn_process_time:.4f} seconds")
        print(f"Average time per turn: {turn_process_time / num_turns:.6f} seconds")

        return move_gen_time, turn_process_time


if __name__ == "__main__":
    game = LocalGame(Grid(width=18, height=20, players=16, uniform_city_density=0.02, uniform_mountain_density=0.15))
    game.display_board()
    move_time, turn_time = game.benchmark(100000, 1000, 1000)
    print("\nAfter benchmark:")
    game.display_board()