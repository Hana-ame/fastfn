# routers/call.py

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Any
import importlib.util

from .consts import BASE_DIR

class CallRequest(BaseModel):
    data: Any

router = APIRouter()

@router.post("/{folder}/{filename}")
async def call(folder: str, filename: str, req: CallRequest):
    # 1. 定位文件
    if not filename.endswith(".py"):
        raise HTTPException(400, "Only .py files")
    file_path = BASE_DIR / folder / filename
    if not file_path.exists():
        raise HTTPException(404, "Function not found")

    # 2. 动态加载模块
    spec = importlib.util.spec_from_file_location("user_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)   # 执行用户代码

    # 3. 检查 main 函数
    if not hasattr(module, "main"):
        raise HTTPException(500, "No 'main' function")

    # 4. 调用并返回
    try:
        result = module.main(req.data)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}