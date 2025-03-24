import asyncio
import json
import ssl
import threading
import time
import traceback
from typing import Callable, Literal, Tuple
import aiohttp
import numpy as np
from ratelimit import limits
from aioconsole import ainput
from genghis.game.observation import Observation


class IO_GameState:
    def __init__(self, data: dict):
        self.usernames = data["usernames"]
        self.player_index = data["playerIndex"]
        self.opponent_index = 1 - self.player_index  # works only for 1v1

        self.n_players = len(self.usernames)

        self.map: list[int] = []
        self.cities: list[int] = []

    def update(self, data: dict) -> None:
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

    def get_observation(self) -> Observation:
        width, height = self.map[0], self.map[1]
        size = height * width

        armies = np.array(self.map[2 : 2 + size]).reshape((height, width))
        terrain = np.array(self.map[2 + size : 2 + 2 * size]).reshape((height, width))
        cities = np.zeros((height, width))
        for city in self.cities:
            cities[city // width, city % width] = 1

        generals = np.zeros((height, width))
        for general in self.generals:
            if general != -1:
                generals[general // width, general % width] = 1

        army = armies
        owned_cells = np.where(terrain == self.player_index, 1, 0).astype(bool)
        opponent_cells = np.where(terrain == self.opponent_index, 1, 0).astype(bool)
        neutral_cells = np.where(terrain == -1, 1, 0).astype(bool)
        mountain_cells = np.where(terrain == -2, 1, 0).astype(bool)
        fog_cells = np.where(terrain == -3, 1, 0).astype(bool)
        structures_in_fog = np.where(terrain == -4, 1, 0).astype(bool)
        owned_land_count = self.scores[self.player_index]["tiles"]
        owned_army_count = self.scores[self.player_index]["total"]
        opponent_land_count = self.scores[self.opponent_index]["tiles"]
        opponent_army_count = self.scores[self.opponent_index]["total"]
        timestep = self.turn
        priority = 1 if self.player_index == 0 else 0

        return Observation(
            armies=army,
            generals=generals,
            cities=cities,
            mountains=mountain_cells,
            neutral_cells=neutral_cells,
            owned_cells=owned_cells,
            opponent_cells=opponent_cells,
            fog_cells=fog_cells,
            structures_in_fog=structures_in_fog,
            owned_land_count=owned_land_count,
            owned_army_count=owned_army_count,
            opponent_land_count=opponent_land_count,
            opponent_army_count=opponent_army_count,
            timestep=timestep,
            priority=priority,
        )



class Player:
    def __init__(self, name: str, indice: int, is_us: bool, forcing: bool, team: int) -> None:
        self.name = name
        self.indice = indice
        self.is_us = is_us
        self.forcing = forcing
        self.team = team

class IO_QueueState:
    def __init__(self, queue: dict):
        self._queue = queue
        if "queueTimeLeft" in queue: # We know this is ffa
            self.queue_time_left = queue["queueTimeLeft"]
            self.is_forcing = queue["isForcing"]
            self.number_players = queue["numPlayers"]
        if "options" in queue: # we know this is custom
            self.options = queue["options"]
            self.number_players = queue["numPlayers"]



US_SERVER = "ws.generals.io"
BOT_SERVER = "botws.generals.io"
EU_SERVER = "eu.generals.io"
POLLING_URL = "https://server/socket.io/?EIO=4&transport=polling"
WEBSOCKET_URL = "wss://server/socket.io/?EIO=4&transport=websocket"
WEIRD_CONSTANT = "sd09fjdZ03i0ejwi_changeme"

class GeneralsClient:
    def __init__(self, user_id, bot, server=Literal["bot", "us", "eu"], join_as=Literal["human", "bot"]):
        self.user_id = user_id
        self.bot = bot
        self.socket = None
        self.sid = None
        self.queueing_for = None
        self.current_chat_channel = None
        self.queue = None
        self.in_game = None  # unknown until API request
        self.ping_interval = None
        self.lock = asyncio.Lock()
        self.join_as = join_as
        self._atomic_query_number = 1
        self.username = None
        self._has_checked_username = False
        self.pending_queries = {}
        if server == "us":
            self.polling_url = POLLING_URL.replace("server", US_SERVER)
            self.websocket_url = WEBSOCKET_URL.replace("server", US_SERVER)
        elif server == "bot":
            self.polling_url = POLLING_URL.replace("server", BOT_SERVER)
            self.websocket_url = WEBSOCKET_URL.replace("server", BOT_SERVER)
        elif server == "eu":
            self.polling_url = POLLING_URL.replace("server", EU_SERVER)
            self.websocket_url = WEBSOCKET_URL.replace("server", EU_SERVER)
        else:
            raise ValueError(f"Unknown server {server!r}")

    @property
    def atomic_query_number(self):
        # Certain queries follow the following format
        # SEND 42xyz (e.g. 429 or 4211)
        # RECV 43xyz (e.g. 439 or 4311)
        self._atomic_query_number += 1
        return int("42"+str(self._atomic_query_number))

    @staticmethod
    def _expected_return_atomic_query(query):
        return int("43" + str(query)[2:])


    async def _update_session_id(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.polling_url, data="40", ssl=False) as resp:
                text = await resp.text()
                json_data = text[text.find("{"):]
                data = json.loads(json_data)
                self.sid = data["sid"]
                self.ping_interval = data["pingInterval"] / 1000

            async with session.post(self.polling_url + f"&sid={self.sid}",
                                    data="40", ssl=False) as resp:
                assert await resp.text() == 'ok', "Could not verify Session ID"


    async def connect(self):
        self._atomic_query_number = 1
        await self._update_session_id()
        self.session = aiohttp.ClientSession()
        self.socket = await self.session.ws_connect(f"{self.websocket_url}&sid={self.sid}", ssl=False)

        async with self.lock:
            await self._send(literal="2probe")
            await self._send(prefix=5)

        # Schedule background tasks
        asyncio.create_task(self._recv())
        asyncio.create_task(self._heartbeat())
        print("Restarted connection")


    async def _recv(self):
        """Async receive loop using aiohttp WebSocket"""
        try:
            while True:
                msg = await self.socket.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print("Received:", msg.data)
                    if "[" in msg.data:
                        prefix = int(msg.data[:msg.data.find("[")])
                        data = json.loads(msg.data[msg.data.find("["):])
                        await self._process_response(prefix, data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    await self._cleanup()
                    asyncio.create_task(self.connect())  # Cannot be run from within _recv because this is spawned by connect()
                    return
        except Exception as e:
            print(f"Receive error: {e}")
            print(traceback.format_exc())
        finally:
            await self._cleanup()

    async def _process_response(self, prefix: int, data: list):
        completed = []
        for key, (future, condition) in self.pending_queries.items():
            if not future.done() and condition(prefix, data):
                future.set_result((prefix, data))
                completed.append(key)
        for key in completed:
            self.pending_queries.pop(key, None)
        if not len(data):
            return
        if data[0] == "queue_update":
            self.queue = data[1]
        if data[0] == "pre_game_start":
            self.queueing_for = None

        if data[0] == "game_start":
            self.game = IO_GameState(data[1])
            self.current_chat_channel = data[1]["chat_room"]
        if data[0] == "game_update":
            self.game.update(data[1])
            print(self.game.get_observation().armies)


        

    async def _send(self, prefix: int = None, message: list = None, literal: str = None):
        if literal is not None:
            print("Sending literal:", literal)
            await self.socket.send_str(literal)
        else:
            msg = str(prefix) + json.dumps(message)
            print("Sending message:", msg)
            await self.socket.send_str(msg)

    async def _heartbeat(self):
        while True:
            try:
                async with self.lock:
                    await self._send(prefix=3)
                await asyncio.sleep(self.ping_interval)
            except Exception as e:
                print(f"Heartbeat error: {e}")
                break

    async def _cleanup(self):
        if self.socket and not self.socket.closed:
            await self.socket.close()
        if self.session and not self.session.closed:
            await self.session.close()

    async def query(self, request_prefix: int, query: list,
                    condition: Callable[[int, list], bool] | None = None,
                    timeout: float = 10.0) -> Tuple[int, list]:
        if condition is not None:
            future = asyncio.Future()
            query_id = id(future)
            self.pending_queries[query_id] = (future, condition)

            try:
                await self._send(prefix=request_prefix, message=query)
                return await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Query timed out after {timeout} seconds")
            finally:
                self.pending_queries.pop(query_id, None)
        else:
            await self._send(prefix=request_prefix, message=query)

    async def join_private_lobby(self, room_id):
        # assert self.username is not None and self._has_checked_username,\
        #     "Username not set before attempting to join lobby."
        condition = lambda p, d: d[0] in ["queue_update", "error_join_queue"]
        prefix, data = await self.query(
            request_prefix=42,
            query=["join_private", room_id, self.user_id, WEIRD_CONSTANT, None],
            condition=condition
        )
        if data[0] == "error_join_queue":
            assert data[1] == "", f"Failed to join private lobby: {data[1]}"
        self.queueing_for = f"custom[{room_id}]"
        return prefix, data

    async def cancel(self):
        return await self.query(
            request_prefix=42,
            query=["cancel"],
            condition=None  # For some reason, there is no confirmation that the leave succeeded
        )

    async def get_username(self):
        query_number = self.atomic_query_number
        condition = lambda p, d: p == self._expected_return_atomic_query(query_number)
        self._has_checked_username = True
        prefix, data = await self.query(
            request_prefix=query_number,
            query=["get_username", self.user_id],
            condition=condition
        )
        self.username = data[0]

        if self.username:
            assert not (self.username.startswith("[Bot]") and self.join_as == "human"
                or self.join_as == "human" and not self.username.startswith("[Bot]")), f"Failed to connect as role {self.join_as!r}: username is {self.username!r}"

        return self.username

    async def set_username(self, username):
        if self.join_as == "human":
            return await self.query(
                request_prefix=42,
                query=["set_username", self.user_id, username, WEIRD_CONSTANT, None, None],
                condition=lambda p, d: d[0] == "error_set_username"
            )
        else:
            return await self.query(
                request_prefix=42,
                query=["set_username", self.user_id, username],
                condition=lambda p, d: d[0] == "error_set_username"
            )

    async def join_1v1_queue(self):
        self.queueing_for = "1v1"
        return await self.query(
            request_prefix=42,
            query=["join_1v1", self.user_id, WEIRD_CONSTANT, None, None],
            condition=None  # For some reason, there is no confirmation that the 1v1 join succeeded
        )

    async def join_ffa_queue(self):
        self.queueing_for = "ffa"
        return await self.query(
            request_prefix=42,
            query=["play", self.user_id, WEIRD_CONSTANT, None, None],
            condition=None  # For some reason, there is no confirmation that the ffa join succeeded
        )
    async def join_2v2_team_queue(self, team_id="matchmaking"):
        self.queueing_for = "2v2"
        condition = lambda p, d: d[0] in ["team_update", "team_joined_queue"]
        return await self.query(
            request_prefix=42,
            query=["join_team", team_id, self.user_id, WEIRD_CONSTANT, None, None],
            condition=condition
        )

    async def set_force_start(self, value: bool):
        if self.queueing_for in ["2v2", "1v1", "ffa"]:
            lobby_id = None
        elif self.queueing_for.startswith("custom"):
            lobby_id = self.queueing_for[self.queueing_for.find("[")+1:self.queueing_for.find("]")]


        condition = lambda p, d: ((d[0] == "queue_update" and d[1]["isForcing"] == value)
                                  or d[0] == "pre_game_start")
        return await self.query(
            request_prefix=42,
            query=["set_force_start", lobby_id, value],
            condition=condition
        )

    async def surrender(self):
        condition = lambda p, d: d[0] == "game_lost" and d[1]["surrender"]
        return await self.query(
            request_prefix=42,
            query=["surrender"],
            condition=condition
        )

    async def change_private_game_settings(self):

        pass

    async def change_color(self):
        pass


    async def send_chat_message(self):
        pass



    async def subscribe_to_public_custom_games(self):
        return await self.query(
            request_prefix=42,
            query=["listen_public_customs"],
            condition=None
        )

    async def unsubscribe_to_public_custom_games(self):
        return await self.query(
            request_prefix=42,
            query=["stop_listen_public_customs"],
            condition=None
        )



    async def stars_and_rank(self):
        pass

    # async def is_supporter(self):
    #
    #     pass

    async def get_notifications(self):
        """

        :return:
        """
        pass

    async def get_moderation_info(self):
        pass

    async def link_email(self, email):
        return await self.query(
            request_prefix=self.atomic_query_number,
            query=["link_email", email],
            condition=None
        )
        pass

    # async def set_custom_host(self, host):
    #     pass

    # async def set_custom_team(self, team):
    #     assert self.queueing_for.startswith("custom"),\
    #         "This function only works when you are queuing for a custom game."
    #
    #     return await self.query(
    #         request_prefix=self.atomic_query_number,
    #         query=["set_custom_team", self.queueing_for.replace("custom[", "").replace("]"), team, WEIRD_CONSTANT, None, None],
    #         condition=None
    #     )

    async def recover_account(self, email):

        return await self.query(
            request_prefix=self.atomic_query_number,
            query=["recover_account", email],
            condition=None
        )

    async def _drop_connection(self):
        """
        sends an empty message, which drops the connection. This should trigger _recv to restart the connection.
        :return:
        """
        await self._send(message=[])

    async def mod(self):
        # Returns muted, <disabled>, <warning>,
        await self._send(prefix=421, message=["check_moderation", self.user_id])

    async def play(self, mode):
        await self._send(prefix=422, message=["play", self.user_id, WEIRD_CONSTANT, mode, None])

    async def ping_worker(self):
        await self._send(prefix=42, message=["ping_worker"])

    async def ping_server(self):
        await self._send(prefix=42, message=["ping_server"])
# "X8xuc1_ba"
g = GeneralsClient(user_id="", server="bot", bot=None, join_as="bot")

async def main():
    await g.connect()
    await g.get_username()
    while True:
        command = (await ainput("> ")).split(" ")
        if command == [""]:
            continue
        arguments = command[1:]
        for i, arg in enumerate(command[1:]):
            if arg.lower() == "true":
                arguments[i] = True
            elif arg.lower() == "false":
                arguments[i] = False
            elif arg.lower() == "null":
                arguments[i] = None
            elif arg.isdigit():
                arguments[i] = int(arg)
        try:
            print(await getattr(g, command[0])(*arguments))
        except AttributeError:
            recombined = [command[0]]
            recombined.extend(arguments)

            print(command, recombined, arguments)
            await g._send(prefix=421, message=recombined)
asyncio.get_event_loop().run_until_complete(main())