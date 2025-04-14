<div align="center">

# Generals.io REST API

a guide by [@quantumbagel](https://github.com/quantumbagel)
</div>



## About





### `GET /api/event/getEncryptedUsername`

#### Arguments

`un: username to encrypt (string)`

#### Returns

```
A base64-encrypted salt (e.g. U2FsdGVkX1+1ARHPTJh2N3jRghpT4/bwg9bJoBmGo20= (base64-decrypted 'Salted__Lv7xтSɠm'')
Seems to be used for the internal database, there is little requirement to use this for the API
```


### `GET /api/replays`

#### Arguments

```
count: number of replays to provide (1-200) (int)
offset: numeric offset from beginning (int)
l: the ladder ID (duel for 1v1, ffa for ffa, [UNKNOWN] for 2v2]
```
#### Returns 
```
A list of dictionaries representing the replays.

Example format:
   {
    "type": "custom",  # custom for custom game, classic for ladder game
    "ladder_id": null, # null for custom game, duel for 1v1, ffa for ffa, [UNKNOWN] for 2v2
    "id": "ywh-nBxHC",  # Replay ID
    "started": 1742594343376,  # Epoch time in MS
    "turns": 527,  # Total number of half turns in the game (This game would end on turn 263, or the 527th half-turn)
    "ranking": [  # A ranking of the players, based on how long they survived for, NOT their team. Note that in this example, San and Vandy were on the same team, and won. This is not captured by this replay snapshot.
      {
        "name": "VandyAW",  # name at the time of playing the game
        "stars": 0,  # Stars for this gamemode (0 for custom game)
        "currentName": "VandyAW"  # Current name as of now (only will be different for supporters)
      },
      {
        "name": "Majikarp",
        "stars": 0,
        "currentName": "Majikarp"
      },
      {
        "name": "San12637",
        "stars": 0,
        "currentName": "San12637"
      },
      {
        "name": "AMagan",
        "stars": 0,
        "currentName": "AMagan"
      }
    ]
  }
```

### `GET /api/map`

### Arguments

`name: the name of the map (e.g. 1v1%20Ultimate)`

### Returns

`A dictionary containing information about the map, or 404 if it does not exist.`
```
{
  "title": "1v1 Ultimate",  # Title you passed in
  "description": "You can see your opponent's king. They can see you. Make any mistake, and your opponent will see it immediately.",  # Description
  "width": 8,  # Width of map
  "height": 8,  # Height of map
  "map": "5, , , , , , , , , , , , , , , , , , , , , , , , , , ,g,m, , , , , , ,m,g, , , , , , , , , , , , , , , , , , , , , , , , , , ,5, , , , , , , , , , , , , , , ",
  "username": "President Trump",  # Username of creator
  "server_name": "NA",  # Servername of creator
  "created_at": "2017-03-30T01:07:20.441Z",  # The encoded timestamp of when the map was created
  "score": 240140.794239664, # Score (see GET /api/maps/lists/top)
  "upvotes": 749  # The number of upvotes
}
```

#### Additional information about the `map` parameter

```
g: general (can be suffixed with team and number (e.g. A, B, A1, B2)
m: mountain
a number (e.g. 200): city with that amount of army
n[number] (e.g. n200): neutral army with that amount of army
s: swamp
l: lookout
<nothing>: normal tile
Prefixed by L_: Light tile (always shown)
```
TODO: add data for observatory tiles (maybe o?)


### `GET /api/games/public`

### Arguments

`none`

### Returns

`a list of all public custom lobbies, with the following format:`


```
[
  {
    "id": "snbw",  # Game id (generals.io/games/snbw in this example)
    "map": null,  # The name of the custom map, or null if no map
    "players": "1 / 16",  # The number of players in the lobby and the limit of players that can join the lobby, as a string for some reason.
    "mods": [  # Mods to the game. A list of lists with format ["name", value] where value can be a string, int, float, or null
    
      [  # Width and height are always in custom games, regardless of value. They are NEVER null.
        "Width",
        0.89],
      [
        "Height",
        0.3],
        
      # Each of these are always provided in the JSON, with null for default values (provided in the below table)
      [
        "Game Speed",
        null],
      [
        "Mountain Density",
        0.79],
      [
        "City Density",
        null],
      [
        "Lookout Density",
        null],
      [
        "Observatory Density",
        null],
      [
        "Swamp Density",
        0.61],
      [
        "Desert Density",
        null],
      [
        "City Fairness",
        null],
      [
        "Spawn Fairness",
        0.31],
      
      # All of the modifiers. If a modifier is "off," it will not be shown in this list. This means that "On" is the only possible value for modifiers.
      [
        "City-State",
        "On"
      ]
    ]
  }
]
```


#### Default values for non-modifiers

| Parameter name      | Default value                   | Possible Values                  |
|---------------------|---------------------------------|----------------------------------|
| Game Speed          | 1                               | 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4 |
| Mountain Density    | 0.5                             | 0.0 - 1.0                        |
| City Density        | 0.5                             | 0.0 - 1.0                        |
| Lookout Density     | 0                               | 0.0 - 1.0                        |
| Observatory Density | 0                               | 0.0 - 1.0                        |
| Swamp Density       | 0                               | 0.0 - 1.0                        |
| Desert Density      | 0                               | 0.0 - 1.0                        |
| City Fairness       | 0.5                             | 0.0 - 1.0                        |
| Spawn Fairness      | 0.5 [Only applies to 1v1 games] | 0.0 - 1.0                        |




### GET /api/serverSettings


#### Arguments

`none`

#### Returns

The settings of the generals.io server instance

```
{
  "is_ladder_chat_restricted": false,
  "enabled_ladders": [
    "2v2",  # The ladder IDs currently enabled (see /api/replays, parameter l)
    "ffa",
    "duel"
  ],
  "event_name": "4x3 Saturday!",  # The current event happening, or null if no event
  "event_banner_text": null,  # If not null, display a centered banner with the event banner (below the event name). This is inside the gamemode selection menu.
  "event_notification_popup_text": null,  # If not null, will display a popup upon loading the website. IDK if this takes precedence over the update popup.
  "ffa_player_count": 12, # The current total number of players in FFA (for events, 8 if no event)
  "ffa_team_size": 3,  # The current team size of FFA (for events, 1 if no event)
  "desert_enabled": true, # Whether to allow the desert tile in custom games as a modifier
  "lookout_enabled": true,  # Whether to allow the lookout tile in custom games as a modifier
  "observatory_enabled": true, # Whether to allow the observatory tile in custom games as a modifier
  "unhidden_modifiers": [0, 1, 2, 3, 4, 5, 7, 6, 8],  # Modifiers to display, based on their index (see TBA)
  "non_supporter_modifiers": [0, 1, 2, 3, 5, 6, 8]  # Modifiers that can be used by non-supporters, based on their index (see TBA)
}
```

### POST /api/maps/upvote

#### Arguments

`map: the map to upvote`
`user_id: the user id of the user who is upvoting`

#### Returns

`200 if success, 400 if user_id does not exist or is not provided, 403 if map is already upvoted, or 404 if map does not exist`


### GET /api/maps/lists/new


#### Arguments

`none`

#### Returns

Custom maps, sorted by how new they are.


### GET /api/maps/lists/hot


#### Arguments

`none`

#### Returns

Custom maps, sorted by how 🔥HOT🔥 they are. 

Algorithm: TBA

### GET /api/maps/lists/top


#### Arguments

`none`

#### Returns

Custom maps, sorted by how good they are base on their score parameter.

Algorithm:

Score = Upvotes + Playtime

Upvotes = Sum of U(Player) for each player who upvoted

U(Player) = 1 + (Games Played)/2.5 (max=5)

Playtime = 1 point per player per 40 turns, with an additional penalty for short games (TBA)


### GET /api/maps/lists/best


#### Arguments

`none`

#### Returns

Custom maps hand-picked by Lazerpent (generals.io developer)


### GET /api/maps/random


#### Arguments

`none`

#### Returns

10 random maps (see map formatting and GET /api/map)


### GET /api/maps/search

#### Arguments

`q: query to search for`

#### Returns
top 10 results (or less) based on the query. Also includes 




#### Cache

From the generals.io source:

NEW_MAPS_CACHE_HOURS: 1 / 60, (every minute)

HOT_MAPS_CACHE_HOURS: .05, (every 3 minutes)

TOP_MAPS_CACHE_HOURS: 5 / 60, (every 5 minutes)

BEST_MAPS_CACHE_HOURS: 24, (every day)

RANDOM_MAPS_CACHE_HOURS: 1 / 60 / 6, (every 10 seconds)

#### Map formatting

```
{
    # These parameters are the same as (GET /api/map)

    "title": "Ultimate 4player",  
    "description": "1 vs 1 vs 1 vs 1 or also as teams\n\nPerfectly symmetric",  
    "server_name": "NA",
    "created_at": "2025-03-12T15:56:35.838Z",
    "username": "pacefalm",
    "width": 17,  # Width of map
    "height": 17,  # Height
    "map": " , , , , , , , , , , , , , , , , , ,40, , , , , ,o,m,o, , , , , ,40, , , , , , , , , ,m, , , , , , , , , , , ,20, , , , ,m, , , , ,20, , , , , , , , , , , ,m, , , , , , , , , , , , , ,10, , ,m, , ,10, , , , , , , , , , , , , ,m, , , , , , , , , ,o, , , , , ,g ,o,g , , , , , ,o, , ,m,m,m,m,m,m,o,m,o,m,m,m,m,m,m, , ,o, , , , , ,g ,o,g , , , , , ,o, , , , , , , , , ,m, , , , , , , , , , , , , ,10, , ,m, , ,10, , , , , , , , , , , , , ,m, , , , , , , , , , , ,20, , , , ,m, , , , ,20, , , , , , , , , , , ,m, , , , , , , , , ,40, , , , , ,o,m,o, , , , , ,40, , , , , , , , , , , , , , , , , , ",
    "score": 23,  # Score (see GET /api/maps/lists/top)
    "upvotes": 1, Total number of upvotes, not weighted (just number of accounts)
    
    # For the GET /api/maps/lists/hot, this additional parameter is added
    "hot": 0.0235090757837417  # hot score (only in/see GET /api/maps/lists/hot)
    "textScore": 0.02845  # How well the map matches the query (only in GET /api/maps/search) (higher=better)
  },
```

### POST /api/publishedMapToFile

#### Arguments

`name: map to download`
`user_id: user_id of owner of map`

### Returns

`409 if user is not a supporter`
IDK other return codes simply because I am not a supporter :O


### POST /api/createCustomMap

#### Arguments

`title: title of map`

`description: description of map`

`width: width of map`

`height: height of map`

`map: the actual map data, formatted like the GET /api/map request`

`user_id: user id of map creator`

#### Returns

`500 if width * height is not equal to the number of tiles`
TBA



### POST /api/mapToFile

### POST /api/mapFromFile

### GET /api/adminSettings

### POST /api/adminSetting

### POST /api/ackWarning

### GET /api/replaysForUsername

(offset, count)
### GET /api/mapsForUsername

(offset, count)



### GET /api/validateUsername

u

### GET /api/starsAndRanks

u, client (bool)


### GET /api/isSupporter

u


### GET /api/profileModerationData

u, m, client

### POST /api/moderate

moderator, moderator_id, code, target, action, reason

action: "targeted_disable", "targeted_enable"
