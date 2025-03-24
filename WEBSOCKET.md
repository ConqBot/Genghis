<div align="center">

# Generals.io WebSocket API

a guide by [@quantumbagel](https://github.com/quantumbagel)
</div>


# Sending

Type A = send prefix = 42, does not send explicit response (e.g. cancel, stars_and_rank, join_1v1)
Type B = send message prefix = 42xyz, return prefix = 43xyz as return value (e.g. get_username, is_supporter)


## User Information
| Name             | Arguments   | Argument Description   | WDID?                                                                                                    | Returns                                                                                                                                                                                                                                                                                                                                          | Type | Verified |
|------------------|-------------|------------------------|----------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|----------|
| stars_and_rank   | `[user_id]` | `user_id`: the user id | Get the stars and ranking of the user with ID `user_id`                                                  | `star` and `rank` message containing the user's stars for all played queues, as well as their serverwide ranking.                                                                                                                                                                                                                                | A    | Yes      |
| get_username     | `[user_id]` | `user_id`: the user id | Get username of the user with ID `user_id`, or `null`                                                    | `[<username>]` where `username` is the username, or null if does not exist                                                                                                                                                                                                                                                                       | B    | Yes      |
| is_supporter     | `[user_id]` | `user_id`: the user id | Get whether the user with ID `user_id` is a supporter.                                                   | `[<status>]` where `status` is a boolean value of whether the user is a supporter. Note that for UIDs that do not exist, this will still be `false`                                                                                                                                                                                              | B    | Yes      |
| get_notifs       | `[user_id]` | `user_id`: the user id | Get the moderator notifications (warnings) of the user with ID `user_id` (I think, not sure on this one) | Unknown (simply because this is the only type B message to not return a value if none exists.                                                                                                                                                                                                                                                    | B    | No       |
| check_moderation | `[user_id]` | `user_id`: the user id | Get the moderation status of the user with ID `user_id`                                                  | `[<muted>, <disabled>, <warning>]` where `muted` is a boolean describing whether the user is muted, `disabled` is a string describing the reason the account was disabled, or `null` if the account is not disabled. `warning` is the same thing as `disabled` (a string or `null`), but only serves as a warning with no penalty to the account | B    | No       |


## Join Games


| Name         | Arguments                      | Argument Description   | WDID?                                                                                                                                                                 | Returns | Type | Verified |
|--------------|--------------------------------|------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------|------|----------|
| play         | `[user_id] NBK null null`      | `user_id`: the user id | Add the user to the FFA ladder queue (or whatever queue it is replaced by (e.g. Big Team)                                                                             | None    | A    | Yes      |
| join_1v1     | `[user_id] NBK null null`      | `user_id`: the user id | Add the user to the 1v1 ladder queue.                                                                                                                                 | None    | A    | Yes      |
| join_private | `[room_id] [user_id] NBK null` | `user_id`: the user id | Add the user with ID `user_id` to the private game with ID `room_id`, or create the room if it does not exist. If the room is full, the user will become a spectator. | None    | A    | Yes      |


## Custom Games
| Name                         | Arguments                         | Argument Description                                                                                                                             | WDID?                                                                                                                                                                                                                                          | Returns                                                                                                                                                                                       | Type | Verified |
|------------------------------|-----------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|----------|
| set_custom_options           | `[room_id] [options]`             | `room_id`: the room ID to change settings in. `options`: The options to change, as a dictionary. To see all options, go to TBA                   | Changes one (or multiple) settings to the specified values.                                                                                                                                                                                    | An empty list is success. If `room_id` does not exist, return `"This custom game does not exist."` If the current user is not the host of the game, return `"You are not the host of this game."` | B    | Yes      |
| set_custom_team              | `[room_id] [team_id]`             | `room_id` the room ID to change the user's team on. `team_id`: The team ID to change the player to.                                              | Sets the logged-in player to the team with ID `team_id`. Note that `team_id` must be from 1-16. If you provide a `team_id` value of 17, the user will become a spectator. If the `team_id` or `game_id` value is invalid, nothing will happen. | None                                                                                                                                                                                          | A    | Yes      |
| make_custom_public           | `[room_id]`                       | `room_id`: the room ID to make public (display in the "Public Custom Games" list.                                                                | Sets the lobby with ID `room_id` as public.                                                                                                                                                                                                    | An empty list is success. If `room_id` does not exist, return `"This custom game does not exist."` If the current user is not the host of the game, return `"You are not the host of this game."` | B    | Yes      |
| update_custom_chat_recording | `[room_id] null [chat_recording]` | `room_id`: the room ID to update the chat recording setting. `chat_recording`: a boolean representing what to set the chat recording setting to. | Sets the chat recording setting in the lobby with ID `room_id` to `chat_recording`, but only if the lobby exists and the current user is the host of the game. Note that this command does not return any positive or negative confirmation    | No response is success.                                                                                                                                                                       | A    | Yes      |
| set_custom_host | `[room_id] [player_index]` | `room_id`: the room ID to change the host of the custom game. `player_index`: the index of the player to make host (0 is host, 1 is next to join after host, etc) | Sets the host of the custom game with ID `room_id` to the player with room index `player_index` | No response is success.  If `room_id` does not exist, return `"This custom game does not exist."` If the current user is not the host of the game, return `"You are not the host of this game."

## ping_worker 
## ping_server
## set_username \[user_id] \[username] \[NBK] null
## set_custom_host \[room_id] \[room_index]
## set_color \[room_index] \[color_index]
## attack \[starting_tile] \[ending_tile] \[split]
## ping_tile \[tile]
## cancel
## set_force_start \[room_id] \[force_start]
## chat_message \[channel] 
## leaderboard \[mode]
## get_2v2_teammates \[user_id]
## leave_game
## surrender
## undo_move
## clear_moves
## join_team \[team_id] \[user_id] \[NBK] null null
## join_big_team \[team_id] \[user_id] \[NBK] null null
## leave_team
## link_email \[email]
## recover_account \[email]
## get_season
## listen_public_customs
## stop_listen_public_customs
## clear_notif
## queue_count
## rematch




# Receiving
## notify
## pre_game_start
## game_start
## game_update
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