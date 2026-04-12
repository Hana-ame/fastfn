import pytest
import requests
import subprocess
import time
import os
import signal

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
        process.terminate()
        raise RuntimeError("Failed to start server for testing")

    yield

    # Teardown: Stop the server
    process.send_signal(signal.SIGINT)
    process.wait(timeout=5)
    if process.poll() is None:
        process.kill()

def test_execute_python():
    payload = {
        "text": "print('Hello from Python!')",
        "operation": "execute_python"
    }
    response = requests.post(f"{SERVER_URL}/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Hello from Python!" in data["result"]
    assert "```stdout" in data["result"]

def test_execute_bash():
    payload = {
        "text": "echo 'Hello from Bash!'",
        "operation": "execute_bash"
    }
    response = requests.post(f"{SERVER_URL}/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Hello from Bash!" in data["result"]
    assert "```stdout" in data["result"]

def test_execute_markdown():
    payload = {
        "text": "```python\nprint('MD Python')\n```",
        "operation": "execute_markdown"
    }
    response = requests.post(f"{SERVER_URL}/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "MD Python" in data["result"]
    assert "```stdout" in data["result"]

def test_invalid_operation():
    payload = {
        "text": "print('Hello')",
        "operation": "execute_ruby"
    }
    response = requests.post(f"{SERVER_URL}/process", json=payload)
    assert response.status_code == 422 # Pydantic validation error
