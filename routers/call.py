# routers/call.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
from pathlib import Path

from consts import BASE_DIR
from process_manager import get_or_create_process, call_runner

router = APIRouter()

class CallRequest(BaseModel):
    data: Any

@router.post("/{folder}/{filename}")
async def call_function(folder: str, filename: str, req: CallRequest):
    # 1. 只允许 .py 文件被调用
    if not filename.endswith(".py"):
        raise HTTPException(400, "Only .py files")

    # 2. 构建文件在磁盘上的实际路径（用于检查文件是否存在）
    file_path = BASE_DIR / folder / filename
    if not file_path.exists():
        raise HTTPException(404, "Function not found")

    # 3. 生成一个唯一标识符，用于在 process_manager 中管理子进程
    #    这里去掉了 .py 后缀，例如 "math/add.py" 变成 "math/add"
    # key = f"{folder}/{filename[:-3]}"  # 去掉最后3个字符 ".py"
    key = f"{folder}/{filename}"   # 不再去掉 .py
    
    # 4. 获取或启动该函数对应的常驻子进程
    proc = await get_or_create_process(key, file_path)
    
    # 5. 通过子进程的 stdin/stdout 发送请求数据，并等待响应
    response = await call_runner(proc, req.data)

    # 6. 根据响应内容返回结果
    if response.get("error"):
        return {"success": False, "error": response["error"]}
    return {"success": True, "result": response.get("result")}