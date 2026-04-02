# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from pathlib import Path

BASE_DIR = Path("functions")
BASE_DIR.mkdir(exist_ok=True)


app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from FastAPI"}

@app.put("/{folder}/{filename}")
async def upload(folder: str, filename: str, file: UploadFile = File(...)):
    # 1. 安全检查：禁止路径遍历
    if ".." in folder or ".." in filename or "/" in folder:
        raise HTTPException(400, "Invalid folder or filename")
    if not filename.endswith(".py"):
        raise HTTPException(400, "Only .py files")

    # 2. 构建保存路径
    file_path = BASE_DIR / folder / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 3. 保存文件
    content = await file.read()
    file_path.write_bytes(content)

    return {"message": "saved", "path": str(file_path)}


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