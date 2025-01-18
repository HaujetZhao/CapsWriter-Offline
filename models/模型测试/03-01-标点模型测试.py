import logging
import time

# 关闭 jieba 的 debug
import jieba
from funasr_onnx import CT_Transformer

jieba.setLogLevel(logging.INFO)

print(f"正在载入模型")
t1 = time.time()
model_dir = "."
model = CT_Transformer(model_dir, quantize=True)
print(f"载入模型时间：{time.time() - t1}")


while True:
    text_in = ""
    print("\n\n请输入多行文字，按下回车键完成输入:")
    while True:
        line = input()
        if not line:
            break
        text_in += line
    if text_in:
        result = model(text_in)
        print(result[0])
