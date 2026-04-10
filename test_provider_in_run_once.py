#!/usr/bin/env python
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_DIR))

import asyncio
from dotenv import load_dotenv
load_dotenv(PROJECT_DIR / ".env")

from agent_framework.llm import PlaywrightDeepSeekLLM

async def main():
    if len(sys.argv) < 2:
        print("用法: python test_provider_in_run_once.py \"你的问题\"")
        sys.exit(1)
    question = sys.argv[1]
    llm = PlaywrightDeepSeekLLM(timeout=50)  # 设置更短的超时以适应限制
    messages = [{"role": "user", "content": question}]
    response = await llm.generate(messages)
    print(response["content"])

if __name__ == "__main__":
    asyncio.run(main())
