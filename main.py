# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from pathlib import Path
from typing import Any

# from routers import upload, call, delete, download
from routers import upload, call
from game import ws  # 导入刚才写的模块

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from FastAPI"}

app.include_router(upload.router)
app.include_router(call.router)

# ws
app.include_router(ws.router)

# 在文件末尾
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,   # 开发时启用热重载
        log_level="info"
    )

# 直接运行此文件：uvicorn main:app --reload