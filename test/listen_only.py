# test/listen_only.py

"""
无限收听脚本：连接 WebSocket 并持续打印服务器推送的消息。
用法：python listen_only.py
"""

import asyncio
import websockets
import json
from datetime import datetime

WS_URL = "wss://laptop-8000.moonchan.xyz/ws?user=testuser"

async def listen_forever():
    print(f"Connecting to {WS_URL} ...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("Connected. Listening for messages (Ctrl+C to stop)...\n")
            while True:
                # 接收消息（阻塞）
                message = await websocket.recv()
                # 打印时间戳和消息内容
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                # 尝试将消息格式化为 JSON 以便阅读
                try:
                    data = json.loads(message)
                    print(f"[{timestamp}] {json.dumps(data, indent=2, ensure_ascii=False)}")
                except json.JSONDecodeError:
                    print(f"[{timestamp}] {message}")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"\nConnection closed: {e}")
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(listen_forever())
    except KeyboardInterrupt:
        print("\nExited.")