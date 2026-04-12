# -*- coding: utf-8 -*-

"""
交互式命令工具 - 支持 /select 带下拉菜单的交互选择
依赖：pip install prompt_toolkit
"""

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    from prompt_toolkit.completion import Completer, Completion
except ImportError:
    print("错误：需要安装 prompt_toolkit 库。")
    print("请执行：pip install prompt_toolkit")
    exit(1)

# ================== 配置 ==================
# 主命令列表
COMMANDS = [
    "/new", "/edit", "/delete", "/list",
    "/help", "/exit", "/save", "/load", "/select"
]

# /select 中的选项列表
SELECT_OPTIONS = [
    "苹果", "香蕉", "橙子", "葡萄",
    "西瓜", "草莓", "芒果", "菠萝"
]

# ================== 主命令自动建议 ==================
class CommandAutoSuggest(AutoSuggest):
    def get_suggestion(self, buffer, document):
        text = document.text
        if not text:
            return None
        for cmd in COMMANDS:
            if cmd.startswith(text):
                return Suggestion(text=cmd[len(text):])
        return None

# ================== 下拉菜单补全器 ==================
class SelectCompleter(Completer):
    """
    为 /select 提供选项补全，空字符串时显示所有选项，
    支持输入前缀过滤，并自动以下拉菜单形式展示。
    """
    def __init__(self, options):
        self.options = options

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        # 无论是否输入文字，都基于前缀过滤
        for opt in self.options:
            if opt.startswith(text):
                yield Completion(
                    text=opt,
                    start_position=-len(text),
                    display=opt,           # 下拉菜单中显示的文字
                    style='fg:ansicyan'    # 可选样式
                )

def select_option(options, prompt_text="请选择一项 > "):
    """
    交互式选择：自动显示下拉菜单，上下键移动，回车选中。
    返回用户选中的字符串，若取消则返回 None。
    """
    if not options:
        print("没有可用的选项。")
        return None

    # 自定义键绑定（不覆盖上下键，只处理 Ctrl+C 等）
    kb = KeyBindings()
    
    @kb.add('c-c')
    def _(event):
        event.app.exit(result=None)   # 按 Ctrl+C 返回 None
    
    style = Style([
        ('prompt', '#00aa00 bold'),
        ('completion-menu.completion', 'bg:#444444 fg:#ffffff'),
        ('completion-menu.completion.current', 'bg:#008888 fg:#ffffff bold'),
    ])

    session = PromptSession(
        completer=SelectCompleter(options),
        key_bindings=kb,
        style=style,
        complete_while_typing=True,    # 实时显示下拉菜单
        enable_history_search=False,   # 避免上下键冲突
        complete_in_thread=True,       # 提升大列表性能
    )

    print("\n💡 提示：使用 ↑ ↓ 键移动高亮，按回车选择，Tab 可自动补全，Ctrl+C 取消\n")
    try:
        selected = session.prompt(prompt_text)
        # 验证选择是否有效（用户可能输入了不在列表中的文字）
        while selected not in options:
            print(f"无效选择：“{selected}”，请从列表中选择。")
            selected = session.prompt(prompt_text)
        return selected
    except (KeyboardInterrupt, EOFError):
        print("\n已取消选择。")
        return None

# ================== 主程序 ==================
def main():
    # 主命令的键绑定（Tab 接受建议）
    kb = KeyBindings()
    
    @kb.add('tab')
    def _(event):
        buffer = event.app.current_buffer
        if buffer.suggestion:
            buffer.insert_text(buffer.suggestion.text)
            buffer.suggestion = None
    
    style = Style([
        ('auto-suggestion', '#888888'),
    ])
    
    session = PromptSession(
        auto_suggest=CommandAutoSuggest(),
        key_bindings=kb,
        style=style,
        enable_history_search=True,
    )
    
    print("启动命令工具（支持 Tab 补全）")
    print("可用命令：" + ", ".join(COMMANDS))
    print("特别命令：/select - 进入带下拉菜单的交互式选择（上下键移动，回车确认）")
    print("按 Ctrl+C 或输入 /exit 退出。\n")
    
    try:
        while True:
            user_input = session.prompt("> ")
            if user_input.lower() in ("/exit", "quit"):
                print("退出程序。")
                break
            
            if user_input.strip() == "/select":
                chosen = select_option(SELECT_OPTIONS)
                if chosen:
                    print(f"你选择了：{chosen}\n")
                else:
                    print("未做选择。\n")
                continue
            
            # 其他命令的处理
            print(f"你输入了命令：{user_input}\n")
    except (KeyboardInterrupt, EOFError):
        print("\n已退出。")

if __name__ == "__main__":
    main()