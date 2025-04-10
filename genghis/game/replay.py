from genghis.game.game import LocalGame
from genghis.game.grid import ReplayGrid
from genghis.replays.deserialize import Replay


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
                    print(moves[turn])
                    self.process_turn(moves[turn])
                    self.history.append((self.grid.types, self.grid.armies, self.grid.owners))
                else:
                    self.process_turn()
                    self.history.append((self.grid.types, self.grid.armies, self.grid.owners))





r = ReplayGrid(Replay(filename="../replays/vQKnym89k.gior"))
print(r)

rg = ReplayGame(r)

print(rg.display_board())

for i in range(10):
    rg.turn += 10
    print(rg.turn)
    print(rg.display_board())
