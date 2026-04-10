# playwright/open_deepseek.py
r"""
连接到已运行的 Edge 浏览器并打开 chat.deepseek.com
请先启动调试模式的 Edge：
msedge --remote-debugging-port=9222 --user-data-dir="C:/temp/edge_debug_profile"
"""

import asyncio
from playwright.async_api import async_playwright

async def open_deepseek():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        print("已连接到 Edge 浏览器，当前标签页数量:", len(browser.contexts))
        
        # 获取默认上下文中的第一个页面
        if browser.contexts:
            context = browser.contexts[0]
        else:
            context = await browser.new_context()
        
        if context.pages:
            page = context.pages[0]
            print(f"当前页面标题: {await page.title()}")
        else:
            page = await context.new_page()
        
        print("正在打开 chat.deepseek.com ...")
        await page.goto("https://chat.deepseek.com")
        print(f"页面标题: {await page.title()}")
        print("已成功打开 DeepSeek 聊天页面。")
        
        # 可选：截图确认
        await page.screenshot(path="playwright/deepseek_loaded.png")
        print("截图已保存至 playwright/deepseek_loaded.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(open_deepseek())
