"""
LLM 处理器 - 协调器

功能：
1. 协调各个组件（角色加载、上下文管理、客户端池、消息构建）
2. 提供统一的处理接口
3. 流式输出
"""

from typing import Dict, Tuple, Optional, Any
from pathlib import Path

from util.llm.llm_role_loader import RoleLoader
from util.llm.llm_context import ContextManager
from util.llm.llm_watcher import LLMFileWatcher
from util.llm.llm_role_config import RoleConfig
from util.llm.llm_client_pool import ClientPool
from util.llm.llm_message_builder import MessageBuilder
from util.llm.llm_role_detector import RoleDetector
from util.llm.llm_processor import LLMProcessor
from util.llm.llm_get_selection import get_selected_text, record_selection_usage
from util.llm.llm_process_text import LLMResult
from . import logger
from util.hotword import get_hotword_manager


# ======================================================================
# --- LLM 处理器（协调器）---

class LLMHandler:
    """LLM 润色处理器（协调器）"""

    def __init__(self, hotwords_file: str = 'hot.txt'):
        logger.info("初始化 LLM 处理器")

        # 获取热词管理器单例
        self.hotword_manager = get_hotword_manager()

        # 角色管理
        self.role_loader = RoleLoader()
        self.roles = self.role_loader.get_roles()
        logger.info(f"已加载角色: {list(self.roles.keys())}")

        # 上下文管理器池
        self.context_managers: Dict[str, ContextManager] = {}
        self._init_context_managers()

        # 客户端池
        self.client_pool = ClientPool()

        # 消息构建器（内部从 HotwordManager 获取 rectify_rag）
        self.message_builder = MessageBuilder()

        # 角色检测器
        self.role_detector = RoleDetector(self.role_loader)

        # LLM 处理引擎
        self.processor = LLMProcessor(self.client_pool)

    def _init_context_managers(self):
        """为启用了历史的角色创建上下文管理器"""
        for role_name, role_config in self.roles.items():
            if role_config.enable_history:
                self.context_managers[role_name] = ContextManager(
                    max_length=role_config.max_context_length,
                )

    def reload_roles(self):
        """重新加载所有角色（保留历史记录）"""
        logger.info("重新加载角色配置")
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
        logger.info(f"重新加载后角色: {list(self.roles.keys())}")
        self._init_context_managers()

        # 恢复历史记录
        for role_name, ctx in self.context_managers.items():
            if role_name in old_contexts:
                ctx.history = old_contexts[role_name]['history']
                ctx.last_interaction = old_contexts[role_name]['last_interaction']
                logger.debug(f"恢复角色 '{role_name}' 的历史记录: {len(ctx.history)} 条")

    def clear_history(self):
        """清除所有角色的对话历史记录"""
        logger.info("正在清除所有角色的对话历史记录...")
        count = 0
        for role_name, manager in self.context_managers.items():
            manager.clear()
            count += 1
        logger.info(f"已清除 {count} 个角色的对话历史记录")

    def detect_role(self, text: str) -> Tuple[Optional[RoleConfig], str]:
        """检测文本是否匹配某个角色前缀

        Args:
            text: 输入文本

        Returns:
            (role_config, content) - role_config 是 RoleConfig 对象，content 是去除前缀后的文本
        """
        return self.role_detector.detect(text)

    def process(self, role_config: RoleConfig, content: str, matched_hotwords=None, callback=None, should_stop_check=None) -> Tuple[str, int, float]:
        """执行实际的 LLM 模型调用（内部方法）

        Args:
            role_config: 角色配置对象
            content: 去除前缀后的输入内容
            matched_hotwords: [(hotword, score), ...] 来自 hot_phoneme 的检索结果
            callback: 流式输出的回调函数
            should_stop_check: 检查是否应该停止的函数（返回 True 表示停止）

        Returns:
            (处理后的文本, 输出token数, 生成时间秒)
        """
        # 获取处理后的角色名称（空字符串 -> '默认'）
        role_name = role_config.name or RoleConfig.DEFAULT_ROLE_NAME
        logger.debug(f"开始 LLM 核心处理 [角色: {role_name}] [内容长度: {len(content)}]")

        # 获取上下文管理器（如果启用历史）
        context_manager = self.context_managers.get(role_name) if role_config.enable_history else None
        if context_manager:
            logger.debug(f"角色 '{role_name}' 启用历史，当前历史条数: {len(context_manager.history)}")
        
        # 获取选中文字（如果启用）
        selection_text = get_selected_text(role_config)
        
        # 构建消息
        messages = self.message_builder.build_messages(
            role_config, content, context_manager,
            hotwords=matched_hotwords,
            selection_text=selection_text
        )
        
        # 使用 LLM 处理引擎执行请求
        result_text, token_count, gen_time = self.processor.process(
            role_config=role_config,
            messages=messages,
            callback=callback,
            should_stop_check=should_stop_check,
            context_manager=context_manager
        )

        # 记录选中文字的使用（用于下一轮判断是否重复）
        record_selection_usage(role_config, selection_text)

        return result_text, token_count, gen_time

    async def process_and_output(self, text: str, return_result: bool = False, paste: bool = None, matched_hotwords=None) -> Optional[LLMResult]:
        """
        统一入口：处理输入文本并根据配置执行输出（打字或弹屏）
        
        Args:
            text: 待润色的完整原始文本（含可能的前缀）
            return_result: 是否返回 LLMResult 对象
            paste: 是否强制使用粘贴模式（None 则遵循配置）
            matched_hotwords: 潜在热词列表
        """
        import time
        from util.llm.llm_output_typing import handle_typing_mode, output_text
        from util.llm.llm_output_toast import handle_toast_mode
        from util.client.output.text_output import TextOutput

        start_time = time.time()
        
        # 1. 角色检测
        role_config, content = self.detect_role(text)

        # 2. 如果不匹配任何需要处理的角色（或者默认角色被禁用）
        if not role_config:
            result_text = TextOutput.strip_punc(text)
            await output_text(result_text, paste)
            
            # 更新全局状态并 UDP 广播
            from util.client.state import get_state
            get_state().set_output_text(result_text)

            if return_result:
                return LLMResult(result=result_text, role_name=None, processed=False, 
                                 token_count=0, polish_time=0, input_text=text)
            return None

        # 3. 检查是否启用 LLM 处理
        display_name = role_config.name or RoleConfig.DEFAULT_ROLE_NAME
        if not role_config.process:
            # 角色匹配但禁用 LLM（如只是占位符），原样输出
            result_text = TextOutput.strip_punc(content)
            await output_text(result_text, paste)
            
            # 更新全局状态并 UDP 广播
            from util.client.state import get_state
            get_state().set_output_text(result_text)

            if return_result:
                return LLMResult(result=result_text, role_name=display_name, processed=False,
                                 token_count=0, polish_time=0, input_text=content)
            return None

        # 4. 根据输出模式分发处理
        if role_config.output_mode == 'toast':
            result, token_count, gen_time = await handle_toast_mode(text, role_config, matched_hotwords, content)
        else: # typing
            result, token_count, gen_time = await handle_typing_mode(text, paste, matched_hotwords, role_config, content)

        # 5. 后置处理
        # 更新全局状态（即便是中断了，也记录已经输出的部分）
        if result:
            from util.client.state import get_state
            get_state().set_output_text(result)

        if return_result:
            return LLMResult(
                result=result,
                role_name=display_name,
                processed=True,
                token_count=token_count,
                polish_time=time.time() - start_time,
                input_text=content,
                generation_time=gen_time
            )
        return None


# ======================================================================
# --- 全局实例 ---

_handler: Optional[LLMHandler] = None
_watcher: Optional[LLMFileWatcher] = None


def get_handler() -> LLMHandler:
    """获取 LLM 处理器实例（单例）"""
    global _handler, _watcher

    if _handler is None:
        _handler = LLMHandler()
        # 创建 Watcher，传入回调函数实现解耦
        _watcher = LLMFileWatcher(
            on_roles_reload=lambda: _handler.reload_roles(),
            get_roles=lambda: _handler.roles,
        )
        _watcher.start()

    return _handler


def init_llm_system():
    """初始化 LLM 系统（便捷函数）"""
    from config_client import ClientConfig as Config
    if Config.llm_enabled:
        try:
            get_handler()
        except Exception as e:
            from util.client.state import console
            console.print(f'[red]LLM 系统初始化失败: {e}[/]')
            logger.error(f"LLM 系统初始化失败: {e}", exc_info=True)


async def llm_process_text(text: str, return_result: bool = False, paste: bool = None, matched_hotwords=None) -> Optional[LLMResult]:
    """润色文本并直接输出（外部主入口）"""
    handler = get_handler()
    return await handler.process_and_output(text, return_result, paste, matched_hotwords)


def clear_llm_history():
    """清除 LLM 对话历史（便捷函数）"""
    handler = get_handler()
    handler.clear_history()


# ======================================================================
# --- 测试 ---

if __name__ == "__main__":
    print("=" * 60)
    print("LLM 处理器 - 测试模式")
    print("=" * 60)

    import asyncio
    
    async def run_test_cases():
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
            result = await llm_process_text(test_text)
            print()
            print("-" * 40)

    asyncio.run(run_test_cases())
