"""
LLM 处理器 - 协调器

功能：
1. 协调各个组件（角色加载、上下文管理、客户端池、消息构建）
2. 提供统一的处理接口
3. 流式输出
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any
from pathlib import Path

from .llm_role_loader import RoleLoader
from .llm_context import ContextManager
from .llm_watcher import LLMFileWatcher
from .llm_role_config import RoleConfig
from .llm_client_pool import ClientPool
from .llm_message_builder import MessageBuilder
from .llm_role_detector import RoleDetector
from .llm_processor import LLMProcessor
from .llm_get_selection import get_selected_text, record_selection_usage
from . import logger
from .llm_stop_monitor import StopMonitor
from core.client.udp.udp_broadcaster import broadcast_output_udp


@dataclass
class LLMResult:
    """LLM 处理结果"""
    result: str                    # 润色后的文本
    role_name: Optional[str]       # 角色名
    processed: bool                # 是否经过处理
    token_count: int               # token数
    polish_time: float             # 总耗时（秒）
    input_text: str                # 输入文本（已移除角色前缀）
    generation_time: float = 0.0   # 生成时间（秒，从第一个 token 开始）


# ======================================================================
# --- LLM 处理器（协调器）---

class LLMHandler:
    """LLM 润色处理器（协调器）"""

    def __init__(self, app):
        logger.info("初始化 LLM 处理器")
        self.app = app

        # 获取热词管理器
        self.hotword_manager = app.hotword

        # 角色管理
        self.role_loader = RoleLoader()
        self.roles = self.role_loader.get_roles()
        logger.info(f"已加载角色: {list(self.roles.keys())}")

        # 上下文管理器池
        self.context_managers: Dict[str, ContextManager] = {}
        self._init_context_managers()

        # 客户端池
        self.client_pool = ClientPool()

        # 消息构建器
        self.message_builder = MessageBuilder(app)

        # 角色检测器
        self.role_detector = RoleDetector(self.role_loader)

        # LLM 处理引擎
        self.processor = LLMProcessor(self.client_pool)

        # 5. 子服务监控
        # 配置文件监控
        self.watcher = LLMFileWatcher(
            on_roles_reload=lambda: self.reload_roles(),
            get_roles=lambda: self.roles,
        )
        # 中断按键监控
        self.monitor = StopMonitor()

    def start(self):
        """启动 LLM 系统的子服务监控"""
        self.watcher.start()
        self.monitor.start()
        logger.debug("LLM 系统子服务已启动")

    def stop(self):
        """停止 LLM 系统的子服务监控"""
        self.watcher.stop()
        self.monitor.stop()
        logger.debug("LLM 系统子服务已停止")

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

    def process(self, role_config: RoleConfig, content: str, matched_hotwords=None, callback=None) -> Tuple[str, int, float]:
        """执行实际的 LLM 模型调用（内部方法）

        Args:
            role_config: 角色配置对象
            content: 去除前缀后的输入内容
            matched_hotwords: [(hotword, score), ...] 来自 hot_phoneme 的检索结果
            callback: 流式输出的回调函数

        Returns:
            (处理后的文本, 输出token数, 生成时间秒)
        """
        # 获取中断检查函数
        should_stop_check = lambda: self.monitor.should_stop()
        # 获取处理后的角色名称（空字符串 -> '默认'）
        role_name = role_config.name or RoleConfig.DEFAULT_ROLE_NAME
        logger.debug(f"开始 LLM 核心处理 [角色: {role_name}] [内容长度: {len(content)}]")

        # 获取上下文管理器（如果启用历史）
        context_manager = self.context_managers.get(role_name) if role_config.enable_history else None
        if context_manager:
            logger.debug(f"角色 '{role_name}' 启用历史，当前历史条数: {len(context_manager.history)}")
        
        # 获取选中文字（如果启用）
        selection_text = get_selected_text(role_config, self.app.state)
        
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

    async def process_and_output(self, text: str, paste: bool = None, matched_hotwords=None) -> Optional[LLMResult]:
        """
        统一入口：处理输入文本并根据配置执行输出（打字或弹屏）
        
        Args:
            text: 待润色的完整原始文本（含可能的前缀）
            paste: 是否强制使用粘贴模式（None 则遵循配置）
            matched_hotwords: 潜在热词列表
        """
        import time
        from core.client.llm.llm_output_typing import handle_typing_mode, output_text
        from core.client.llm.llm_output_toast import handle_toast_mode
        from core.client.output.text_output import TextOutput

        start_time = time.time()
        # 重置中断标志
        self.monitor.reset()
        
        # 1. 角色检测
        role_config, content = self.detect_role(text)

        # 2. 如果不匹配任何需要处理的角色
        if not role_config:

            # 打字输出
            await output_text(text, paste)
            
            # 更新全局状态并 UDP 广播
            self.app.state.set_output_text(text)
            broadcast_output_udp(text)

            return LLMResult(result=text, role_name=None, processed=False, 
                                token_count=0, polish_time=0, input_text=text)


        # 4. 根据输出模式分发处理
        if role_config.output_mode == 'toast':
            result, token_count, gen_time = await handle_toast_mode(self, text, role_config, matched_hotwords, content)
        else: # typing
            result, token_count, gen_time = await handle_typing_mode(self, text, paste, matched_hotwords, role_config, content)

        # 5. 后置处理
        # 更新全局状态（即便是中断了，也记录已经输出的部分）
        if result:
            self.app.state.set_output_text(result)
            broadcast_output_udp(result)

        return LLMResult(
            result=result,
            role_name=role_config.name or RoleConfig.DEFAULT_ROLE_NAME,
            processed=True,
            token_count=token_count,
            polish_time=time.time() - start_time,
            input_text=content,
            generation_time=gen_time
        )


# ======================================================================
# --- 测试 ---

if __name__ == "__main__":
    print("=" * 60)
    print("LLM 处理器 - 测试模式")
    print("=" * 60)

    import asyncio
    from core.client.state import ClientState
    from types import SimpleNamespace

    async def run_test_cases():
        # 创建一个模拟的 app 实例
        mock_app = SimpleNamespace()
        mock_app.base_dir = Path(".").resolve()
        
        # 模拟 hotword manager
        mock_app.hotword = SimpleNamespace()
        mock_app.hotword.get_rectify_rag = lambda: None
        
        # 模拟 state
        mock_app.state = ClientState(mock_app)
        
        # 初始化处理器
        handler = LLMHandler(mock_app)
        handler.start()
        
        print(f"\n已加载角色: {list(handler.roles.keys())}")

        test_cases = [
            "呃，我想查看一下当前目录的文件",
            "命令 查看当前目录的文件",
            "Python 读取文件",
        ]

        print("\n--- 测试案例 ---\n")
        try:
            for test_text in test_cases:
                print(f"输入: {test_text}")
                # 注意：这里直接调用 process 而不是 process_and_output，避免依赖复杂的 UI/打字逻辑
                role_config, content = handler.detect_role(test_text)
                if role_config:
                    print(f"检测到角色: {role_config.name}")
                    # 由于是模拟环境，可能无法真正发起请求，这里仅演示逻辑
                else:
                    print("未检测到特定角色")
                print("-" * 40)
        finally:
            handler.stop()

    asyncio.run(run_test_cases())


