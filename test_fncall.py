import pytest
import requests
import subprocess
import time
import os
import signal
import json

# The URL where the server will be running
SERVER_URL = "http://127.0.0.1:8000"

@pytest.fixture(scope="session", autouse=True)
def start_server():
    os.environ["ALLOW_CODE_EXECUTION"] = "true"

    # Start the server using uvicorn in a subprocess
    process = subprocess.Popen(
        ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.abspath(os.path.dirname(__file__))
    )

    # Wait for the server to start
    for _ in range(30):
        try:
            response = requests.get(SERVER_URL)
            if response.status_code in [200, 404]: # fastfn might not have a root path
                break
        except requests.ConnectionError:
            pass
        time.sleep(0.5)
    else:
        # Get errors from stdout/stderr if possible
        stdout, stderr = process.communicate(timeout=1)
        print(f"Server start error: {stderr.decode()}")
        process.terminate()
        raise RuntimeError("Failed to start server for testing")

    yield

    # Teardown: Stop the server
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

def test_fncall_python():
    payload = {
        "fncall": {
            "name": "execute_python",
            "arguments": json.dumps({"code": "print('FN Python')"})
        }
    }
    response = requests.post(f"{SERVER_URL}/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "FN Python" in data["result"]
    assert "fncall:execute_python" in data["operation"]

def test_fncall_bash():
    payload = {
        "fncall": {
            "name": "execute_bash",
            "arguments": json.dumps({"code": "echo 'FN Bash'"})
        }
    }
    response = requests.post(f"{SERVER_URL}/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "FN Bash" in data["result"]
    assert "fncall:execute_bash" in data["operation"]

def test_fncall_external():
    # Make sure functions/test/echo.py exists
    # It was created by the previous shell command
    payload = {
        "fncall": {
            "name": "test.echo",
            "arguments": json.dumps({"hello": "world"})
        }
    }
    response = requests.post(f"{SERVER_URL}/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    # External function returns json-encoded result
    result = json.loads(data["result"])
    assert result["hello"] == "world"
    assert "fncall:test.echo" in data["operation"]

def test_fncall_invalid():
    payload = {
        "fncall": {
            "name": "non_existent",
            "arguments": "{}"
        }
    }
    response = requests.post(f"{SERVER_URL}/process", json=payload)
    assert response.status_code == 500
    assert "未知函数" in response.json()["detail"]
