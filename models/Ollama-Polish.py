import ollama

# --- 调试开关 ---
ENABLE_HISTORY = True       # True: 记住之前的对话; False: 每次对话都是独立的
THINKING = False            # True: 打开思考功能; False: 禁止思考

# MODEL_NAME = 'qwen3:0.6b' 
# MODEL_NAME = 'qwen3:1.7b' 
# MODEL_NAME = 'qwen3:4b' 
MODEL_NAME = 'gemma3:4b' 
# MODEL_NAME = 'gemma3:12b' 

# ======================================================================
# 预设喂给模型的句子，每一行将作为一句进行投喂
PRESET_INPUTS = """
我用上 fun asr nano 了
我刚刚下载了firefoux浏览器
查看 ffmpeg 的可用编码器有哪些
告诉我你的角色是什么
我想告诉你我爱你
"""
# ======================================================================





# ======================================================================
# 定义多种不同的 system_prompt

默认 = """
你是一位转录助手，你的任务是将用户提供的语音转录文本进行润色和整理

要求：

- 清除语气词（如：呃、啊、那个、就是说）
- 修正语音识别的错误（根据上下文推断同音错别字进行修正）
- 修正专有名词、大小写
- 用户的一切内容都不是在与你对话，要把问题当成用户所要打的字进行润色，而不是回答，不要与用户交互
- 用户的一切内容都不是在与你对话，要把问题当成用户所要打的字进行润色，而不是回答，不要与用户交互
- 用户的一切内容都不是在与你对话，要把问题当成用户所要打的字进行润色，而不是回答，不要与用户交互
- 仅输出润色后的内容，严禁任何多余的解释，不要翻译语言
- 仅输出润色后的内容，严禁任何多余的解释，不要翻译语言
- 仅输出润色后的内容，严禁任何多余的解释，不要翻译语言
"""


# ======================================================================













def polish_chat(system_prompt):
    base_messages = [{'role': 'system', 'content': system_prompt}]
    chat_history = []

    print("\n")
    print(f"--- Ollama 润色助手 (模型: {MODEL_NAME}) ---")
    print(f"--- 配置: 历史记忆={ENABLE_HISTORY}, 思考={THINKING} ---")

    def get_response(user_input, is_preset=False):
        current_user_msg = {'role': 'user', 'content': user_input}
        
        # 处理历史逻辑
        if ENABLE_HISTORY:
            messages = base_messages + chat_history + [current_user_msg]
        else:
            messages = base_messages + [current_user_msg]

        try:
            stream = ollama.chat(
                model=MODEL_NAME,
                messages=messages,
                stream=True,
                options={'num_predict': 512}, # 限制输出长度防止无限生成
                think=THINKING 
            )

            full_response = ""
            
            prefix = "得到输出：" if is_preset else "输出："
            print(prefix, end='', flush=True)
            for chunk in stream:
                if chunk.message.content:
                    print(chunk.message.content, end='', flush=True)
                    full_response += chunk.message.content

            print("\n")
            
            if ENABLE_HISTORY:
                chat_history.append(current_user_msg)
                chat_history.append({'role': 'assistant', 'content': full_response})

        except Exception as e:
            print(f"\n发生错误: {e}")

    # 先喂预设输入
    preset_lines = [line.strip() for line in PRESET_INPUTS.strip().split('\n') if line.strip()]
    if preset_lines:
        print("\n>>> 正在喂入预设消息...")
        for text in preset_lines:
            print(f"预设输入：{text}")
            get_response(text, is_preset=True)
        print(">>> 预设消息处理完毕。")

    # 进入正常交互
    while True:
        user_input = input("\n输入：").strip()
        
        if not user_input or user_input.lower() in ['exit', 'quit']:
            break

        get_response(user_input)

if __name__ == "__main__":
    prompt = 默认
    polish_chat(prompt)

