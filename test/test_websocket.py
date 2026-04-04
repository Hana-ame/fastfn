# test/test_websocket.py

"""
测试 WebSocket 端点: ws://localhost:8000/ws?user=testuser

依赖库: websockets (安装: pip install websockets)
"""

import asyncio
import json
import websockets

# 测试配置
WS_URL = "ws://localhost:8000/ws?user=testuser"
TEST_MESSAGE = "hello from client"
EXPECTED_PUSH_COUNT = 3   # 期望至少收到的推送消息条数
RECEIVE_TIMEOUT = 5       # 接收消息超时（秒）

async def test_websocket_endpoint():
    print(f"Connecting to {WS_URL} ...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("Connected.")

            # 用于收集收到的推送消息
            push_messages = []
            # 用于标识是否已收到对发送消息的回复
            reply_received = False

            # 辅助函数：接收一条消息并判断类型
            async def receive_one():
                nonlocal reply_received
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=RECEIVE_TIMEOUT)
                    # 尝试解析 JSON，若成功且包含 "timestamp" 字段则视为推送数据
                    try:
                        data = json.loads(msg)
                        if "timestamp" in data:
                            push_messages.append(data)
                            print(f"[PUSH] {data}")
                            return "push"
                        else:
                            # 否则视为对输入消息的回复
                            if msg.startswith("Input processed:"):
                                reply_received = True
                                print(f"[REPLY] {msg}")
                                return "reply"
                            else:
                                print(f"[UNKNOWN] {msg}")
                                return "unknown"
                    except json.JSONDecodeError:
                        # 非 JSON 字符串，可能是回复或纯文本推送
                        if msg.startswith("Input processed:"):
                            reply_received = True
                            print(f"[REPLY] {msg}")
                            return "reply"
                        else:
                            print(f"[TEXT] {msg}")
                            return "text"
                except asyncio.TimeoutError:
                    print("Timeout waiting for message.")
                    return None

            # 1. 等待第一条推送消息（连接后 1 秒内应到达）
            print("\nWaiting for first push message...")
            first_msg_type = await receive_one()
            assert first_msg_type == "push", "Did not receive push message as first message"

            # 2. 发送一条测试消息，并等待回复
            print(f"\nSending test message: {TEST_MESSAGE}")
            await websocket.send(TEST_MESSAGE)
            print("Waiting for reply...")
            # 注意：在等待回复期间，可能同时会收到推送消息，但 receive_one 会处理任意类型
            # 我们需要持续接收直到收到回复，或者超时。
            reply_timeout = asyncio.get_event_loop().time() + RECEIVE_TIMEOUT
            while not reply_received:
                if asyncio.get_event_loop().time() > reply_timeout:
                    raise AssertionError("Did not receive reply within timeout")
                await receive_one()
            print("Reply received.")

            # 3. 继续接收若干秒，确保推送消息持续到达（至少 EXPECTED_PUSH_COUNT 条）
            print(f"\nWaiting for at least {EXPECTED_PUSH_COUNT} push messages in total...")
            # 计算还需要多少条推送
            needed = EXPECTED_PUSH_COUNT - len(push_messages)
            while needed > 0:
                msg_type = await receive_one()
                if msg_type == "push":
                    needed -= 1
                # 如果收到回复，忽略（正常情况下不会再有额外回复）
            print(f"Successfully received {len(push_messages)} push messages.")

            # 4. 验证推送消息格式：每个都包含 "timestamp" 字段且时间戳递增（粗略验证）
            timestamps = [msg["timestamp"] for msg in push_messages]
            assert all(isinstance(ts, (int, float)) for ts in timestamps), "Timestamp missing or invalid type"
            assert timestamps == sorted(timestamps), "Timestamps not in increasing order"
            print("Push message format validation passed.")

            print("\nAll tests passed!")

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closed unexpectedly: {e}")
        raise
    except Exception as e:
        print(f"Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_websocket_endpoint())