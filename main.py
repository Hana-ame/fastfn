# main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from process_manager import shutdown_all_processes

from middleware import UploadBlockMiddleware  # ← 导入中间件

from routers import upload, call
from game import chess
from repo import main as repo

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup on shutdown/reload
    await shutdown_all_processes()

app = FastAPI(title="fastfn", lifespan=lifespan)

# 📌 注册中间件（顺序很重要，建议放在最前面）
app.add_middleware(UploadBlockMiddleware)

# ==================== CORS 配置 ====================

# 1. 允许所有来源的简单请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有域名
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# 2. (可选) 如果你需要更严格的“仅针对 POST 动态返回 Origin”的逻辑，
# 上面的中间件其实已经足够覆盖了。
# FastAPI 的 CORSMiddleware 在 allow_origins=["*"] 时，
# 会自动处理 Access-Control-Allow-Origin。

# 但如果你的需求是“非 POST 不允许跨域”，那需要自定义中间件。
# 下面提供一个【自定义中间件】方案，完全符合你的描述：
# "当遇到 POST 时，allow origin 动态设置为来路 origin"

@app.middleware("http")
async def dynamic_cors_for_post(request: Request, call_next):
    # 获取请求来源
    origin = request.headers.get("origin")
    
    # 先执行路由处理
    response = await call_next(request)
    
    # 如果是 POST 请求且存在 Origin 头，动态添加 CORS 头
    # 注意：OPTIONS 预检请求由上面的 CORSMiddleware 处理，这里只需处理实际请求
    if request.method == "POST" and origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        
    return response

# ==================== 路由挂载 ====================

# 1. 挂载 chess 路由 (不再挂载静态文件)
app.include_router(chess.router, prefix="/chess")
app.include_router(repo.router, prefix="/repo")

app.include_router(upload.router, prefix="/fastfn")
app.include_router(call.router, prefix="/fastfn")

# ==================== 异常处理 ====================

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    # 由于分离了前端，这里的 404 是纯 API 404
    return JSONResponse(
        status_code=404,
        content={"detail": exc.detail, "path": request.url.path}
    )

# ==================== 启动配置 ====================

# main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["functions/*", "*/functions/*"],  # ← Add this
        log_level="info"
    )