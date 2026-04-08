# main.py
from fastapi import FastAPI, Request
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import JSONResponse
from process_manager import shutdown_all_processes  # 引入关闭方法

from routers import upload, call
from game import ws  # 导入刚才写的模块

# 优雅的生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # 服务运行中
    # 停止 FastAPI 服务时，清理所有常驻的 runner.py 子进程
    await shutdown_all_processes()

app = FastAPI(lifespan=lifespan)  # 注入生命周期

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,   # 开发时依然保留热重载框架文件
        reload_excludes=["functions", "functions/*", "functions/**/*"],  # 👑 屏蔽函数目录，解决所有烦恼！
        log_level="info"
    )
# 直接运行此文件：uvicorn main:app --reload