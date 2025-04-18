import asyncio
import dataclasses
import math
import re
import sys
import time
import traceback
from enum import Enum, IntEnum
from random import random

import aiohttp
import json
from typing import List, Any, Callable, Dict, Literal, Optional
import logging

from aiohttp import ClientTimeout

from genghis.api import *
from genghis.game.formatter import Formatter
from genghis.game.game import OnlineGame

# Configure root logger
root_logger = logging.getLogger("root")
root_logger.setLevel(logging.DEBUG)

logging.basicConfig(level=logging.DEBUG)


# create console handler with a higher log level
ch = logging.StreamHandler(stream=sys.stdout)
ch.setLevel(logging.DEBUG)

ch.setFormatter(Formatter())  # custom formatter
root_logger.handlers = [ch]  # Make sure to not double print

class Status(IntEnum):
    IDLE = 0
    QUEUING = 1
    PLAYING = 2

class Game(Enum):
    FFA = "ffa"
    ONES = "duel"
    TWOS = "2v2"
    CUSTOM = "custom"

class Server(Enum):
    US = "us"
    EU = "eu"
    BOT = "bot"


# verification functions

def is_bool(val):
    return type(val) is bool

def is_0_to_1(val):
    return type(val) in [int, float] and 0 <= val <= 1

def is_valid_player_number(val):
    return type(val) is int and 2 <= val <= 16

def is_valid_game_speed(val):
    return val in [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4]

class OptionType(IntEnum):
    GAME_SETTING = 0
    MAP_SETTING = 1
    MODIFIER = 2

class CustomOption(Enum):
    MODIFIER_LEAPFROG = (OptionType.MODIFIER, is_bool, 0, False)
    MODIFIER_CITY_STATE = (OptionType.MODIFIER, is_bool, 1, False)
    MODIFIER_MISTY_VEIL = (OptionType.MODIFIER, is_bool, 2, False)
    MODIFIER_CRYSTAL_CLEAR = (OptionType.MODIFIER, is_bool, 3, False)
    MODIFIER_SILENT_WAR = (OptionType.MODIFIER, is_bool, 4, False)
    MODIFIER_DEFENSELESS = (OptionType.MODIFIER, is_bool, 5, False)
    MODIFIER_WATCHTOWER = (OptionType.MODIFIER, is_bool, 6, False)
    MODIFIER_TORUS = (OptionType.MODIFIER, is_bool, 7, False)
    MODIFIER_FADING_SMOG = (OptionType.MODIFIER, is_bool, 8, False)
    MODIFIER_DEFECTION = (OptionType.MODIFIER, is_bool, 9, False)

    MAP_CITY_DENSITY = (OptionType.MAP_SETTING, is_0_to_1, "city_density", 0.5)
    MAP_CITY_FAIRNESS = (OptionType.MAP_SETTING, is_0_to_1, "city_fairness", 0.5)
    MAP_SPAWN_FAIRNESS = (OptionType.MAP_SETTING, is_0_to_1, "spawn_fairness", 0.5)
    MAP_MOUNTAIN_DENSITY = (OptionType.MAP_SETTING, is_0_to_1, "mountain_density", 0.5)
    MAP_SWAMP_RATIO = (OptionType.MAP_SETTING, is_0_to_1, "swamp_ratio", 0)
    MAP_DESERT_RATIO = (OptionType.MAP_SETTING, is_0_to_1, "desert_ratio", 0)
    MAP_LOOKOUT_RATIO = (OptionType.MAP_SETTING, is_0_to_1, "lookout_ratio", 0)
    MAP_OBSERVATORY_RATIO = (OptionType.MAP_SETTING, is_0_to_1, "observatory_ratio", 0)
    MAP_WIDTH = (OptionType.MAP_SETTING, is_0_to_1, "width", 0.5)
    MAP_HEIGHT = (OptionType.MAP_SETTING, is_0_to_1, "height", 0.5)

    GAME_PUBLIC = (OptionType.GAME_SETTING, is_bool, "public", False)
    GAME_SPECTATOR_CHAT = (OptionType.GAME_SETTING, is_bool, "spectate_chat", False)
    GAME_SPECTATE_ON_DEFEAT = (OptionType.GAME_SETTING, is_bool, "defeat_spectate", True)
    GAME_MAX_PLAYERS = (OptionType.GAME_SETTING, is_valid_player_number, "max_players", 16)
    GAME_SPEED = (OptionType.GAME_SETTING, is_valid_game_speed, "game_speed", 1)
    GAME_CHAT_RECORDING_DISABLED = (OptionType.GAME_SETTING, is_bool, "chatRecordingDisabled", False)




def build_modifier_ids():
    mod_ids = {}
    for member in CustomOption.__members__:
        data = getattr(CustomOption, member).value
        if data[0] == OptionType.MODIFIER:
            mod_ids[data[2]] = getattr(CustomOption, member)
    return mod_ids

MODIFIERS = build_modifier_ids()

print(CustomOption.__members__)

@dataclasses.dataclass
class QueuePlayerInfo:
    index: int
    username: str | None  # Only provided in custom games
    me: bool
    color: int
    forcing: bool | None  # Force status is known for custom games
    host: bool | None  # Whether user is host
    team: int | None  # The team ID the user is on (custom games only)


@dataclasses.dataclass
class QueueInfo:
    modifiers: list
    map: str | None
    players: list[QueuePlayerInfo]
    index: int  # Our index
    forcing: bool
    time_left: int | None  # FFA has queue time remaining
    host: bool | None  # Whether the user is the host (custom lobby only)
    public: bool | None  # Whether the game is public (custom lobby only)
    settings: list  # Custom games only, everything not modifier
    @property
    def force_start_threshold(self):
        return math.ceil(0.7 * len(self.players))  # Ripped from source code

@dataclasses.dataclass
class GamePlayerInfo:
    army: int
    tiles: int
    index: int
    color: int
    username: str
    stars: float | None


@dataclasses.dataclass
class GameInfo:
    modifiers: list
    map: str | None
    players: list[GamePlayerInfo]
    index: int
    replay_id: str
    state: OnlineGame




class GeneralsClient:
    def __init__(self, user_id, server, log_name=None, lightweight=False):
        """
        Initialize the WebSocket client.

        Args:
            uri (str): WebSocket server URI (e.g., 'ws://localhost:8765')
        """
        self.user_id = user_id
        self.server = server
        self._root_server_url = None
        self.lightweight = lightweight
        if server == Server.US:
            self.polling_url = POLLING_URL.replace("server", US_SERVER)
            self.websocket_url = WEBSOCKET_URL.replace("server", US_SERVER)
            self._root_server_url = US_SERVER
        elif server == Server.BOT:
            self.polling_url = POLLING_URL.replace("server", BOT_SERVER)
            self.websocket_url = WEBSOCKET_URL.replace("server", BOT_SERVER)
            self._root_server_url = BOT_SERVER
        elif server == Server.EU:
            self.polling_url = POLLING_URL.replace("server", EU_SERVER)
            self.websocket_url = WEBSOCKET_URL.replace("server", EU_SERVER)
            self._root_server_url = EU_SERVER
        else:
            raise ValueError(f"Unknown server {server!r}")

        self.logger = logging.getLogger(f"genghis.webclient[{self.user_id}]") if log_name is None \
            else logging.getLogger(f"genghis.webclient[{log_name}]")


        # Websocket management
        self._session = None
        self._ws = None
        self.connected = asyncio.Event()
        self._session_id = None
        self._message_queue = asyncio.Queue()
        self._callbacks = {}
        self._solicited_response_handlers = {}
        self._unsolicited_response_handlers = {}
        self._tasks = []
        self._require_heartbeat_response = False


        # Status
        self.status = Status.IDLE
        self.game_type = None

        # User parameters

        self.username = None
        self.supporter = None

        # Moderation
        self.disabled = None
        self.muted = None
        self.warning = None
        self.warning_reason = None

        # Chat
        self._chat_channel = None

        self._queue = None

        self.queue = None

        if not self.lightweight:
            self.register_handler("chat_message", self._process_chat_messages, solicited=False)
            self.register_handler("queue_update", self._process_queue_update, solicited=False)
            self.register_handler("pre_game_start", self._process_pregame, solicited=False)
            self.register_handler("game_start", self._process_game_start, solicited=False)
            asyncio.gather(self._update_queue(), self.get_username(), self.check_moderation(), self.is_supporter())




    async def _update_queue(self):
        self._queue = await self.send_message(["queue_count"], callback=lambda request, response: response[0],
                                       return_callback_value=True)


    @property
    async def queue_count(self):
        return self._queue

    @property
    def queue_ffa(self):
        if self._queue:
            return self._queue[0]

    @property
    def queue_1v1(self):
        if self._queue:
            return self._queue[1]

    @property
    def queue_2v2(self):
        if self._queue:
            return self._queue[2]



    async def _update_session(self):
        log = self.logger.getChild("session")
        async with aiohttp.ClientSession() as session:
            async with session.get(self.polling_url, data="40", ssl=False) as resp:
                text = await resp.text()
                json_data = text[text.find("{"):]
                data = json.loads(json_data)
                self._session_id = data["sid"]
                log.debug(f"Got Session ID {self._session_id!r}")


            async with session.post(self._session_verification_url,
                                    data="40", ssl=False) as resp:
                assert await resp.text() == 'ok', "Could not verify Session ID"
                log.debug(f"Successfully verified Session ID {self._session_id!r}")

    @property
    def _websocket_connection_url(self):
        return self.websocket_url + f"&sid={self._session_id}"

    @property
    def _session_verification_url(self):
        return self.polling_url + f"&sid={self._session_id}"


    async def connect(self):
        log = self.logger.getChild("connect")
        """
        Connect to the WebSocket server and start message processing.
        """
        log.debug("Obtaining session ID...")
        await self._update_session()
        log.debug(f"Connecting to gateway: {self._websocket_connection_url}")
        try:
            self._session = aiohttp.ClientSession()
            self._ws = await self._session.ws_connect(self._websocket_connection_url, ssl=False)
            log.info(f"Connected to gateway: {self._websocket_connection_url!r}")

            # Initialization messages
            await self._message_queue.put("5")
            log.debug("Sent initial message, gateway is ready to use")
            self.connected.set()

            self._tasks = [
                asyncio.create_task(self._receive_messages(), name="receive-messages"),
                asyncio.create_task(self._send_messages(), name='send-messages'),
            ]

            # Wait for tasks to complete (will exit on cancellation or error)
            await asyncio.gather(*self._tasks, return_exceptions=True)


        except Exception as e:
            log.error(f"Failed to connect to gateway: {e}")
            self.connected.clear()
            await self.disconnect()

    async def disconnect(self):
        """
        Disconnect from the WebSocket server.
        """
        log = self.logger.getChild("disconnect")
        log.info(f"Disconnecting from gateway: {self._websocket_connection_url!r}")
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        self.connected.clear()

        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    # Wait for the task to handle cancellation
                    await task
                except asyncio.CancelledError:
                    log.debug(f"Task {task.get_name()} cancelled successfully")
                except Exception as e:
                    log.error(f"Error during task cancellation: {e}")
        log.info("Client disconnected from server")


    async def send_message(
        self,
        data: List[Any] | Dict = None,
            prefix: int = None,
        callback: Optional[Callable[[List[Any]], Any]] = None,
        expected_response: Optional[str] = None,
        return_callback_value: bool = True
    ) -> Any:
        """
        Send a message to the server in the format: SEND 4100["name", arg1, arg2, ...]

        Args:
            prefix (int): Message prefix (e.g., 422 for commands).
            data (List[Any] | Dict): Message data to send.
            callback (Callable, optional): Callback to handle response.
            expected_response (str, optional): Expected response ID for tracking.
            return_callback_value (bool): If True, return the callback's result.

        Returns:
            Any: If return_callback_value is True, returns the callback's result.
                 Otherwise, returns the message ID as a string.
        """
        log = self.logger.getChild("queue_message")
        await self.connected.wait()
        if prefix is None:
            numbers_set = set(self._callbacks.keys())
            suffix = 1
            while True:
                prefix = int(f"42{suffix}")
                check_against = int(f"43{suffix}")
                if check_against not in numbers_set:
                    break
                suffix += 1

        message = f"{prefix}{json.dumps(data)}"

        if expected_response:
            message_id = expected_response
        elif str(prefix).startswith("42"):
            message_id = int("43" + str(prefix)[2:])
        else:
            raise ValueError(f"Unknown message prefix {prefix!r} and expected_response not provided!")

        # Create a Future to capture the callback result if needed
        result_future = asyncio.Future() if return_callback_value else None



        if callback:
            # Wrap the callback to capture its return value
            async def wrapped_callback(request, response):
                try:
                    result = callback(request=request, response=response)
                    if return_callback_value:
                        result_future.set_result(result)
                except Exception as e:
                    if return_callback_value:
                        result_future.set_exception(e)
                    log.error(f"Callback error: {e}")


            self._callbacks[message_id] = {
                "callback": wrapped_callback,
                "request": data
            }


        await self._message_queue.put(message)
        log.debug(f"Queued message: {message}")

        if return_callback_value and callback:
            # Wait for the callback result and return it
            return await result_future

        return message_id

    async def _send_messages(self):
        """
        Process the message queue and send messages to the server.
        """
        log = self.logger.getChild("send")
        while self.connected.is_set():
            try:
                message = await self._message_queue.get()
                await self._ws.send_str(message)
                log.debug(message)
                self._message_queue.task_done()
            except Exception as e:
                log.error(f"Error sending message: {e}")
                break

    async def _receive_messages(self):
        """
        Receive and process messages from the server.
        """
        log = self.logger.getChild("receive")
        while self.connected.is_set():
            try:
                msg = await self._ws.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    log.debug(msg.data)
                    await self._process_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    log.info("connection closed")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.error(f"WebSocket error: {self._ws.exception()}")
                    break
            except Exception as e:
                print("err")
                log.error(f"Error receiving message: {e}")
                traceback.print_exc()



    async def _process_message(self, message: str):
        """
        Process incoming messages in the format: RECV 4101["name", response, response2, ...]

        Args:
            message (str): Raw message from server
        """
        log = self.logger.getChild("process_message")
        try:

            parsed = re.findall("^(\d+)(.*)", message)[0]

            prefix = int(parsed[0])
            data = parsed[1]

            # Special case: heartbeat request


            if prefix == 2 and not data:
                log.debug("Received heartbeat request, sending heartbeat")
                await self._message_queue.put("3")


                # Periodic updates
                if not self.lightweight:
                    asyncio.create_task(self._update_queue())
                return

            try:
                data = json.loads(data)
            except json.decoder.JSONDecodeError:  # Data isn't JSON, pass it on anyway
                log.warning(f"Received invalid JSON from WebSocket, ignoring message. prefix={prefix!r}, json={data!r}")
                return


            # Check for callback
            if prefix in self._callbacks:

                callback_information = self._callbacks[prefix]

                # Check if the callback is a coroutine function
                callback = callback_information["callback"]
                request = callback_information["request"]
                if asyncio.iscoroutinefunction(callback):
                    # Await the callback if it's asynchronous
                    await callback(request=request, response=data)
                else:
                    # Call it directly if it's synchronous
                    callback(request=request, response=data)

                self._callbacks.pop(prefix)  # Remove spent callback



                if request[0] in self._solicited_response_handlers: # Call the linked handler if set up
                    all_message_handlers = self._solicited_response_handlers[request[0]]
                    for message_handler_data in all_message_handlers:
                        message_handler = message_handler_data["callback"]
                        mode = message_handler_data["mode"]
                        if mode == "all":
                            return await message_handler(request[1:], data)
                        elif mode == "request":
                            return await message_handler(request[1:])
                        elif mode == "response":
                            return await message_handler(data)


            if type(data) is list and data and type(data[0]) is str and data[0] in self._callbacks:  # If the string matches up in the callbacks, call callback
                callback_information = self._callbacks[data[0]]
                print(callback_information)
                # Check if the callback is a coroutine function
                callback = callback_information["callback"]
                request = callback_information["request"]
                print(callback, request)
                if asyncio.iscoroutinefunction(callback):
                    # Await the callback if it's asynchronous
                    await callback(request=request[1:], response=data[1:])
                else:
                    # Call it directly if it's synchronous
                    callback(request=request[1:], response=data[1:])


            if type(data) is list and data and type(data[0]) is str and data[0] in self._unsolicited_response_handlers:
                all_message_handlers = self._unsolicited_response_handlers[data[0]]

                for message_handler_data in all_message_handlers:
                    message_handler = message_handler_data["callback"]
                    return await message_handler(data[1:])



                del self._callbacks[prefix]




        except Exception as e:
            log.error(f"Error while processing message {message!r}: {e}")
            raise e  # TODO: remove

    def register_handler(self, name: str, handler: Callable[[List[Any], List[Any]], None],
                         send_to_handler: Literal["all", "response", "request"] = "all", solicited=False):
        """
        Register a handler for specific message names.

        Args:
            name (str): Message name to handle
            handler (Callable): Function to call with response data
        """
        assert send_to_handler in ["all", "response", "request"], f"Invalid send_to_handler mode: {send_to_handler!r}"

        if solicited:
            if name not in self._solicited_response_handlers:
                self._solicited_response_handlers[name] = [{"callback": handler, "mode": send_to_handler}]
            else:
                self._solicited_response_handlers[name].append({"callback": handler, "mode": send_to_handler})
        else:
            if name not in self._unsolicited_response_handlers:
                self._unsolicited_response_handlers[name] = [{"callback": handler}]
            else:
                self._unsolicited_response_handlers[name].append({"callback": handler,})

        self.logger.info(f"Registered handler for: {name}, send_to_handler={send_to_handler!r}, solicited={solicited!r}")

    def _callback_get_username(self, request, response):
        # Request format: ["get_username", user_id]
        # Response format: [username]
        # If the request ID is the class ID (user_id=None), set self.username
        if request[1] == self.user_id:
            self.username = response[0]
        return response[0]

    def _callback_is_supporter(self, request, response):
        # Request format: ["is_supporter", user_id]
        # Response format [bool]
        if request[1] == self.user_id:
            self.supporter = response[0]
        return response[0]


    async def get_username(self, user_id=None):
        if not user_id:
            user_id = self.user_id

        v = await self.send_message( ["get_username", user_id], callback=self._callback_get_username)
        return v

    async def is_supporter(self, user_id=None):
        if not user_id:
            user_id = self.user_id

        v = await self.send_message( ["is_supporter", user_id], callback=self._callback_is_supporter)
        return v

    # async def get_notifs(self, user_id=None):
    #     if not user_id:
    #         user_id = self.user_id
    #
    #     v = await self.send_message(["get_notifs", user_id], callback=self._callback_get_notifs)
    #
    # def _callback_get_notifs(self, request, response):
    #     print(request, response)


    def _callback_set_username(self, request, response):
        return response[0]

    async def set_username(self, username, bot=True):
        if not self.supporter and self.username is not None:  # Not supporter: can't change
            raise ValueError("Can't set username because this account is not a supporter and already has one!")
        if bot and self.server != Server.BOT:
            raise ValueError(f"Can't create a bot account because the connected server is {self.server},"
                             f" not the bot server!")


        if bot:
            v = await self.send_message(["set_username", self.user_id, username], callback=self._callback_set_username, expected_response="error_set_username", return_callback_value=True)
        else:
            v = await self.send_message(["set_username", self.user_id, username, NBK], callback=self._callback_set_username, expected_response="error_set_username", return_callback_value=True)

        if v:
            raise PermissionError(f"Error setting username {username!r} for account {self.user_id!r}: {v!r}")

        return True



    def _callback_get_mod_info(self, request, response):
        muted = response[0]
        disabled = response[1]
        warning = response[2] is not None
        warning_reason = response[2]

        if request[1] == self.user_id:
            self.disabled = disabled
            self.warning = warning
            self.warning_reason = warning_reason
            self.muted = muted

        return {"muted": muted, "disabled": disabled,
                "warning": warning,
                "warning_reason": warning_reason}

    async def check_moderation(self, user_id=None):
        if not user_id:
            user_id = self.user_id

        v = await self.send_message(["check_moderation", user_id], callback=self._callback_get_mod_info)
        return v

    async def send_chat_message(self, message):
        if self._chat_channel is None:
            raise TypeError("Chat channel must be set before sending message"
                            " - i.e. you are not connected to a chat channel")

        await self._chat_channel.send([""])


    async def set_custom_options(self, options: dict[CustomOption, Any]):
        api_set_value = {}
        for key in options:
            value_to_set = options[key]
            if not type(key) is CustomOption:
                raise TypeError(f"Invalid option type {type(key)}. Expected CustomOption")
            option_data = key.value
            option_type = option_data[0]
            verification_function = option_data[1]
            api_id = option_data[2]
            default_value = option_data[3]
            if value_to_set is None:  # Pass None to explicitly reset value
                value_to_set = default_value
            if not verification_function(value_to_set):
                raise TypeError(f"Invalid value {value_to_set} for option {key}.")
            api_set_value[api_id] = value_to_set

        await self.send_message(["set_custom_options", "client_lobby", api_set_value], callback=lambda request, response: None, return_callback_value=True)


    async def join(self, mode=Literal["2v2", "duel", "ffa", "private"], team=None, lobby=None):
        assert mode in ["2v2", "duel", "ffa", "private"], "Invalid mode"

        if mode == "2v2":
            # Join 2v2. Note that the team "matchmaking" is the one generals actually joins you do when you use "Join Random Team"
            await self.send_message(["join_team", "matchmaking" if team is None else team, self.user_id, NBK], callback=None)
        elif mode == "private":
            # Private lobby. This uses the lobby ID. We can also deduce the queue message before joining.
            await self.send_message(["join_private", lobby, self.user_id, NBK], callback=None)
            self._chat_channel = "chat_custom_queue_" + lobby

        elif mode == "duel":
            await self.send_message(["join_1v1", self.user_id, NBK], callback=None)
        elif mode == "ffa":
            await self.send_message(["play", self.user_id, NBK], callback=None)

        self.status = Status.QUEUING

    async def _process_chat_messages(self, response):
        log = self.logger.getChild("chat")
        assert self._chat_channel is not None and self._chat_channel == response[0], f"Error when receiving chat message {response}: channel {response[0]!r} does not match up with chat channel {self._chat_channel!r}"
        data = response[1]
        owner = "[SERVER]" if "username" not in data else data["username"]
        log.info(f"{owner}: {data['text']}")

    async def _process_queue_update(self, response):
        pass_through = {}
        data = response[0]
        def set_if_valid(set_to, set_from):
            if set_from in data:
                pass_through[set_to] = data[set_from]
            else:
                pass_through[set_to] = None

        set_if_valid("index", "lobbyIndex")
        set_if_valid("time_left", "queueTimeLeft")
        set_if_valid("forcing", "isForcing")


        is_custom_lobby = "options" in data
        is_ffa_lobby = pass_through["time_left"] is not None


        if is_custom_lobby:
            options = data["options"]

            if pass_through["index"] == 0:  # Host of custom game
                pass_through["host"] = True
            else:
                pass_through["host"] = False

            pass_through["map"] = options["map"]


            pass_through["modifiers"] = [MODIFIERS[mod_id] for mod_id in options["modifiers"]]
            if "public" in options:
                pass_through["public"] = options["public"]  # Should always be true, but won't always be due to bug
            else:
                pass_through["public"] = False


            settings = {}

            for setting in CustomOption.__members__:
                opt = getattr(CustomOption, setting).value
                if opt[0] != OptionType.MODIFIER:
                    if opt[2] in options:
                        settings[getattr(CustomOption, setting)] = options[opt[2]]  # Set to input value
                    else:
                        settings[getattr(CustomOption, setting)] = opt[3]  # Set to default value

            pass_through["settings"] = settings


            players = []
            indices = data["playerIndices"]
            colors = data["playerColors"]
            usernames = data["usernames"]
            teams = data["teams"]
            forcing = data["numForce"]

            for index in range(data["numPlayers"]):
                player_index = indices[index]
                color = colors[index]
                username = usernames[index]
                team = teams[index]
                is_forcing = player_index in forcing

                players.append(QueuePlayerInfo(index=player_index, username=username, color=color, host=player_index == 0, forcing=is_forcing, team=team, me=pass_through["index"] == player_index))

            pass_through["players"] = players
        else:

            pass_through["host"] = None
            pass_through["public"] = None
            pass_through["settings"] = None

        if is_ffa_lobby:
            players = []
            colors = data["playerColors"]
            forcing = data["numForce"]
            for index in range(data["numPlayers"]):
                color = colors[index]
                is_forcing = index in forcing

                players.append(
                    QueuePlayerInfo(index=index, username=None, color=color, host=None,
                                    forcing=is_forcing, team=None, me=pass_through["index"] == index))


        self.queue = QueueInfo(**pass_through)

    async def _process_pregame(self, response):
        self.status = Status.PLAYING
        log = self.logger.getChild("pregame")
        log.info("Game is about to start!")

    async def _process_game_start(self, response):
        data = response[0]
        # 42["game_start",{"playerIndex":0,
        # "playerColors":[0,2],
        # "replay_id":"m0r4mnnGc",
        # "chat_room":"game_1744978746773WMVjiyvdrlQuE6fmAqCs",
        # "usernames":["bagelsarecool1","bagelsarecool4"],
        # "teams":[1,2],
        # "game_type":"custom",
        # "swamps":[],"lights":[],
        # "options":{"map":null,"width":null,"height":null,"game_speed":null,"modifiers":[],"mountain_density":null,"city_density":null,"lookout_density":null,"observatory_density":null,"swamp_density":null,"desert_density":null,"max_players":null,"city_fairness":null,"spawn_fairness":null,"defeat_spectate":null,"spectate_chat":null,"public":null,"chatRecordingDisabled":null,"eventId":null}
        log = self.logger.getChild("game_start")
        self._chat_channel = data["chat_room"]
        log.info(f"Game started! View the replay at https://{self._root_server_url}/replays/{data['replay_id']}")





# Example usage
async def register_example():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Create client
    user_id = "tmZzkWHo3"
    server = Server.US

    uid_prefix = "bagelbot"
    username_prefix = "bagelsarecool"




    for i in range(10,20):
        client = GeneralsClient(uid_prefix + str(i), server)
        success = False

        async def uname_handler(response):
            nonlocal success
            success = response[0] != "You must wait a bit longer before making a new account."
            print(success)




        client.register_handler("error_set_username", handler=uname_handler, solicited=False)
        # Connect and send some messages
        try:
            async def send_example_messages():
                # Send a message with a callback


                await asyncio.gather(
                    client.get_username(),
                    client.is_supporter(),
                    client.check_moderation(),
                )

                while True:
                    print("Sending again", client.username)
                    if client.username is not None:
                        break
                    else:
                        try:
                            await client.set_username(username_prefix + str(i), False)
                        except Exception:
                            await asyncio.sleep(300)
                            continue

                    break


                await asyncio.gather(client.disconnect())

                # await client.send_message("test", [1, 2, 3])

            # Run connection and message sending concurrently
            await asyncio.gather(
                client.connect(),
                send_example_messages()
            )
        except KeyboardInterrupt:
            await client.disconnect()



async def main():
    client = GeneralsClient("bagelbot1", Server.US)
    print('yo')
    t = asyncio.create_task(client.connect(), name="bot-mainloop")
    await client.join(mode="private", lobby="client_lobby")
    await asyncio.sleep(1)
    print('so', [t for t in asyncio.all_tasks()])

    while True:
        await asyncio.sleep(2)
        await client.send_message(["set_force_start", "client_lobby", True])


if __name__ == "__main__":
    asyncio.run(main())

