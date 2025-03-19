<div align="center">

# **Genghis**

not stable • generals.io bot backend by [@quantumbagel](https://github.com/quantumbagel) • the spiritual successor to Hannibal
</div>

Please note I'm still laying out this project and that a first version of code might take some time.

### Project Layout
1. Game structuring
   - Grid - generators, board validity, load from custom map file. Also has masks (grid.cities, grid.passable, etc)
   - Game - takes a Grid, can step through with a dictionary of {'username': Action} and returns a list of observations for the next turn, can get Observations from a 'username' perspective. Also tracks current statistics.
   - Action - contains information about a move, namely row, col, direction, split. If all = None, then the move is a pass
   - Replay - takes a grid or a file path, can get turn by half-turn number
   - Observation - stores data relative to a player, including priority, visible cells, army count, etc.

2. Bot API
  - Bot - move command (based on Observation) and reset the bot, as well as ID. Also, has functionality for chat commands via bot.commands
  - command structure:
    - def command(arg1, arg2) - return "str" to reply with, as well as alter bot state. register commands as {"command_name": command} in bot.commands
  - Chat - send and receive messages
  - Leaderboard - keeps track of the game stats to display

3. Game Management
  - GeneralsClient - handles mainloop, creates necessary classes, etc.
  - LocalClient - same thing, but run locally
  - SeleniumClient - ?


4. GUI
  - 
  - GameGUIInterface - Functions for managing the display of a game, regardless of whether it's a replay, spectate, or live
  - WatchGameGUI - mainloop structure for watching a game (local or online) over WebSocket
  - PlayGameGUI  - mainloop structure for playing a game (local only)
  - ReplayGUI - mainloop structure for replaying a game (from file or URL)



   