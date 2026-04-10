# playwright/send_deepseek_question.py
r"""
在已打开的 DeepSeek 聊天页面中发送预设问题。
请先启动调试模式的 Edge 并确保已登录 DeepSeek。
"""

import asyncio
from playwright.async_api import async_playwright

PRESET_QUESTION = "请用中文简要介绍 Playwright 的核心功能。"

async def send_question():
    async with async_playwright() as p:
        # 连接到已运行的 Edge
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        print("已连接到 Edge 浏览器")
        
        # 获取第一个上下文和页面（通常就是当前可见的标签页）
        if not browser.contexts:
            raise RuntimeError("没有找到浏览器上下文，请确保 Edge 已打开页面")
        context = browser.contexts[0]
        
        if not context.pages:
            page = await context.new_page()
            await page.goto("https://chat.deepseek.com")
        else:
            page = context.pages[0]
            # 如果当前页面不是 DeepSeek，则导航过去
            if "chat.deepseek.com" not in page.url:
                await page.goto("https://chat.deepseek.com")
        
        print(f"当前页面: {page.url}")
        
        # 等待页面关键元素加载（输入框存在）
        # DeepSeek 输入框通常是一个 contenteditable 的 div 或 textarea
        # 我们尝试几种常见的选择器
        selectors = [
            "textarea[placeholder*='发送消息']",
            "textarea[placeholder*='Message']",
            "div[contenteditable='true']",
            "#chat-input",
            ".input-box textarea"
        ]
        
        input_element = None
        for selector in selectors:
            try:
                input_element = await page.wait_for_selector(selector, timeout=3000)
                if input_element:
                    print(f"找到输入框，选择器: {selector}")
                    break
            except:
                continue
        
        if not input_element:
            # 如果都找不到，打印页面 HTML 片段用于调试
            print("未找到输入框，输出页面部分内容以供分析：")
            content = await page.content()
            print(content[:2000])
            await page.screenshot(path="playwright/debug_no_input.png")
            raise Exception("无法定位输入框，请检查页面结构或登录状态。")
        
        # 输入预设问题
        await input_element.fill(PRESET_QUESTION)
        print(f"已填入问题: {PRESET_QUESTION}")
        
        # 点击发送按钮（通常是纸飞机图标或“发送”文字）
        send_selectors = [
            "button[type='submit']",
            "button:has(svg)",  # 可能包含图标
            "button:has-text('发送')",
            "button:has-text('Send')",
            ".send-btn",
            "button[aria-label='发送']"
        ]
        
        send_button = None
        for selector in send_selectors:
            try:
                send_button = await page.wait_for_selector(selector, timeout=2000)
                if send_button:
                    print(f"找到发送按钮，选择器: {selector}")
                    break
            except:
                continue
        
        if send_button:
            await send_button.click()
        else:
            # 如果找不到发送按钮，尝试按回车键
            print("未找到发送按钮，尝试按 Enter 键发送")
            await input_element.press("Enter")
        
        print("消息已发送，等待响应...")
        
        # 等待响应出现（可以等待一个表示回复正在生成或已完成的标志）
        # 这里简单等待几秒，然后检查是否有新的消息容器出现
        await page.wait_for_timeout(5000)  # 等待 5 秒让回复开始生成
        
        # 等待回复区域稳定（例如最后一个消息气泡出现）
        # 或者等待“停止生成”按钮消失（如果有）
        try:
            await page.wait_for_selector(".message:last-child", timeout=10000)
        except:
            pass
        
        # 截图保存结果
        await page.screenshot(path="playwright/deepseek_response.png", full_page=True)
        print("截图已保存至 playwright/deepseek_response.png")
        
        # 可选：提取最新的回复文本
        # 这里根据实际 DOM 结构调整选择器
        reply_selectors = [
            ".message:last-child .text-content",
            ".chat-message:last-child p",
            "[class*='assistant']:last-child"
        ]
        for sel in reply_selectors:
            try:
                reply_element = await page.wait_for_selector(sel, timeout=2000)
                if reply_element:
                    reply_text = await reply_element.text_content()
                    print(f"回复内容预览: {reply_text[:200]}...")
                    break
            except:
                continue
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(send_question())
