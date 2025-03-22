import json
import ssl
import threading
import time

import requests
from websocket import WebSocketConnectionClosedException, create_connection

user_id = "X8xuc1_ba"  # Skibidious
game_id = "websocket"

msg = requests.get("https://ws.generals.io/socket.io/?EIO=4&transport=polling" , data="40")
print(msg.text)
json_data = msg.text[msg.text.find("{"):]
prefix = msg.text[:msg.text.find("{")]

data = json.loads(json_data)
sid = data["sid"]
checkOne = requests.post("https://ws.generals.io/socket.io/?EIO=4&transport=polling&sid=" + sid, data="40")
print(checkOne.text)

third = requests.get("https://ws.generals.io/socket.io/?EIO=4&transport=polling&sid=" + sid)
print(third.text)

ip = "wss://ws.generals.io/socket.io/?EIO=4&transport=websocket"

socket = create_connection(ip + f"&sid={sid}", sslopt={"cert_reqs": ssl.CERT_NONE})


def send_msg(msg, prefix=""):
    print("Sending msg: {}".format(prefix + msg))
    socket.send(prefix + msg)

lock = threading.RLock()

def _start_sending_heartbeat():
    while True:
        try:
            with lock:
                send_msg("3")

        except WebSocketConnectionClosedException:
            print("Connection Closed - heartbeat")
            break
        time.sleep(15)

def recv_msg():
    msg = socket.recv()
    if msg == "":
        return None, None
    if "{" not in msg:
        return None, msg
    json_data = msg[msg.find("["):]
    prefix = msg[:msg.find("[")]
    print(msg)
    data = json.loads(json_data)
    print("Received message:", msg)
    return int(prefix), data

def _spawn(f):
	t = threading.Thread(target=f)
	t.daemon = True
	t.start()


# prefix, data = recv_msg()
# sid = data["sid"]
# send_msg("5")
# print("SID:", sid)

send_msg("2probe")
send_msg("5")
prefix, data = recv_msg()
print("5response", prefix, data)
_spawn(_start_sending_heartbeat)
send_msg(f'["join_private","{game_id}","{user_id}","sd09fjdZ03i0ejwi_changeme",null]', "42")
#send_msg('["make_custom_public", "elkr"]')
def recv():
    while True:
        print("receiving...")
        prefix, data = recv_msg()
        print(prefix, data)

_spawn(recv)
while True:
    command = input().split(" ")
    print(command[1:])
    send_msg(json.dumps(command[1:]), command[0])



