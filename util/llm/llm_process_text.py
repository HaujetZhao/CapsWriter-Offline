"""
LLM 结果输出 - 主入口

根据 output_mode 选择不同的输出方式：
- typing: 直接打字输出
- toast: 浮动窗口显示
"""
import time
from dataclasses import dataclass
from typing import Optional
from config import ClientConfig as Config
from util.client.processing.output import TextOutput
from util.llm.llm_clipboard import copy_to_clipboard
from util.llm.llm_output_typing import handle_typing_mode, output_text
from util.llm.llm_output_toast import handle_toast_mode


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


async def llm_process_text(text: str, return_result: bool = False, paste: bool = None, matched_hotwords=None) -> Optional[LLMResult]:
    """
    异步处理并输出 LLM 润色后的结果
    根据 output_mode 选择不同的处理方式

    Args:
        text: 待润色的文本
        return_result: 是否返回润色后的文本（用于控制台显示）
        paste: 是否使用 paste 方式（None 表示使用 Config.paste）
        matched_hotwords: [(hotword, score), ...] 来自 hot_phoneme 的检索结果

    Returns:
        如果 return_result=True，返回 LLMResult 对象；否则返回 None
    """
    from util.llm.llm_handler import get_handler

    start_time = time.time()

    # 获取当前角色的输出模式
    handler = get_handler()
    role_config, content = handler.detect_role(text)

    if not role_config:
        # 如果没有匹配到角色（包括默认角色被禁用），直接输出原文本
        result_text = TextOutput.strip_punc(text)
        await output_text(result_text, paste)
        if return_result:
            return LLMResult(
                result=result_text,
                role_name=None,
                processed=False,
                token_count=0,
                polish_time=0,
                input_text=text
            )
        return None

    # 获取角色显示名称（提前获取，供后续使用）
    name = role_config.name
    display_name = name if name else '默认'

    # 检查是否启用 LLM 处理
    if not role_config.process:
        # 角色匹配但未启用 LLM（如占位符），原样输出去除前缀后的文本
        result_text = TextOutput.strip_punc(content)
        await output_text(result_text, paste)
        if return_result:
            return LLMResult(
                result=result_text,
                role_name=display_name,
                processed=False,
                token_count=0,
                polish_time=0,
                input_text=content
            )
        return None

    output_mode = role_config.output_mode

    # 根据输出模式处理
    if output_mode == 'toast':
        result, token_count, generation_time = await handle_toast_mode(text, role_config, matched_hotwords)
    else:  # typing
        result, token_count, generation_time = await handle_typing_mode(text, paste, matched_hotwords)

    # 计算润色耗时
    polish_time = time.time() - start_time

    # 输出完成后复制到剪贴板（如果启用）
    if result and role_config.set_clipboard:
        copy_to_clipboard(result)

    if return_result:
        return LLMResult(
            result=result,
            role_name=display_name,
            processed=True,
            token_count=token_count,
            polish_time=polish_time,
            input_text=content,
            generation_time=generation_time
        )
    return None
