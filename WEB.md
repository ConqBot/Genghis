<div align="center">

# Generals.io Web API

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
  "score": 240140.794239664,  # Some metric generals.io uses to rank the "best" maps (vs "top" maps, where the only factor is the number of upvotes.
  "upvotes": 749  # The number of upvotes
}
```

#### Additional information about the `map` parameter

```
g: general
m: mountain
a number (e.g. 200): city with that amount of army
n[number] (e.g. n200): neutral army with that amount of army
s: swamp
l: lookout
<nothing>: normal tile
```
TODO: add data for observatory tiles (maybe o?)

