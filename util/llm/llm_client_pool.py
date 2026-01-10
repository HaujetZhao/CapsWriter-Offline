"""
LLM 客户端池

功能：
1. 缓存 OpenAI 客户端实例
2. 根据 provider 和 api_url 创建和获取客户端
"""
from openai import OpenAI
from typing import Dict
from util.llm.llm_constants import APIConfig


class ClientPool:
    """OpenAI 客户端池"""

    def __init__(self):
        self._clients: Dict[str, OpenAI] = {}

    def get_client(self, provider: str, api_url: str = '', api_key: str = '') -> OpenAI:
        """获取 OpenAI 客户端（带缓存）

        Args:
            provider: API 提供商（如 'ollama', 'openai'）
            api_url: API 地址（可选，优先使用此值）
            api_key: API Key（可选）

        Returns:
            OpenAI 客户端实例
        """
        cache_key = f"{provider}_{api_url}"

        if cache_key not in self._clients:
            # 获取 api_url（优先使用配置的 URL，否则使用默认值）
            final_url = api_url or APIConfig.DEFAULT_API_URLS.get(provider)

            # 获取 api_key
            final_key = api_key or APIConfig.DEFAULT_API_KEYS.get(provider, '')

            # 创建客户端
            self._clients[cache_key] = OpenAI(
                base_url=final_url,
                api_key=final_key,
            )

        return self._clients[cache_key]

    def clear(self):
        """清空客户端缓存"""
        self._clients.clear()
