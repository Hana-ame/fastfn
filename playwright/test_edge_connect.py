# playwright/test_edge_connect.py
r"""
测试连接到已运行的 Edge 浏览器（通过 CDP 协议）
请先启动调试模式的 Edge：
msedge --remote-debugging-port=9222 --user-data-dir="C:/temp/edge_debug_profile"
"""

import asyncio
from playwright.async_api import async_playwright

async def connect_to_existing_edge():
    async with async_playwright() as p:
        # 连接到本地 Edge 调试端口
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        print("已连接到 Edge 浏览器，当前标签页数量:", len(browser.contexts))
        
        # 获取默认上下文中的第一个页面（或创建新页面）
        if browser.contexts:
            context = browser.contexts[0]
        else:
            context = await browser.new_context()
        
        if context.pages:
            page = context.pages[0]
            print(f"当前页面标题: {await page.title()}")
        else:
            page = await context.new_page()
        
        # 示例操作：打开一个网页并截图
        await page.goto("https://example.com")
        await page.screenshot(path="playwright/example_screenshot.png")
        print("截图已保存至 playwright/example_screenshot.png")
        
        # 注意：不要关闭浏览器，因为连接的是用户手动打开的实例
        # 仅断开连接
        await browser.close()

if __name__ == "__main__":
    asyncio.run(connect_to_existing_edge())
