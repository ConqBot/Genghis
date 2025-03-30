import numpy as np
from enum import Enum
import random
import time

from numba import njit


class TileType(Enum):
    PLAIN = 0
    MOUNTAIN = 1
    CITY = 2
    GENERAL = 3

class Grid:
    # Do generator stuff here
    def __init__(self, width, height, players):
        self.width = width
        self.height = height
        self.num_players = players
        self.grid = np.zeros((self.height, self.width))
        self.mountain_density = 0.5
        self.city_density = 0.5

    def _place_mountains(self):

        pass

    def _place_cities(self):
        pass




class Game:
    def __init__(self, width, height, num_players):
        self.width = width
        self.height = height
        self.num_players = num_players
        self.turn = 0

        self.board_types = np.zeros((height, width), dtype=np.uint8)
        self.board_armies = np.zeros((height, width), dtype=np.uint16)
        self.board_owners = np.full((height, width), -1, dtype=np.int8)
        self.adjacent_indices = self._precompute_adjacents()
        self._setup_board()
        self.priority_player = random.randint(0, num_players - 1)

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

    def _setup_board(self):
        num_mountains = int(self.width * self.height * 0.1)
        mountain_indices = np.random.choice(self.width * self.height, num_mountains, replace=False)
        mountain_y, mountain_x = np.unravel_index(mountain_indices, (self.height, self.width))
        self.board_types[mountain_y, mountain_x] = TileType.MOUNTAIN.value

        num_cities = int(self.width * self.height * 0.05)
        city_indices = np.random.choice(self.width * self.height, num_cities, replace=False)
        city_y, city_x = np.unravel_index(city_indices, (self.height, self.width))
        mask = self.board_types[city_y, city_x] == TileType.PLAIN.value
        city_y, city_x = city_y[mask], city_x[mask]
        self.board_types[city_y, city_x] = TileType.CITY.value
        self.board_armies[city_y, city_x] = np.random.randint(40, 51, size=len(city_y))
        for player in range(self.num_players):
            while True:
                x, y = random.randint(0, self.width - 1), random.randint(0, self.height - 1)
                print(x, y, self.board_types)
                if self.board_types[y, x] == TileType.PLAIN.value:
                    self.board_types[y, x] = TileType.GENERAL.value
                    self.board_armies[y, x] = 1
                    self.board_owners[y, x] = player
                    break

    @staticmethod
    @njit
    def _is_valid_move(start_x, start_y, end_x, end_y, player,
                       board_owners, board_armies, board_types):
        if (board_owners[start_y, start_x] != player or
                board_armies[start_y, start_x] < 2 or
                board_types[end_y, end_x] == TileType.MOUNTAIN.value):
            return False
        return True

    def generate_valid_moves(self, player):
        owned = self.board_owners == player
        enough_armies = self.board_armies >= 2
        valid_starts = np.where(owned & enough_armies)
        start_coords = list(zip(valid_starts[0], valid_starts[1]))
        if not start_coords:
            return []

        #print(self.display_board(25))
        valid_moves = _generate_valid_moves_numba(
            player,
            np.array(start_coords, dtype=np.int16),
            self.adjacent_indices,
            self.board_owners,
            self.board_armies,
            self.board_types
        )
        return valid_moves

    @staticmethod
    @njit
    def _make_move(start_x, start_y, end_x, end_y, player,
                   board_armies, board_owners):
        attack_armies = board_armies[start_y, start_x] - 1
        defend_armies = board_armies[end_y, end_x]

        board_armies[start_y, start_x] = 1

        if attack_armies > defend_armies:
            board_armies[end_y, end_x] = attack_armies - defend_armies
            board_owners[end_y, end_x] = player
        elif attack_armies < defend_armies:
            board_armies[end_y, end_x] = defend_armies - attack_armies
        else:
            board_armies[end_y, end_x] = 0
            board_owners[end_y, end_x] = player
        return True

    def make_move(self, start_x, start_y, end_x, end_y, player):
        if not self._is_valid_move(start_x, start_y, end_x, end_y, player,
                                   self.board_owners, self.board_armies, self.board_types):
            return False
        return self._make_move(start_x, start_y, end_x, end_y, player,
                               self.board_armies, self.board_owners)

    @staticmethod
    @njit
    def _update_armies_with_indices(board_armies, general_indices, owned_indices, city_owned_indices):
        # Update generals
        for idx in general_indices:
            board_armies[idx] += 1
        # Update owned tiles
        for idx in owned_indices:
            board_armies[idx] += 1
        # Update owned cities
        for idx in city_owned_indices:
            board_armies[idx] += 1

    def update_armies(self):
        # Flatten the arrays for indexing
        board_armies_flat = self.board_armies.ravel()
        board_types_flat = self.board_types.ravel()
        board_owners_flat = self.board_owners.ravel()

        # Compute masks and get flat indices
        general_indices = np.where(board_types_flat == TileType.GENERAL.value)[0] if self.turn % 2 == 0 else np.array(
            [], dtype=np.int64)
        owned_indices = np.where(board_owners_flat != -1)[0] if self.turn % 50 == 0 else np.array([], dtype=np.int64)
        city_owned_indices = np.where((board_types_flat == TileType.CITY.value) & (board_owners_flat != -1) & (self.turn % 2 == 0))[0]

        # Update armies using Numba with indices
        self._update_armies_with_indices(board_armies_flat, general_indices, owned_indices, city_owned_indices)



    def process_turn(self, moves):
        current_priority = self.priority_player
        self.turn += 1
        self.update_armies()
        for _ in range(self.num_players):
            for move in moves:
                player_id, start_x, start_y, end_x, end_y = move
                if player_id == current_priority:
                    self.make_move(start_x, start_y, end_x, end_y, player_id)
            current_priority = (current_priority + 1) % self.num_players

        self.priority_player = (self.priority_player + 1) % self.num_players

    def _format_tile(self, x, y):
        owner = self.board_owners[y, x]
        armies = self.board_armies[y, x]
        tile_type = TileType(self.board_types[y, x])

        if tile_type == TileType.MOUNTAIN:
            return "[ MNT ]"
        elif tile_type == TileType.GENERAL:
            return f"[G{owner:1d}:{armies:2d}]"
        elif tile_type == TileType.CITY:
            return f"[C{owner if owner != -1 else '.'}:{armies:2d}]"
        else:
            return f"[{' '+str(owner) if owner != -1 else '. '}:{armies:2d}]"

    def display_board(self, size=5):
        print(f"\nTurn {self.turn} - Priority Player: {self.priority_player}")
        print("-" * (size * 7 + 1))
        print("    ", end="")
        for x in range(size):
            print(f"  {x:2d}  ", end="")
        print("\n    " + "-" * (size * 6))
        for y in range(size):
            row = [self._format_tile(x, y) for x in range(size)]
            print(f"{y:2d} | {' '.join(row)}")
        print("-" * (size * 7 + 1))

    def benchmark(self, num_turns=100, seed=42):
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
            moves = []
            for player in range(self.num_players):
                player_moves = self.generate_valid_moves(player)
                #print(player_moves, turn)
                if player_moves:
                    p_move_L = len(player_moves)
                    random_move = np.random.randint(0, p_move_L)
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
            end_y, end_x = adjacent_indices[start_y, start_x, j]
            if end_y == -1:
                continue
            if (board_owners[start_y, start_x] == player and
                    board_armies[start_y, start_x] >= 2 and
                    board_types[end_y, end_x] != TileType.MOUNTAIN.value):
                moves.append((player, start_x, start_y, end_x, end_y))
    return moves


if __name__ == "__main__":
    game = Game(25, 25, 2)
    game.display_board(size=25)

    move_time, turn_time = game.benchmark(10000)
    print("\nAfter benchmark:")
    game.display_board(size=25)