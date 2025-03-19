<div align="center">
## **Genghis**
generals.io bot backend
</div>


Project Layout
1. Game structuring
   - Grid - generators, board validity, load from custom map file. Also has masks (grid.cities, grid.passable, etc)
   - Game - takes a Grid, can step through with a dictionary of {'username': Action} and returns a list of observations for the next turn, can get Observations from a 'username' perspective. Also tracks current statistics.
   - Action - contains information about a move, namely row, col, direction, split. If all = None, then the move is a pass
   - Replay - takes a grid or a file path, can get turn by half-turn number

