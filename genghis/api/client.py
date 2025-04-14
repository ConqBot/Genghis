import asyncio
import re
from datetime import datetime
from enum import Enum, IntEnum

import aiohttp
import json
import uuid
from typing import List, Any, Callable, Dict, Literal, Optional
import logging

from genghis.api import *

logging.basicConfig(level=logging.DEBUG)


class Status(IntEnum):
    IDLE = 0
    IN_QUEUE = 1
    IN_GAME = 2

class Game(Enum):
    FFA = "ffa"
    ONES = "duel"
    TWOS = "2v2"





class GeneralsClient:
    def __init__(self, user_id, server, log_name=None):
        """
        Initialize the WebSocket client.

        Args:
            uri (str): WebSocket server URI (e.g., 'ws://localhost:8765')
        """
        self.user_id = user_id
        self.server = server
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

        self.logger = logging.getLogger(f"genghis.webclient[{self.user_id}]") if log_name is None \
            else logging.getLogger(f"genghis.webclient[{log_name}]")


        # Websocket management
        self._session = None
        self._ws = None
        self.connected = False
        self._session_id = None
        self._message_queue = asyncio.Queue()
        self._callbacks = {}
        self._solicited_response_handlers = {}
        self._unsolicited_response_handlers = {}
        self._tasks = []
        self._require_heartbeat_response = False

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


        self.register_handler("chat_message", self._process_chat_messages, solicited=False)







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
        await self._update_session()
        try:
            self._session = aiohttp.ClientSession()
            self._ws = await self._session.ws_connect(self._websocket_connection_url, ssl=False)
            log.info(f"Connected to gateway: {self._websocket_connection_url!r}")

            # Initialization messages
            await self._message_queue.put("5")
            log.debug("Sent initial message, gateway is ready to use")
            self.connected = True

            self._tasks = [
                asyncio.create_task(self._receive_messages(), name="receive-messages"),
                asyncio.create_task(self._send_messages(), name='send-messages'),
            ]

            # Wait for tasks to complete (will exit on cancellation or error)
            await asyncio.gather(*self._tasks, return_exceptions=True)


        except Exception as e:
            log.error(f"Failed to connect to gateway: {e}")
            self.connected = False
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
        self.connected = False

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
        while not self.connected:
            await asyncio.sleep(1)
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
                    self.logger.error(f"Callback error: {e}")


            self._callbacks[message_id] = {
                "callback": wrapped_callback,
                "request": data
            }


        await self._message_queue.put(message)
        self.logger.debug(f"Queued message: {message}")

        if return_callback_value and callback:
            # Wait for the callback result and return it
            return await result_future

        return message_id

    async def _send_messages(self):
        """
        Process the message queue and send messages to the server.
        """
        while self.connected:
            try:
                message = await self._message_queue.get()
                await self._ws.send_str(message)
                self.logger.debug(f"Sent: {message}")
                self._message_queue.task_done()
            except Exception as e:
                self.logger.error(f"Error sending message: {e}")
                break

    async def _receive_messages(self):
        """
        Receive and process messages from the server.
        """
        while self.connected:
            try:
                msg = await self._ws.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self.logger.debug(f"Received: {msg.data}")
                    await self._process_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    self.logger.info("Connection closed")
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.logger.error(f"WebSocket error: {self._ws.exception()}")
                    break
            except Exception as e:
                self.logger.error(f"Error receiving message: {e}")
                break


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

            if data[0] in self._unsolicited_response_handlers:
                all_message_handlers = self._unsolicited_response_handlers[data[0]]

                for message_handler_data in all_message_handlers:
                    message_handler = message_handler_data["callback"]
                    return await message_handler(data[1:])



                del self._callbacks[prefix]




        except Exception as e:
            log.error(f"Error while processing message {message!r}: {e}")

    def register_handler(self, name: str, handler: Callable[[List[Any], List[Any]], None], send_to_handler: Literal["all", "response", "request"] = "all", solicited=False):
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


    # async def _callback_get_notifications(self, request, response):
    #     print(request, response)
    #
    #
    # async def get_notifications(self, user_id=None):
    #     if not user_id:
    #         user_id = self.user_id
    #
    #     v = await self.send_message(["get_notifs", user_id], callback=None)  # Don't expect a response
    #     return v


    async def join(self, mode=Literal["2v2", "duel", "ffa", "private"], team=None, lobby=None):
        assert mode in ["2v2", "duel", "ffa", "private"], "Invalid mode"

        if mode == "2v2":
            await self.send_message(["join_team", "matchmaking" if team is None else team, self.user_id, NBK], callback=None)
        elif mode == "private":
            await self.send_message(["join_private", lobby, self.user_id, NBK], callback=None)
            self._chat_channel = "chat_custom_queue_" + lobby

        elif mode == "duel":
            await self.send_message(["join_1v1", self.user_id, NBK], callback=None)
        elif mode == "ffa":
            await self.send_message(["play", self.user_id, NBK], callback=None)

    async def _process_chat_messages(self, response):
        log = self.logger.getChild("chat")
        assert self._chat_channel is not None and self._chat_channel == response[0], f"Error when receiving chat message {response}: channel {response[0]!r} does not match up with chat channel {self._chat_channel!r}"
        data = response[1]
        owner = "SERVER" if "username" not in data else data["username"]
        log.info(f"{owner}: {data['text']}")






# Example usage
async def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Create client
    user_id = "tmZzkWHo3"
    server = "us"

    client = GeneralsClient(user_id, server, log_name="aiotest1")


    # Register a handler for a specific message type
    async def handle_hello(responses):
        print(f"Received get_username response: {responses}")


    client.register_handler("get_username", handle_hello, send_to_handler="response")

    # Connect and send some messages
    try:
        async def send_example_messages():
            # Send a message with a callback
            def on_response(responses):
                print(f"Callback response: {responses}")


            await asyncio.gather(
                client.get_username(),
                client.is_supporter(),
                client.check_moderation(),
                client.join(mode="private",lobby='abcd')
            )
            # await client.send_message("test", [1, 2, 3])

        # Run connection and message sending concurrently
        await asyncio.gather(
            client.connect(),
            send_example_messages()
        )
    except KeyboardInterrupt:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())