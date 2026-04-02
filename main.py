# main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from routers import upload, call
from game import ws  # 导入刚才写的模块

app = FastAPI()

app.include_router(upload.router)
app.include_router(call.router)

# ws
app.include_router(ws.router)

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    # 根据异常内容动态返回响应
    return JSONResponse(
        status_code=200,
        content={"detail": exc.detail, "path": request.url.path}
    )

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