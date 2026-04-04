# game/chess.py

import asyncio
import json
import uvicorn
from fastapi import APIRouter, WebSocket
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid

router = APIRouter()

# ==================== 数据模型 ====================

class RenderCommand(BaseModel):
    """渲染指令基类"""
    cmd: str  # draw_rect, draw_circle, draw_text, draw_sprite, clear, set_bg
    id: Optional[str] = None  # 对象唯一ID，用于增量更新
    layer: int = 0  # 图层顺序
    params: Dict[str, Any] = {}

class InputEvent(BaseModel):
    """输入事件"""
    type: str  # mouse_down, mouse_up, mouse_move, key_down
    x: float = 0
    y: float = 0
    button: int = 0
    key: str = ""
    timestamp: float

class GameState:
    """游戏状态管理"""
    def __init__(self):
        self.objects: Dict[str, Dict] = {}  # 场景对象
        self.ui_elements: Dict[str, Dict] = {}  # UI元素
        self.mode = "legal"  # legal, free, edit
        self.selected_piece = None
        self.current_player = "white"
        self.hovered_ui = None
        
    def create_board(self):
        """创建棋盘"""
        # 棋盘背景
        for y in range(8):
            for x in range(8):
                is_light = (x + y) % 2 == 0
                obj_id = f"cell_{x}_{y}"
                self.objects[obj_id] = {
                    "cmd": "draw_rect",
                    "id": obj_id,
                    "layer": 0,
                    "params": {
                        "x": x * 60 + 20,
                        "y": y * 60 + 20,
                        "w": 60, "h": 60,
                        "color": "#f0d9b5" if is_light else "#b58863",
                        "interactive": True,
                        "data": {"type": "cell", "x": x, "y": y}
                    }
                }
                
                # 坐标标签
                if x == 0:
                    self.objects[f"label_y_{y}"] = {
                        "cmd": "draw_text",
                        "id": f"label_y_{y}",
                        "layer": 1,
                        "params": {
                            "x": 5, "y": y * 60 + 50,
                            "text": str(8-y),
                            "style": {"fontSize": 12, "fill": "#666"}
                        }
                    }
                if y == 7:
                    self.objects[f"label_x_{x}"] = {
                        "cmd": "draw_text",
                        "id": f"label_x_{x}",
                        "layer": 1,
                        "params": {
                            "x": x * 60 + 50, "y": 500,
                            "text": chr(97 + x),
                            "style": {"fontSize": 12, "fill": "#666"}
                        }
                    }

    def create_ui(self):
        """创建UI菜单（完全由Python定义）"""
        # 顶部工具栏背景
        self.ui_elements["toolbar_bg"] = {
            "cmd": "draw_rect",
            "id": "toolbar_bg",
            "layer": 10,
            "params": {
                "x": 0, "y": 0, "w": 800, "h": 50,
                "color": "#16213e",
                "alpha": 0.9
            }
        }
        
        # 模式切换按钮
        buttons = [
            {"id": "btn_legal", "x": 20, "y": 10, "w": 80, "h": 30, 
             "text": "合法模式", "color": "#4fbdba", "action": "set_mode_legal"},
            {"id": "btn_free", "x": 110, "y": 10, "w": 80, "h": 30, 
             "text": "自由模式", "color": "#e94560", "action": "set_mode_free"},
            {"id": "btn_edit", "x": 200, "y": 10, "w": 80, "h": 30, 
             "text": "编辑模式", "color": "#ffc107", "action": "toggle_edit"},
            {"id": "btn_reset", "x": 600, "y": 10, "w": 60, "h": 30, 
             "text": "重置", "color": "#ff6b6b", "action": "reset"},
        ]
        
        for btn in buttons:
            # 按钮背景
            self.ui_elements[f"{btn['id']}_bg"] = {
                "cmd": "draw_round_rect",
                "id": f"{btn['id']}_bg",
                "layer": 11,
                "params": {
                    "x": btn["x"], "y": btn["y"], 
                    "w": btn["w"], "h": btn["h"], "radius": 5,
                    "color": btn["color"],
                    "interactive": True,
                    "hover_color": "#ffffff",
                    "data": {"type": "button", "action": btn["action"]}
                }
            }
            # 按钮文字
            self.ui_elements[f"{btn['id']}_text"] = {
                "cmd": "draw_text",
                "id": f"{btn['id']}_text",
                "layer": 12,
                "params": {
                    "x": btn["x"] + btn["w"]/2,
                    "y": btn["y"] + btn["h"]/2 + 5,
                    "text": btn["text"],
                    "style": {"fontSize": 14, "fill": "#ffffff", "align": "center"}
                }
            }
        
        # 状态显示
        self.ui_elements["status_text"] = {
            "cmd": "draw_text",
            "id": "status_text",
            "layer": 12,
            "params": {
                "x": 400, "y": 30,
                "text": f"回合: {self.current_player} | 模式: {self.mode}",
                "style": {"fontSize": 16, "fill": "#7ec8e3"}
            }
        }

    def add_piece(self, piece_type: str, color: str, x: int, y: int):
        """添加棋子"""
        piece_id = f"piece_{uuid.uuid4().hex[:8]}"
        symbols = {
            "white": {"king": "♔", "queen": "♕", "rook": "♖", 
                     "bishop": "♗", "knight": "♘", "pawn": "♙"},
            "black": {"king": "♚", "queen": "♛", "rook": "♜", 
                     "bishop": "♝", "knight": "♞", "pawn": "♟"}
        }
        
        self.objects[piece_id] = {
            "cmd": "draw_text",
            "id": piece_id,
            "layer": 5,
            "params": {
                "x": x * 60 + 50,
                "y": y * 60 + 50,
                "text": symbols[color][piece_type],
                "style": {
                    "fontSize": 48,
                    "fill": "#ffffff" if color == "white" else "#333333",
                    "stroke": "#000000",
                    "strokeThickness": 2
                },
                "interactive": True,
                "data": {
                    "type": "piece",
                    "piece_type": piece_type,
                    "color": color,
                    "grid_x": x,
                    "grid_y": y
                }
            }
        }
        return piece_id

    def handle_input(self, event: InputEvent) -> List[RenderCommand]:
        """处理输入事件，返回需要更新的渲染指令"""
        updates = []
        
        if event.type == "mouse_down":
            # 检测点击了哪个UI或棋子
            clicked = self.hit_test(event.x, event.y)
            
            if clicked:
                if clicked.get("type") == "button":
                    action = clicked.get("action")
                    if action == "set_mode_legal":
                        self.mode = "legal"
                    elif action == "set_mode_free":
                        self.mode = "free"
                    elif action == "toggle_edit":
                        self.mode = "edit" if self.mode != "edit" else "legal"
                    
                    # 更新UI显示
                    self.ui_elements["status_text"]["params"]["text"] = \
                        f"回合: {self.current_player} | 模式: {self.mode}"
                    updates.append(self.ui_elements["status_text"])
                    
                    # 按钮反馈动画
                    btn_id = [k for k, v in self.ui_elements.items() 
                             if v.get("params", {}).get("data", {}).get("action") == action][0]
                    updates.append({
                        "cmd": "animate",
                        "id": btn_id,
                        "params": {"scale": 0.9, "duration": 100}
                    })
                    
                elif clicked.get("type") == "piece":
                    self.selected_piece = clicked
                    # 添加选中高亮
                    highlight_id = "selection_highlight"
                    self.objects[highlight_id] = {
                        "cmd": "draw_circle",
                        "id": highlight_id,
                        "layer": 4,
                        "params": {
                            "x": clicked["grid_x"] * 60 + 50,
                            "y": clicked["grid_y"] * 60 + 50,
                            "radius": 25,
                            "color": "#e94560",
                            "alpha": 0.3
                        }
                    }
                    updates.append(self.objects[highlight_id])
                    
                elif clicked.get("type") == "cell" and self.selected_piece:
                    # 移动棋子
                    if self.mode == "free" or self.is_valid_move(
                        self.selected_piece, clicked["x"], clicked["y"]
                    ):
                        self.move_piece(self.selected_piece, clicked["x"], clicked["y"])
                        # 重新生成所有对象指令
                        return self.get_full_render_list()
        
        elif event.type == "mouse_move":
            # 悬停效果检测
            hovered = self.hit_test(event.x, event.y)
            if hovered and hovered.get("type") == "button":
                if self.hovered_ui != hovered:
                    self.hovered_ui = hovered
                    # 发送悬停高亮指令
                    # 实际应用中应该只发送变化的部分
        
        return updates

    def hit_test(self, x: float, y: float) -> Optional[Dict]:
        """碰撞检测（从后往前检测）"""
        # 检测UI（层级高优先）
        for id, obj in sorted(self.ui_elements.items(), key=lambda x: -x[1]["layer"]):
            params = obj["params"]
            if params.get("interactive"):
                if self.point_in_rect(x, y, params):
                    return params.get("data", {})
        
        # 检测游戏对象
        for id, obj in sorted(self.objects.items(), key=lambda x: -x[1]["layer"]):
            params = obj["params"]
            if params.get("interactive"):
                if obj["cmd"] == "draw_text":  # 棋子
                    # 简化的圆形碰撞
                    dx = x - params["x"]
                    dy = y - params["y"]
                    if (dx*dx + dy*dy) < 900:  # 30px半径
                        return params.get("data", {})
                elif self.point_in_rect(x, y, params):
                    return params.get("data", {})
        return None

    def point_in_rect(self, x, y, params):
        """点是否在矩形内"""
        return (params["x"] <= x <= params["x"] + params.get("w", 0) and
                params["y"] <= y <= params["y"] + params.get("h", 0))

    def is_valid_move(self, piece, to_x, to_y) -> bool:
        """简化的移动合法性检查"""
        # 这里可以实现完整的国际象棋规则
        return True  # 简化处理

    def move_piece(self, piece_data, to_x, to_y):
        """移动棋子"""
        piece_id = None
        for pid, obj in self.objects.items():
            if obj["params"].get("data") == piece_data:
                piece_id = pid
                break
        
        if piece_id:
            # 更新位置
            self.objects[piece_id]["params"]["x"] = to_x * 60 + 50
            self.objects[piece_id]["params"]["y"] = to_y * 60 + 50
            self.objects[piece_id]["params"]["data"]["grid_x"] = to_x
            self.objects[piece_id]["params"]["data"]["grid_y"] = to_y
            
            # 移除高亮
            if "selection_highlight" in self.objects:
                del self.objects["selection_highlight"]
            
            self.selected_piece = None
            self.current_player = "black" if self.current_player == "white" else "white"

    def get_full_render_list(self) -> List[Dict]:
        """获取完整渲染列表"""
        all_objects = []
        all_objects.extend(self.objects.values())
        all_objects.extend(self.ui_elements.values())
        # 按层级排序
        all_objects.sort(key=lambda x: x["layer"])
        return all_objects

    def get_initial_frame(self) -> List[Dict]:
        """获取初始帧"""
        self.create_board()
        self.create_ui()
        # 添加初始棋子
        setup = [
            ("rook", "black", 0, 0), ("knight", "black", 1, 0), 
            ("bishop", "black", 2, 0), ("queen", "black", 3, 0),
            ("king", "black", 4, 0), ("bishop", "black", 5, 0),
            ("knight", "black", 6, 0), ("rook", "black", 7, 0),
        ] + [("pawn", "black", i, 1) for i in range(8)] + \
          [("pawn", "white", i, 6) for i in range(8)] + [
            ("rook", "white", 0, 7), ("knight", "white", 1, 7),
            ("bishop", "white", 2, 7), ("queen", "white", 3, 7),
            ("king", "white", 4, 7), ("bishop", "white", 5, 7),
            ("knight", "white", 6, 7), ("rook", "white", 7, 7),
        ]
        
        for ptype, color, x, y in setup:
            self.add_piece(ptype, color, x, y)
            
        return self.get_full_render_list()

# ==================== WebSocket 服务 ====================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.game_states: Dict[str, GameState] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # 为每个连接创建独立的游戏状态
        game_state = GameState()
        self.game_states[str(websocket)] = game_state
        
        # 发送初始帧
        initial_frame = game_state.get_initial_frame()
        await websocket.send_json({
            "type": "full_frame",
            "objects": initial_frame
        })

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        if str(websocket) in self.game_states:
            del self.game_states[str(websocket)]

    async def send_updates(self, websocket: WebSocket, updates: List[Dict]):
        if updates:
            await websocket.send_json({
                "type": "delta",
                "objects": updates
            })

manager = ConnectionManager()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    game_state = manager.game_states[str(websocket)]
    
    try:
        while True:
            # 接收前端输入
            data = await websocket.receive_json()
            event = InputEvent(**data)
            
            # Python处理输入，生成渲染更新
            updates = game_state.handle_input(event)
            
            # 发送增量更新
            await manager.send_updates(websocket, updates)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        manager.disconnect(websocket)

# 挂载静态文件（前端）
# router.mount("/", StaticFiles(directory="static", html=True), name="static")
