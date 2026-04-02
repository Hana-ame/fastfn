# game/ws.py
import time
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from game.world import get_data, process_input

router = APIRouter()

@router.websocket("/ws")
async def websocket_echo(websocket: WebSocket):
    await websocket.accept()

    # 从 URL 查询参数中获取 user，例如：/ws?user=alice
    user = websocket.query_params.get("user")
    if not user:
        user = "anonymous"   # 默认用户
        
    # 定时推送任务：每秒调用一次 get_data(user, timestamp) 并发送
    async def send_periodic_data():
        try:
            while True:
                timestamp = time.time()
                data = get_data(user, timestamp)   # 从外部文件获取数据
                # 如果 data 不是字符串，可以转为 JSON 字符串或使用 send_json
                await websocket.send_text(json.dumps(data))
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            # 连接断开时自动退出循环
            pass

    # 启动后台定时任务
    send_task = asyncio.create_task(send_periodic_data())


    try:
        # 主循环：接收并处理客户端发来的输入消息
        while True:
            message = await websocket.receive_text()
            print(f"Received from {user}: {message}")
            process_input(user, message)
            # 可选：回复一条确认消息
            await websocket.send_text(f"Input processed: {message}")
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for user {user}")
    finally:
        # 取消后台定时任务，避免资源泄露
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass
