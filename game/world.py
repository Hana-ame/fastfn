# game/world.py
import random


def get_data(user: str, timestamp: float):
    """根据用户和时间戳生成要推送的数据"""
    return {
        "user": user,
        "timestamp": timestamp,
        "value": random.randint(1, 100),
        "message": f"Hello {user}, server time is {timestamp}",
    }


def process_input(user: str, message: str):
    print(user, message)
