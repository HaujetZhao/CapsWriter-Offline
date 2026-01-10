"""
LLM 接口定义

使用 Protocol 定义组件接口，实现依赖倒置原则
"""
from typing import Protocol, List, Dict, Optional, Tuple, Any
from abc import ABC, abstractmethod


# ======================================================================
# --- 客户端接口 ---

class LLMClient(Protocol):
    """LLM 客户端接口"""

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        stream: bool = False,
        **kwargs
    ) -> Any:
        """聊天接口"""
        ...


# ======================================================================
# --- 上下文管理接口 ---

class IContextManager(Protocol):
    """上下文管理器接口"""

    def add_message(self, role: str, content: str) -> None:
        """添加消息到历史"""
        ...

    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        ...


# ======================================================================
# --- RAG 接口 ---

class IRAG(Protocol):
    """RAG 检索接口"""

    def search(self, text: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """搜索相关内容"""
        ...

    def format_prompt(self, text: str) -> str:
        """生成提示词"""
        ...


# ======================================================================
# --- 消息构建接口 ---

class IMessageBuilder(Protocol):
    """消息构建器接口"""

    def build_messages(
        self,
        role_config: Any,
        text: str,
        context_manager: Optional[IContextManager] = None
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        ...


# ======================================================================
# --- 角色加载接口 ---

class IRoleLoader(Protocol):
    """角色加载器接口"""

    def get_roles(self) -> Dict[str, Any]:
        """获取所有角色"""
        ...

    def get_default_role(self) -> Any:
        """获取默认角色"""
        ...

    def reload_role(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """重新加载单个角色"""
        ...

    def load_all_roles(self) -> List[Dict[str, Any]]:
        """加载所有角色"""
        ...


# ======================================================================
# --- 抽象基类（用于实现） ---

class AbstractContextManager(ABC):
    """上下文管理器抽象基类"""

    @abstractmethod
    def add_message(self, role: str, content: str) -> None:
        """添加消息到历史"""
        pass

    @abstractmethod
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        pass


class AbstractRAG(ABC):
    """RAG 检索抽象基类"""

    @abstractmethod
    def search(self, text: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """搜索相关内容"""
        pass

    @abstractmethod
    def format_prompt(self, text: str) -> str:
        """生成提示词"""
        pass


class AbstractMessageBuilder(ABC):
    """消息构建器抽象基类"""

    @abstractmethod
    def build_messages(
        self,
        role_config: Any,
        text: str,
        context_manager: Optional[IContextManager] = None
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        pass
