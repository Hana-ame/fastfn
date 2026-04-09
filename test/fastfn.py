"""
测试脚本 for fastfn 服务
要求：服务运行在 http://localhost:8000
安装依赖：pytest, requests
运行：pytest test_fastfn.py -v
"""

import os
import pytest
import requests

BASE_URL = "http://localhost:8000"
UPLOAD_URL = f"{BASE_URL}/fastfn"
CALL_URL = f"{BASE_URL}/fastfn"

# ------------------------------------------------------------------
# 辅助函数：生成临时 Python 文件内容
# ------------------------------------------------------------------
def make_valid_module(test_success=True):
    """
    生成一个有效的可上传模块内容
    符合新的规范: main(data) 函数 + testCases 列表
    """
    main_code = """
def main(data=None):
    if isinstance(data, dict) and data.get("action") == "echo":
        return {"echo": "ok"}
    return {"status": "success", "received": data}
"""
    if test_success:
        test_code = """
testCases = [
    {
        "input": None, 
        "expected": {"status": "success", "received": None}
    },
    {
        "input": {"name": "Hana"}, 
        "expected": {"status": "success", "received": {"name": "Hana"}}
    },
    {
        "input": {"action": "echo"},
        "expected": {"echo": "ok"}
    }
]
"""
    else:
        # 故意制造一个不匹配的预期结果，使得测试用例失败
        test_code = """
testCases = [
    {
        "input": {"name": "Hana"}, 
        "expected": {"status": "error", "message": "This is intentionally wrong"}
    }
]
"""
    return main_code + test_code

def make_syntax_error_module():
    return "def main(data=None):\n    return data  # missing colon on next line?\n    x = "

# ------------------------------------------------------------------
# 测试夹具：清理可能残留的测试文件
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
    """测试正常上传有效文件，并调用 main 函数"""
    filename = "echo.py"
    module_content = make_valid_module(test_success=True)
    
    # 1. 上传
    put_resp = requests.put(
        f"{UPLOAD_URL}/{unique_folder}/{filename}",
        files={"file": (filename, module_content, "text/x-python")}
    )
    assert put_resp.status_code == 200
    data = put_resp.json()
    assert data["message"] == "saved and pre-warmed"
    assert "path" in data

    # 2. 调用 (测试基础逻辑)
    post_resp = requests.post(
        f"{CALL_URL}/{unique_folder}/{filename}",
        json={"data": {"name": "TestUser"}}
    )
    assert post_resp.status_code == 200
    result = post_resp.json()
    assert result["success"] is True
    # 断言结果应与 main 函数的返回逻辑一致
    assert result["result"] == {"status": "success", "received": {"name": "TestUser"}}

    # 3. 调用 (测试特定的分支逻辑)
    post_resp_2 = requests.post(
        f"{CALL_URL}/{unique_folder}/{filename}",
        json={"data": {"action": "echo"}}
    )
    assert post_resp_2.status_code == 200
    assert post_resp_2.json()["result"] == {"echo": "ok"}


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
    """上传语法错误的文件应失败，且文件不应被保留"""
    filename = "syntax_error.py"
    content = make_syntax_error_module()
    
    put_resp = requests.put(
        f"{UPLOAD_URL}/{unique_folder}/{filename}",
        files={"file": (filename, content, "text/x-python")}
    )
    assert put_resp.status_code == 400
    # 响应应包含错误细节（语法错误）
    assert "error" in str(put_resp.json().get("detail", "")).lower()

    # 验证文件确实未保存：调用应 404
    call_resp = requests.post(
        f"{CALL_URL}/{unique_folder}/{filename}",
        json={"data": {}}
    )
    assert call_resp.status_code == 404

def test_upload_testcases_failure(unique_folder):
    """上传的文件 testCases 执行失败（实际输出与expected不符），上传应被拒绝并回滚"""
    filename = "bad_test.py"
    content = make_valid_module(test_success=False)
    
    put_resp = requests.put(
        f"{UPLOAD_URL}/{unique_folder}/{filename}",
        files={"file": (filename, content, "text/x-python")}
    )
    assert put_resp.status_code == 400
    detail = put_resp.json().get("detail", "")
    
    # 根据服务端的具体报错信息，这里可能需要调整断言关键字
    # 假设服务端报错中会包含 "test" 或 "fail" 等字眼
    assert "test" in str(detail).lower() or "fail" in str(detail).lower()

    # 调用应 404（文件未保存）
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
    assert resp.status_code == 404
    assert "Not Found" in resp.text

def test_call_with_complex_data(unique_folder):
    """调用时传递复杂 JSON 数据，应原样传递到 main 函数并返回"""
    filename = "complex.py"
    content = """
def main(data=None):
    return {"received": data, "type": str(type(data))}

testCases = [
    {
        "input": {"a": [1, 2, 3], "b": {"x": "y"}},
        "expected": {"received": {"a": [1, 2, 3], "b": {"x": "y"}}, "type": "<class 'dict'>"}
    }
]
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