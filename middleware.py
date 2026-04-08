# middleware.py
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 🎚️ 全局开关：改这里即可控制上传功能
ENABLE_CODE_UPLOAD = False 
ENABLE_CODE_UPLOAD = True 

class UploadBlockMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 🚫 如果上传功能关闭，且请求路径包含 /upload
        if not ENABLE_CODE_UPLOAD and "/upload" in request.url.path:
            return JSONResponse(
                status_code=403,
                content={
                    "code": 403,
                    "detail": "代码上传功能已暂停维护",
                    "enabled": ENABLE_CODE_UPLOAD
                }
            )
        
        # ✅ 其他请求正常放行
        response = await call_next(request)
        return response