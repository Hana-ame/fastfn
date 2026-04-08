"""
测试脚本 for fastfn 服务
要求：服务运行在 http://localhost:8000
安装依赖：pytest, requests
运行：pytest test_fastfn.py -v
"""

import os
import tempfile
import pytest
import requests

BASE_URL = "http://localhost:8000"
UPLOAD_URL = f"{BASE_URL}/fastfn"
CALL_URL = f"{BASE_URL}/fastfn"

# ------------------------------------------------------------------
# 辅助函数：生成临时 Python 文件内容
# ------------------------------------------------------------------
def make_valid_module(call_return_value=None, test_success=True):
    """生成一个有效的可上传模块内容"""
    call_code = f"""
def call(data):
    return {repr(call_return_value) if call_return_value else 'data'}
"""
    test_code = """
def testCases():
    return {"success": True}
""" if test_success else """
def testCases():
    return {"error": "Test failed intentionally"}
"""
    return call_code + test_code

def make_syntax_error_module():
    return "def call(data):\n    return data  # missing colon on next line?\n    x = "

# ------------------------------------------------------------------
# 测试夹具：清理可能残留的测试文件（通过调用删除端点？但服务无删除，故只确保测试不互相影响）
# ------------------------------------------------------------------
@pytest.fixture
def unique_folder():
    """生成唯一文件夹名，避免冲突"""
    import time
    return f"test_{int(time.time()*1000)}"

# ------------------------------------------------------------------
# 测试用例
# ------------------------------------------------------------------
def test_upload_and_call_valid(unique_folder):
    """测试正常上传有效文件，并调用函数"""
    filename = "echo.py"
    module_content = make_valid_module(call_return_value={"echo": "ok"})
    
    # 1. 上传
    put_resp = requests.put(
        f"{UPLOAD_URL}/{unique_folder}/{filename}",
        files={"file": (filename, module_content, "text/x-python")}
    )
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["message"] == "saved and pre-warmed"
    assert "path" in data

    # 2. 调用
    post_resp = requests.post(
        f"{CALL_URL}/{unique_folder}/{filename}",
        json={"data": "hello"}
    )
    assert post_resp.status_code == 200
    result = post_resp.json()
    assert result["success"] is True
    assert result["result"] == {"echo": "ok"}  # 应返回模块中 call 函数定义的值

def test_upload_non_py_file(unique_folder):
    """上传非 .py 文件应失败"""
    resp = requests.put(
        f"{UPLOAD_URL}/{unique_folder}/test.txt",
        files={"file": ("test.txt", b"content", "text/plain")}
    )
    assert resp.status_code == 400
    assert "Only .py files" in resp.text

def test_call_nonexistent_file(unique_folder):
    """调用不存在的函数文件应返回 404"""
    resp = requests.post(
        f"{CALL_URL}/{unique_folder}/nonexist.py",
        json={"data": {}}
    )
    assert resp.status_code == 404
    assert "Function not found" in resp.text

def test_upload_syntax_error_file(unique_folder):
    """上传语法错误的文件应失败，且文件被删除（无法再调用）"""
    filename = "syntax_error.py"
    content = make_syntax_error_module()
    
    put_resp = requests.put(
        f"{UPLOAD_URL}/{unique_folder}/{filename}",
        files={"file": (filename, content, "text/x-python")}
    )
    assert put_resp.status_code == 400
    # 响应应包含错误细节（语法错误）
    assert "error" in put_resp.json()["detail"]

    # 验证文件确实未保存：调用应 404
    call_resp = requests.post(
        f"{CALL_URL}/{unique_folder}/{filename}",
        json={"data": {}}
    )
    assert call_resp.status_code == 404

def test_upload_testcases_failure(unique_folder):
    """上传的文件 testCases 返回 error，上传应失败并回滚"""
    filename = "bad_test.py"
    content = make_valid_module(test_success=False)
    
    put_resp = requests.put(
        f"{UPLOAD_URL}/{unique_folder}/{filename}",
        files={"file": (filename, content, "text/x-python")}
    )
    assert put_resp.status_code == 400
    detail = put_resp.json()["detail"]
    assert "Test failed intentionally" in str(detail)

    # 调用应 404（文件已被删除）
    call_resp = requests.post(
        f"{CALL_URL}/{unique_folder}/{filename}",
        json={"data": {}}
    )
    assert call_resp.status_code == 404

def test_upload_path_traversal_prevention():
    """尝试路径遍历应被阻止"""
    resp = requests.put(
        f"{UPLOAD_URL}/../etc/test.py",
        files={"file": ("test.py", b"print(1)", "text/x-python")}
    )
    assert resp.status_code == 400
    assert "Invalid folder or filename" in resp.text

def test_call_with_complex_data(unique_folder):
    """调用时传递复杂 JSON 数据，应原样传递到 call 函数并返回"""
    filename = "complex.py"
    content = """
def call(data):
    return {"received": data, "type": str(type(data))}
def testCases():
    return {"success": True}
"""
    # 上传
    put_resp = requests.put(
        f"{UPLOAD_URL}/{unique_folder}/{filename}",
        files={"file": (filename, content, "text/x-python")}
    )
    assert put_resp.status_code == 200

    # 调用：传递嵌套结构
    test_data = {"a": [1, 2, 3], "b": {"x": "y"}}
    post_resp = requests.post(
        f"{CALL_URL}/{unique_folder}/{filename}",
        json={"data": test_data}
    )
    assert post_resp.status_code == 200
    result = post_resp.json()
    assert result["success"] is True
    assert result["result"]["received"] == test_data
    assert "dict" in result["result"]["type"]