<div align="center">

# Generals.io WebSocket API

a guide by [@quantumbagel](https://github.com/quantumbagel)
</div>


# Sending


## Some notes on protocol
Type A = send prefix = 42, does not send explicit response (e.g. cancel, stars_and_rank, join_1v1). 42xyz can also be sent, but 42 will still be the response.

Type B = send message prefix = 42xyz, return prefix = 43xyz as return value (e.g. get_username, is_supporter). 

`NBK` = This peculiar constant: `sd09fjdZ03i0ejwi_changeme`





## User Information
| Name             | Arguments   | Argument Description   | WDID?                                                                                                    | Returns                                                                                                                                                                                                                                                                                                                                          | Type | Verified |
|------------------|-------------|------------------------|----------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|----------|
| stars_and_rank   | `[user_id]` | `user_id`: the user id | Get the stars and ranking of the user with ID `user_id`                                                  | `star` and `rank` message containing the user's stars for all played queues, as well as their serverwide ranking.                                                                                                                                                                                                                                | A    | Yes      |
| get_username     | `[user_id]` | `user_id`: the user id | Get username of the user with ID `user_id`, or `null`                                                    | `[<username>]` where `username` is the username, or null if does not exist                                                                                                                                                                                                                                                                       | B    | Yes      |
| is_supporter     | `[user_id]` | `user_id`: the user id | Get whether the user with ID `user_id` is a supporter.                                                   | `[<status>]` where `status` is a boolean value of whether the user is a supporter. Note that for UIDs that do not exist, this will still be `false`                                                                                                                                                                                              | B    | Yes      |
| get_notifs       | `[user_id]` | `user_id`: the user id | Get the moderator notifications (warnings) of the user with ID `user_id` (I think, not sure on this one) | Unknown (simply because this is the only type B message to not return a value if none exists.                                                                                                                                                                                                                                                    | B    | No       |
| check_moderation | `[user_id]` | `user_id`: the user id | Get the moderation status of the user with ID `user_id`                                                  | `[<muted>, <disabled>, <warning>]` where `muted` is a boolean describing whether the user is muted, `disabled` is a boolean representing whether the account was disabled, or `null` if the account is not disabled. `warning` is the same thing as `disabled` (a string or `null`), but only serves as a warning with no penalty to the account | B    | No       |


## Join Games


| Name         | Arguments                           | Argument Description                                                             | WDID?                                                                                                                                                                 | Returns | Type | Verified |
|--------------|-------------------------------------|----------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|------|----------|
| play         | `[user_id] NBK null null`           | `user_id`: the user id                                                           | Add the user to the FFA ladder queue (or whatever queue it is replaced by (e.g. Big Team)                                                                             | None    | A    | Yes      |
| join_1v1     | `[user_id] NBK null null`           | `user_id`: the user id                                                           | Add the user to the 1v1 ladder queue.                                                                                                                                 | None    | A    | Yes      |
| join_private | `[room_id] [user_id] NBK null`      | `user_id`: the user id                                                           | Add the user with ID `user_id` to the private game with ID `room_id`, or create the room if it does not exist. If the room is full, the user will become a spectator. | None    | A    | Yes      |
| join_team    | `[team_id] [user_id] NBK null null` | `team_id`: the team id to join. `user_id`: the user attempting to join the team. | Puts the user with ID `user_id` on the team with ID `team_id`, creating the team if it does not exist                                                                 | None    | A    | Yes      |



## Custom Games
| Name                         | Arguments                         | Argument Description                                                                                                                                              | WDID?                                                                                                                                                                                                                                          | Returns                                                                                                                                                                                           | Type | Verified |
|------------------------------|-----------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|----------|
| set_custom_options           | `[room_id] [options]`             | `room_id`: the room ID to change settings in. `options`: The options to change, as a dictionary. To see all options, go to TBA                                    | Changes one (or multiple) settings to the specified values.                                                                                                                                                                                    | An empty list is success. If `room_id` does not exist, return `"This custom game does not exist."` If the current user is not the host of the game, return `"You are not the host of this game."` | B    | Yes      |
| set_custom_team              | `[room_id] [team_id]`             | `room_id` the room ID to change the user's team on. `team_id`: The team ID to change the player to.                                                               | Sets the logged-in player to the team with ID `team_id`. Note that `team_id` must be from 1-16. If you provide a `team_id` value of 17, the user will become a spectator. If the `team_id` or `game_id` value is invalid, nothing will happen. | None                                                                                                                                                                                              | A    | Yes      |
| make_custom_public           | `[room_id]`                       | `room_id`: the room ID to make public (display in the "Public Custom Games" list.                                                                                 | Sets the lobby with ID `room_id` as public.                                                                                                                                                                                                    | An empty list is success. If `room_id` does not exist, return `"This custom game does not exist."` If the current user is not the host of the game, return `"You are not the host of this game."` | B    | Yes      |
| update_custom_chat_recording | `[room_id] null [chat_recording]` | `room_id`: the room ID to update the chat recording setting. `chat_recording`: a boolean representing what to set the chat recording setting to.                  | Sets the chat recording setting in the lobby with ID `room_id` to `chat_recording`, but only if the lobby exists and the current user is the host of the game. Note that this command does not return any positive or negative confirmation    | No response is success.                                                                                                                                                                           | A    | Yes      |
| set_custom_host              | `[room_id] [player_index]`        | `room_id`: the room ID to change the host of the custom game. `player_index`: the index of the player to make host (0 is host, 1 is next to join after host, etc) | Sets the host of the custom game with ID `room_id` to the player with room index `player_index`                                                                                                                                                | No response is success.  If `room_id` does not exist, return `"This custom game does not exist."` If the current user is not the host of the game, return `"You are not the host of this game."`  | B    | Yes      |



## Queue Actions
| Name            | Arguments                  | Argument Description                                                                                                                                                  | WDID?                                                                                        | Returns                                                                                                                                                                                                    | Type | Verified |
|-----------------|----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|----------|
| set_force_start | `[room_id] [force_start]`  | `room_id` the custom room ID to set force start, or `null` if queueing for FFA. `force_start`: a boolean representing whether the user wants to force start or not.   | Sets the force start status for the user to `force_start`                                    | None                                                                                                                                                                                                       | A    | Yes      |
| cancel          | None                       | None                                                                                                                                                                  | Removes the user from the current queue, if any                                              | None                                                                                                                                                                                                       | A    | Yes      |
| set_color       | `[queue_id] [color_index]` | `queue_id`: the ID of the queue to set the color (duel, 2v2, ffa, or the custom lobby id. `color_index`: the index of the color to set (see TBA for a list of colors) | Sets the player's color for queue `queue_id` to the color at index `color_index`             | Returns empty list if success (unverified). Returns `"This queue does not exist"` if `queue_id` is not valid. Returns `"Only supporters can choose their color"` if the logged-in user is not a supporter. | B    | Mostly   |
| leave_team      | None                       | None                                                                                                                                                                  | Removes the user from their 2v2 team, if it exists. This is basically `cancel` for 2v2 games | None                                                                                                                                                                                                       | A    | Yes      |


## In-Game Actions
| Name         | Arguments                                              | Argument Description                                                                                                                                                                                                                                                                                                                                                                                                                                                              | WDID?                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Returns | Type | Verified |
|--------------|--------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|------|----------|
| attack       | `[starting_tile] [ending_tile] [split] [attack_index]` | `starting_tile` and `ending_tile`: the ID of the starting and ending tiles for the attack (see TBA for how to calculate). `split`: a boolean value representing whether to split the army or not (attacking square rounded down). `attack_index`: the index of the attack, which should increment from 1 onwards based on the queued moves. The server will respond with the last moved move_index, so the client knows what moves have been made (or invalidated) by the server. | Makes a move from `starting_tile` to `ending_tile`, splitting army if `split` is true.                                                                                                                                                                                                                                                                                                                                                                                | None    | A    | True     |        
| ping_tile    | `[tile]`                                               | `tile`:  the ID of the tile to ping (see TBA on how to calculate).                                                                                                                                                                                                                                                                                                                                                                                                                | Pings the tile with ID `tile`. Note this only works when the current account is on a team (multiple players)                                                                                                                                                                                                                                                                                                                                                          | None    | A    | Yes      |
| undo_move    | None                                                   | None                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Remove the most recently queued move, if any. This will stop the server-side attackIndex from incrementing past the value of the attack that was cancelled, which means the client should actually send this value again for the next `attack`. Interestingly enough, the official web client actually has a inefficiency in this regard, and continues to increment attackIndex regardles, which makes the logic for which attack was cancelled much more difficult. | None    | A    | Yes      |
| clear_moves  | None                                                   | None                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Remove all queued moves (see `undo_move` for logic). Completely stops server-side attackIndex from incrementing.                                                                                                                                                                                                                                                                                                                                                      | None    | A    | Yes      |
| surrender    | None                                                   | None                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Forfeit the current game.                                                                                                                                                                                                                                                                                                                                                                                                                                             | None    | A    | Yes      |
| chat_message | `[channel] [message] ""`                               | `channel`: the chat channel to send the message to. This is provided by the `game_start` message in most cases, or generated as `chat_custom_queue` + the lobby ID for custom games. `message`: the message to send. Note that you MUST send an empty string as the third argument, NOT `null`. I honestly have zero clue what the point of the third argument is lmfao                                                                                                           | Send the message `message` in the chat channel `channel`                                                                                                                                                                                                                                                                                                                                                                                                              | None    | A    | Yes      |
| leave_game   | None                                                   | None                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Leave the current game (only applies to spectators and players after the game is over)                                                                                                                                                                                                                                                                                                                                                                                | None    | A    | Yes      |
| rematch      | None                                                   | None                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Send the request to have a rematch (after the game is done)                                                                                                                                                                                                                                                                                                                                                                                                           | None    | A    | Yes      | 

## Utilities
| Name                       | Arguments                                                                                                                                      | Argument Description                                                                                                                   | WDID?                                                                                              | Returns                                                                                                                                                                                                                     | Type | Verified |
|----------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|----------|
| set_username               | `[user_id] [username] NBK` to create a human / `[user_id] [username]` to create a bot. Note that bot users are only allowed on the bot server. | `user_id`: the ID of the user to set the username for. `username`: the username to assign to the user ID                               | Sets the account with ID `user_id`'s username to `username`, if available. Cooldown is 300 seconds | None (will send a `error_set_message` message with one argument, a string. If the string is none, the change was successful)                                                                                                | A    | Yes      |
| link_email                 | `[email]`                                                                                                                                      | `email`: the email to link                                                                                                             | Links the email `email` to the currently signed account                                            | Returns an empty list if success and `null` if failure                                                                                                                                                                      | B    | Yes      |
| recover_account            | `[email]`                                                                                                                                      | `email`: the email to recover the account for                                                                                          | Sends a recovery email to the account associated with the email `email`                            | Returns `true` if the account exists and `false` if it does not                                                                                                                                                             | B    | Yes      |
| get_season                 | None                                                                                                                                           | None                                                                                                                                   | Returns the current season, as an integer                                                          | The current season as an integer                                                                                                                                                                                            | B    | Yes      |        
| queue_count                | None                                                                                                                                           | None                                                                                                                                   | Returns the amount of player queued for each gamemode                                              | Returns the amount of player queued for each gamemode `[ffa, duel, 2v2]`. Note that the return value has one argument: a list (not three arguments) e.g. `431[[1, 2, 3]]`                                                   | B    | Yes      |
| ping_server                | None                                                                                                                                           | None                                                                                                                                   | Pings the server                                                                                   | Sends a `pong_server` message back to test ping.                                                                                                                                                                            | A    | Yes      |
| listen_public_customs      | None                                                                                                                                           | None                                                                                                                                   | Subscribe to updates to the list of public custom games                                            | None                                                                                                                                                                                                                        | A    | Yes      |
| stop_listen_public_customs | None                                                                                                                                           | None                                                                                                                                   | Stop subscribing to updates to the list of public custom games                                     | None                                                                                                                                                                                                                        | A    | Yes      |
| leaderboard                | `[mode]`                                                                                                                                       | `mode`: the mode to get the leaderboard from (choose from `ffa`, `ffacombat`, `ffakills`, `ffawin`, `bigteam`, `mm2v2`, `2v2`, `duel`) | Get the leaderboard data for the mode `mode`                                                       | Returns the following format: `{"ladder": <mode>, "users": <list of usernames>, "supporters": <list of booleans representing supporter status>, "stars": <list of stringified floats representing the rating of the user>}` | B    | Yes      |

## Commands I couldn't get working

- join_big_team \[team_id] \[user_id] NBK null null
- clear_notif
- get_notifs
- check_moderation
- get_2v2_teammates \[user_id]
- ping_worker





# Receiving
| Name           | When is it sent?                                                          | Format             | Description                                                                      | What does it do?                                                              |
|----------------|---------------------------------------------------------------------------|--------------------|----------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| notify         | When the server wants to display a notification to the client             | `[subject] [body]` | `subject`: the subject of the notification. `body`: the body of the notification | Asks the client to send a notification with subject `subject` and body `body` |
| pre_game_start | When the server wants to notify the client is 1 second away from starting | No other data      | None                                                                             | Asks the client to display notice that the game is about to start.            |
| game_start | When the game has started and the server wants to send information about the game, including usernames, modifiers, chat channel, replay ID, custom map, swamp positions, and light positions. | `{

## game_start example format
```
{ 
   "playerIndex": 0,
    "playerColors": [
      0,
      2
    ],
    "replay_id": "Z1mtzONO7",
    "chat_room": "game_1743023103283t3mujse6uRw1LiSAAjaD",
    "usernames": [
      "HannibalAI",
      "Skibidious"
    ],
    "teams": [
      1,
      2
    ],
    "game_type": "custom",
    "swamps": [],
    "lights": [],
    "options": {  # Note that these options mirror the formatting from the public games modifiers in REST.md
      "map": null,
      "width": 0.3,
      "height": 0.3,
      "game_speed": null,
      "modifiers": [],
      "mountain_density": null,
      "city_density": null,
      "lookout_density": null,
      "observatory_density": null,
      "swamp_density": null,
      "desert_density": null,
      "max_players": null,
      "city_fairness": null,
      "spawn_fairness": null,
      "defeat_spectate": null,
      "spectate_chat": null,
      "public": null,
      "chatRecordingDisabled": null,
      "eventId": null
    }
  }
  ```
  
  
## game_update
[
  "game_update",
  {
    "scores": [
      {
        "total": 62,
        "tiles": 1,
        "i": 0,
        "color": 0,
        "dead": false,
        "warn_afk": true
      },
      {
        "total": 62,
        "tiles": 1,
        "i": 1,
        "color": 2,
        "dead": false,
        "warn_afk": true
      }
    ],
    "turn": 118,
    "attackIndex": 0,
    "generals": [
      88,
      -1
    ],
    "map_diff": [
      90,
      1,
      62,
      595
    ],
    "cities_diff": [
      1
    ],
    "deserts_diff": [
      0
    ]
  },
  null
]
## game_over

## disable_rematch
## rematch_update
## ping_tile
## pong_server
## pong_worker
## queue_update
## team_update
## big_team_update
## team_joined_queue
## removed_from_queue
## chat_message
## game_lost
[
  "game_lost",
  {
    "surrender": true,
    "afk": true
  },
  null
]
## afk_warning
## game_won
## server_down
## 2v2_teammates
## stars
## rank
## error_user_id
## error_queue_full
## error_banned
## server_restart
## gio_error
## error_set_username
## public_customs_update