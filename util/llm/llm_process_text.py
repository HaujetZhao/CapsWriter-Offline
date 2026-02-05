from dataclasses import dataclass
from typing import Optional

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


async def llm_process_text(text: str, return_result: bool = False, paste: bool = None, matched_hotwords=None, role_name: str = None) -> Optional[LLMResult]:
    """润色文本并直接输出（外部主入口 - Shim）
    
    Args:
        text: 待润色的完整原始文本
        return_result: 是否返回 LLMResult 对象
        paste: 是否强制使用粘贴模式
        matched_hotwords: 潜在热词列表
        role_name: 指定角色名称（来自场景绑定）
    """
    from util.llm.llm_handler import get_handler
    handler = get_handler()
    return await handler.process_and_output(text, return_result, paste, matched_hotwords, role_name=role_name)
