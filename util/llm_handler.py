"""
LLM 处理器 - 使用 OpenAI 库

功能：
1. 根据输入前缀匹配角色
2. 调用 LLM API 进行处理
3. 流式输出（typing 和 toast 模式）
4. 上下文管理
5. 热词 RAG 检索
6. 文件监控（自动重载修改的角色配置）
"""

from typing import Dict, List, Tuple, Optional
from openai import OpenAI

from .llm_role_loader import RoleLoader
from .llm_rag import HotwordsRAG
from .llm_context import ContextManager
from .llm_watcher import LLMFileWatcher


# ======================================================================
# --- API 配置映射 ---
# provider 仅作为标识，当 api_url 为空时用于查找默认 URL
# 可以随意填写，也可以添加新的 provider 和对应的默认 URL

API_URLS = {
    'ollama': 'http://localhost:11434/v1',
    'openai': 'https://api.openai.com/v1',
    'deepseek': 'https://api.deepseek.com/v1',
    'moonshot': 'https://api.moonshot.cn/v1',
    'zhipu': 'https://open.bigmodel.cn/api/paas/v4',
    # 可以添加更多 provider
}

DEFAULT_API_KEYS = {
    'ollama': 'ollama',
    'openai': '',
    'deepseek': '',
    'moonshot': '',
    'zhipu': '',
    # 可以添加更多默认 key
}


# ======================================================================
# --- LLM 处理器 ---

class LLMHandler:
    """LLM 润色处理器"""

    def __init__(self, hotwords_file: str = 'hot-llm.txt'):
        self.role_loader = RoleLoader()
        self.roles = self.role_loader.get_roles()

        # 热词 RAG
        self.rag = HotwordsRAG(hotwords_file)

        # 上下文管理器
        self.context_managers: Dict[str, ContextManager] = {}
        self._init_context_managers()

        # OpenAI 客户端缓存
        self._clients: Dict[str, OpenAI] = {}

    def _init_context_managers(self):
        """为启用了历史的角色创建上下文管理器"""
        for role_name, role_config in self.roles.items():
            if role_config.get('enable_history', False):
                self.context_managers[role_name] = ContextManager(
                    max_length=role_config.get('max_context_length', 2000),
                    forget_duration=role_config.get('forget_duration', 300),
                )

    def reload_roles(self):
        """重新加载所有角色"""
        self.context_managers.clear()
        self._clients.clear()
        self.role_loader.load_all_roles()
        self.roles = self.role_loader.get_roles()
        self._init_context_managers()

    def get_client(self, role_config: Dict) -> OpenAI:
        """获取 OpenAI 客户端（带缓存）"""
        provider = role_config['provider']
        cache_key = f"{provider}_{role_config.get('api_url', '')}"

        if cache_key not in self._clients:
            # 获取 api_url（优先使用配置的 URL，否则使用默认值）
            api_url = role_config.get('api_url') or API_URLS.get(provider)

            # 获取 api_key
            api_key = role_config.get('api_key') or DEFAULT_API_KEYS.get(provider, '')

            # 创建客户端
            self._clients[cache_key] = OpenAI(
                base_url=api_url,
                api_key=api_key,
            )

        return self._clients[cache_key]

    def detect_role(self, text: str) -> Tuple[Optional[str], Optional[Dict], str]:
        """检测文本是否匹配某个角色前缀"""
        for role_name, role_config in self.roles.items():
            if role_name == '默认':
                continue

            # 检查是否启用前缀匹配
            if not role_config.get('match', True):
                continue

            name = role_config.get('name', '')
            # 空名字和「默认」都不作为前缀匹配
            if not name or name == '默认':
                continue

            if name and text.startswith(name):
                remaining_text = text[len(name):]
                remaining_text = remaining_text.lstrip('：，。,. ')

                return role_name, role_config, remaining_text

        # 未匹配，使用默认角色
        default_role = self.role_loader.get_default_role()
        if default_role.get('process', True):
            return '默认', default_role, text

        return None, None, text

    def build_messages(self, text: str, role_config: Dict, role_name: str, clipboard_text: str = "") -> List[Dict]:
        """构建消息列表

        Args:
            text: 输入文本
            role_config: 角色配置
            role_name: 角色名称
            clipboard_text: 剪贴板内容（可选）

        Returns:
            消息列表
        """
        messages = [
            {'role': 'system', 'content': role_config['system_prompt'].strip()}
        ]

        # 添加历史
        if role_config.get('enable_history', False) and role_name in self.context_managers:
            history = self.context_managers[role_name].get_history()
            messages.extend(history)

        # 热词 RAG - 生成提示并添加到用户消息
        user_content_parts = []

        if role_config.get('enable_hotwords', False):
            hotword_prompt = self.rag.format_prompt(text)
            if hotword_prompt:
                user_content_parts.append(hotword_prompt)

        # 剪贴板内容
        if clipboard_text:
            user_content_parts.append(f"剪贴板内容：{clipboard_text}")

        # 用户输入
        if user_content_parts:
            user_content = "\n\n".join(user_content_parts) + "\n\n用户输入：" + text
        else:
            user_content = text

        messages.append({'role': 'user', 'content': user_content})

        # DEBUG: 打印完整的 prompt
        print(f"\n[LLM 完整 Prompt]")
        print(f"角色: {role_name}")
        print("=" * 60)
        for msg in messages:
            print(f"\n[{msg['role'].upper()}]")
            print(msg['content'])
        print("=" * 60 + "\n")

        return messages

    def process(self, text: str, clipboard_text: str = "", callback=None, should_stop_check=None) -> tuple:
        """处理输入文本

        Args:
            text: 输入文本
            clipboard_text: 剪贴板内容（可选）
            callback: 流式输出的回调函数
            should_stop_check: 检查是否应该停止的函数（返回 True 表示停止）

        Returns:
            (处理后的文本, 输出token数)
        """
        role_name, role_config, content = self.detect_role(text)

        if not role_config:
            return (text, 0)

        messages = self.build_messages(content, role_config, role_name, clipboard_text)
        client = self.get_client(role_config)

        # 构建请求参数
        request_params = {
            'model': role_config['model'],
            'messages': messages,
        }

        # 添加生成参数
        if role_config.get('temperature') is not None:
            request_params['temperature'] = role_config['temperature']

        if role_config.get('top_p') is not None:
            request_params['top_p'] = role_config['top_p']

        if role_config.get('max_tokens', 0) > 0:
            request_params['max_tokens'] = role_config['max_tokens']

        # 处理停止序列
        stop = role_config.get('stop', '')
        if stop:
            if isinstance(stop, str):
                request_params['stop'] = [s.strip() for s in stop.split(',')]
            else:
                request_params['stop'] = stop

        # 合并额外选项
        extra_options = role_config.get('extra_options', {})
        if extra_options:
            request_params.update(extra_options)

        try:
            full_response = ""
            total_tokens = 0

            # 流式输出（typing 和 toast 都使用流式）
            request_params['stream'] = True
            stream = client.chat.completions.create(**request_params)

            for chunk in stream:
                # 检查是否应该停止
                if should_stop_check and should_stop_check():
                    break

                if chunk.choices[0].delta.content:
                    content_chunk = chunk.choices[0].delta.content
                    full_response += content_chunk
                    if callback:
                        callback(content_chunk)

                # 统计 token 数（在最后一个 chunk 中获取）
                # 注意：某些提供商（如 Ollama）的流式响应不包含 usage
                if hasattr(chunk, 'usage') and chunk.usage:
                    if hasattr(chunk.usage, 'completion_tokens'):
                        total_tokens = chunk.usage.completion_tokens or 0

            # 更新历史
            if role_config.get('enable_history', False) and role_name in self.context_managers:
                ctx = self.context_managers[role_name]
                ctx.add_message('user', content)
                ctx.add_message('assistant', full_response)

            return (full_response.strip(), total_tokens)

        except Exception as e:
            print(f"[LLM 处理器] 错误: {e}")
            return (text, 0)


# ======================================================================
# --- 全局实例 ---

_handler: Optional[LLMHandler] = None
_watcher: Optional[LLMFileWatcher] = None


def get_handler() -> LLMHandler:
    """获取 LLM 处理器实例（单例）"""
    global _handler, _watcher

    if _handler is None:
        _handler = LLMHandler()
        _watcher = LLMFileWatcher(_handler)
        _watcher.start()
        # 加载热词到 RAG
        _handler.rag.load_hotwords()

    return _handler


def init_llm_system():
    """初始化 LLM 系统（便捷函数）"""
    from config import ClientConfig as Config
    if Config.llm_enabled:
        try:
            get_handler()
        except Exception as e:
            from util.client_cosmic import console
            console.print(f'[red]LLM 系统初始化失败: {e}[/]')


def polish_text(text: str, clipboard_text: str = "", callback=None, should_stop_check=None) -> tuple:
    """润色文本（便捷函数）

    Args:
        text: 待润色的文本
        clipboard_text: 剪贴板内容（可选）
        callback: 流式输出的回调函数
        should_stop_check: 检查是否应该停止的函数

    Returns:
        (润色后的文本, 输出token数)
    """
    handler = get_handler()
    return handler.process(text, clipboard_text, callback, should_stop_check)


# ======================================================================
# --- 测试 ---

if __name__ == "__main__":
    print("=" * 60)
    print("LLM 处理器 - 测试模式（使用 OpenAI 库）")
    print("=" * 60)

    handler = get_handler()

    print(f"\n已加载角色: {list(handler.roles.keys())}")

    test_cases = [
        "呃，我想查看一下当前目录的文件",
        "命令 查看当前目录的文件",
        "Python 读取文件",
    ]

    print("\n--- 测试案例 ---\n")

    for test_text in test_cases:
        print(f"输入: {test_text}")
        print(f"输出: ", end='', flush=True)

        result = polish_text(test_text, callback=lambda x: print(x, end='', flush=True))
        print()
        print("-" * 40)

    print("\n--- 交互模式（输入 'quit' 退出）---\n")

    while True:
        try:
            user_input = input(">>> ").strip()

            if not user_input or user_input.lower() in ['quit', 'exit', '退出']:
                break

            result = polish_text(user_input, callback=lambda x: print(x, end='', flush=True))
            print()

        except KeyboardInterrupt:
            print("\n\n再见！")
            break
