# routers/upload.py

from fastapi import APIRouter, UploadFile, File, HTTPException
import importlib.util
import tempfile
import os

from .consts import BASE_DIR, deep_equal

router = APIRouter()

@router.put("/{folder}/{filename}")
async def upload(folder: str, filename: str, file: UploadFile = File(...)):
    # 1. 安全检查：禁止路径遍历
    if ".." in folder or ".." in filename or "/" in folder:
        raise HTTPException(400, "Invalid folder or filename")
    if not filename.endswith(".py"):
        raise HTTPException(400, "Only .py files")

    # 读取内容  
    content = await file.read()
    code = content.decode("utf-8")

    
    # 将代码写入临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        # 动态加载临时模块
        spec = importlib.util.spec_from_file_location("test_module", tmp_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # 获取 testCases
        test_cases = getattr(module, "testCases", None)
        if not isinstance(test_cases, list):
            raise HTTPException(400, "No valid testCases array")

        # 运行测试
        errors = []
        for idx, tc in enumerate(test_cases):
            if "input" not in tc or "expected" not in tc:
                errors.append({"testCaseIndex": idx, "error": "Missing input/expected"})
                continue
            try:
                actual = module.main(tc["input"])
                if not deep_equal(actual, tc["expected"]):
                    errors.append({
                        "testCaseIndex": idx,
                        "input": tc["input"],
                        "expected": tc["expected"],
                        "actual": actual
                    })
            except Exception as e:
                errors.append({"testCaseIndex": idx, "error": str(e)})

        if errors:
            raise HTTPException(400, detail={"error": "Test cases failed", "details": errors})
    finally:
        os.unlink(tmp_path)   # 删除临时文件

    # 2. 构建保存路径
    file_path = BASE_DIR / folder / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 3. 保存文件
    file_path.write_bytes(content)

    return {"message": "saved", "path": str(file_path)}

