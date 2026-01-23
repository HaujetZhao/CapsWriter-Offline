"""
ASR 演示脚本 - 简单直接的使用示例
"""

import os
from fun_asr_gguf import create_asr_engine


# ==================== Vulkan 选项 ====================

os.environ["VK_ICD_FILENAMES"] = "none"       # 禁止 Vulkan
# os.environ["GGML_VK_VISIBLE_DEVICES"] = "0"   # 禁止 Vulkan 用独显（强制用集显）
# os.environ["GGML_VK_DISABLE_F16"] = "1"       # 禁止 VulkanFP16 计算（Intel集显fp16有溢出问题）


# ==================== 配置区域 ====================

# 音频文件路径
audio_file = "input.mp3"

# 语言设置（None=自动检测, "中文", "英文", "日文" 等）
language = None

# 上下文信息（留空则不使用）
context = "这是1004期睡前消息节目，主持人叫督工，助理叫静静"

# 是否启用 CTC 辅助（True=提供时间戳和热词, False=仅LLM）
enable_ctc = True

# 是否打印详细信息
verbose = True

# 是否以 JSON 格式输出结果
json_output = False

# 模型文件路径
model_dir = "models/FunASR-Nano/Fun-ASR-Nano-GGUF"
encoder_onnx_path = f"{model_dir}/Fun-ASR-Nano-Encoder-Adaptor.fp32.onnx"
ctc_onnx_path = f"{model_dir}/Fun-ASR-Nano-CTC.int8.onnx"
decoder_gguf_path = f"{model_dir}/Fun-ASR-Nano-Decoder.q8_0.gguf"
tokens_path = f"{model_dir}/tokens.txt"
hotwords_path = "./hot.txt"  # 可选，留空则不使用热词

# ==================== 语言说明 ====================

"""
Fun-ASR-Nano-2512
    中文、英文、日文
     
Fun-ASR-MLT-Nano-2512
    中文、英文、粤语、日文、韩文、越南语、印尼语、泰语、马来语、菲律宾语、阿拉伯语、
    印地语、保加利亚语、克罗地亚语、捷克语、丹麦语、荷兰语、爱沙尼亚语、芬兰语、希腊语、
    匈牙利语、爱尔兰语、拉脱维亚语、立陶宛语、马耳他语、波兰语、葡萄牙语、罗马尼亚语、
    斯洛伐克语、斯洛文尼亚语、瑞典语 
"""

# ==================== 执行区域 ====================

def main():

    print("="*70)
    print("ASR 语音识别")
    print("="*70)

    # 创建 ASR 引擎
    engine = create_asr_engine(
        encoder_onnx_path=encoder_onnx_path,
        ctc_onnx_path=ctc_onnx_path,
        decoder_gguf_path=decoder_gguf_path,
        tokens_path=tokens_path,
        hotwords_path=hotwords_path,
        enable_ctc=enable_ctc,
        verbose=verbose,
    )

    # 转录音频
    result = engine.transcribe(
        audio_file, 
        language=language, 
        context=context, 
        verbose=verbose
    )

    # 输出结果
    if json_output:
        import json
        print("\n" + "="*70)
        print("识别结果 (JSON)")
        print("="*70)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    # 清理资源
    engine.cleanup()

    return 0


if __name__ == "__main__":
    exit(main())
