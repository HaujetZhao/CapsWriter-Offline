"""
LLM 处理器 - 协调器

功能：
1. 协调各个组件（角色加载、上下文管理、客户端池、消息构建）
2. 提供统一的处理接口
3. 流式输出
"""

from typing import Dict, Tuple, Optional
from util.llm_role_loader import RoleLoader
from util.llm_rag import HotwordsRAG
from util.llm_context import ContextManager
from util.llm_watcher import LLMFileWatcher
from util.llm_role_config import RoleConfig
from util.llm_client_pool import ClientPool
from util.llm_message_builder import MessageBuilder


# ======================================================================
# --- LLM 处理器（协调器）---

class LLMHandler:
    """LLM 润色处理器（协调器）"""

    def __init__(self, hotwords_file: str = 'hot-llm.txt'):
        # 角色管理
        self.role_loader = RoleLoader()
        self.roles = self.role_loader.get_roles()

        # 热词 RAG
        self.rag = HotwordsRAG(hotwords_file)

        # 上下文管理器池
        self.context_managers: Dict[str, ContextManager] = {}
        self._init_context_managers()

        # 客户端池
        self.client_pool = ClientPool()

        # 消息构建器
        self.message_builder = MessageBuilder(rag=self.rag)

    def _init_context_managers(self):
        """为启用了历史的角色创建上下文管理器"""
        for role_name, role_config in self.roles.items():
            if role_config.enable_history:
                self.context_managers[role_name] = ContextManager(
                    max_length=role_config.max_context_length,
                    forget_duration=role_config.forget_duration,
                )

    def reload_roles(self):
        """重新加载所有角色（保留历史记录）"""
        # 保存旧的历史记录
        old_contexts = {}
        for role_name, ctx in self.context_managers.items():
            old_contexts[role_name] = {
                'history': ctx.history.copy(),
                'last_interaction': ctx.last_interaction
            }

        # 清空并重新加载
        self.context_managers.clear()
        self.client_pool.clear()
        self.role_loader.load_all_roles()
        self.roles = self.role_loader.get_roles()
        self._init_context_managers()

        # 恢复历史记录
        for role_name, ctx in self.context_managers.items():
            if role_name in old_contexts:
                ctx.history = old_contexts[role_name]['history']
                ctx.last_interaction = old_contexts[role_name]['last_interaction']
                print(f"[上下文管理] 恢复角色 '{role_name}' 的历史记录: {len(ctx.history)} 条")

    def detect_role(self, text: str) -> Tuple[Optional[RoleConfig], str]:
        """检测文本是否匹配某个角色前缀

        Returns:
            (role_config, content) - role_config 是 RoleConfig 对象，content 是去除前缀后的文本
        """
        for role_name, role_config in self.roles.items():
            if role_name == '默认':
                continue

            # 检查是否启用前缀匹配
            if not role_config.match:
                continue

            name = role_config.name
            # 空名字和「默认」都不作为前缀匹配
            if not name or name == '默认':
                continue

            if name and text.startswith(name):
                remaining_text = text[len(name):]
                remaining_text = remaining_text.lstrip('：，。,. ')

                return role_config, remaining_text

        # 未匹配，使用默认角色
        default_role = self.role_loader.get_default_role()
        if default_role.process:
            return default_role, text

        return None, text

    def process(self, text: str, callback=None, should_stop_check=None) -> tuple:
        """处理输入文本

        Args:
            text: 输入文本
            callback: 流式输出的回调函数
            should_stop_check: 检查是否应该停止的函数（返回 True 表示停止）

        Returns:
            (处理后的文本, 输出token数)
        """
        role_config, content = self.detect_role(text)

        if not role_config:
            return (text, 0)

        role_name = role_config.name

        # 获取上下文管理器（如果启用历史）
        context_manager = self.context_managers.get(role_name) if role_config.enable_history else None

        # 构建消息
        messages = self.message_builder.build_messages(role_config, content, context_manager)

        # 获取客户端
        client = self.client_pool.get_client(
            provider=role_config.provider,
            api_url=role_config.api_url,
            api_key=role_config.api_key
        )

        # 构建请求参数
        request_params = {
            'model': role_config.model,
            'messages': messages,
        }

        # 添加生成参数
        if role_config.temperature is not None:
            request_params['temperature'] = role_config.temperature

        if role_config.top_p is not None:
            request_params['top_p'] = role_config.top_p

        if role_config.max_tokens > 0:
            request_params['max_tokens'] = role_config.max_tokens

        # 处理停止序列
        stop = role_config.stop
        if stop:
            if isinstance(stop, str):
                request_params['stop'] = [s.strip() for s in stop.split(',')]
            else:
                request_params['stop'] = stop

        # 合并额外选项
        if role_config.extra_options:
            request_params.update(role_config.extra_options)

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
            if role_config.enable_history and context_manager:
                # 保存完整的用户提示词（包含剪贴板、热词等），而不是原始识别文本
                # messages[-1]['content'] 就是完整的用户提示词
                context_manager.add_message('user', messages[-1]['content'])
                context_manager.add_message('assistant', full_response)

            return (full_response.strip(), total_tokens)

        except Exception as e:
            import traceback
            print(f"[LLM 处理器] 错误: {e}")
            print(f"[LLM 处理器] 错误详情:\n{traceback.format_exc()}")
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


def polish_text(text: str, callback=None, should_stop_check=None) -> tuple:
    """润色文本（便捷函数）

    Args:
        text: 待润色的文本
        callback: 流式输出的回调函数
        should_stop_check: 检查是否应该停止的函数

    Returns:
        (润色后的文本, 输出token数)
    """
    handler = get_handler()
    return handler.process(text, callback, should_stop_check)


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
