# Fastfn - Serverless Function Execution Platform

Fastfn is a lightweight FastAPI-based platform for executing code snippets (Bash, Python, Markdown) and managed "functions" (Python scripts in resident subprocesses).

## Core Features

- **Direct Execution**: Run Bash, Python, or Markdown directly via a unified `/process` endpoint.
- **Managed Functions**: Pre-load Python scripts from the `functions/` directory for high-performance execution.
- **Unified Function Call Controller**: Support for OpenAI-style tool calls that can trigger both built-in executors and managed functions.
- **Safe Execution**: Process-level isolation with timeouts and process tree cleanup.
- **Cross-Platform**: Optimized for both Linux and Windows (Git Bash support).

## API Endpoints

### 1. Unified Process Endpoint (`POST /process`)
Handles various execution modes based on the request body:

- **Bash**: `{"bash": "echo hello"}`
- **Python**: `{"python": "print('hello')"}`
- **Markdown**: `{"markdown": "```python\nprint('hello')\n```"}`
- **Function Call**: 
  ```json
  {
    "fncall": {
      "name": "execute_bash",
      "arguments": "{\"code\": \"ls\"}"
    }
  }
  ```
  *Note: External functions can be called using `folder.filename` as the name (e.g., `math.add`).*

### 2. Direct Function Call (`POST /fastfn/{folder}/{filename}`)
Calls a managed function directly.

## HTML Executors (Monaco Editor Integrated)

Access these tools for a friendly web interface:

- 🔗 **Python Executor**: [Link](https://upload.moonchan.xyz/api/01LLWEUUZB6DAZII34M5FJQJA435LFTI2G/python.html)
- 🔗 **Bash Executor**: [Link](https://upload.moonchan.xyz/api/01LLWEUUY4RB457LLY7JG2NRXM4RINDB7B/bash.html)
- 🔗 **Markdown Executor**: [Link](https://upload.moonchan.xyz/api/01LLWEUU6FLNKRZZHU2JGYJYTK7NT5K5HS/markdown.html)
- 🔗 **Function Call Executor**: [Link](https://upload.moonchan.xyz/api/01LLWEUU2HS6X6LBPSWVD3HM7ZQEFIFRMO/fncall.html)

## Development & Testing

Run tests with pytest:
```bash
pytest test_fncall.py
pytest test_live_server.py
```
