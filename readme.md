## CapsWriter 简陋的离线版

![client_console](assets/client_console.png)

这是 `CapsWriter` 简陋的离线版，一个 PC 端的语音输入工具。

运行后，只要按下键盘上的 `大写锁定键`，就会开始录音，当你松开 `大写锁定键` 时，就会识别你的录音，并将识别结果立刻输入。


## 下载模型

本工具使用了 [sherpa-onnx](https://k2-fsa.github.io/sherpa/onnx/index.html) 作服务端，载入阿里巴巴开源的 [Paraformer](https://www.modelscope.cn/models/damo/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/summary) 模型（[转为onnx格式](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/offline-paraformer/paraformer-models.html)），整个模型约 1GB 大小。你可以从这里下载到已转换好的模型文件：

- [csukuangfj/sherpa-onnx-paraformer-zh-2023-03-28 at main (huggingface.co)](https://huggingface.co/csukuangfj/sherpa-onnx-paraformer-zh-2023-03-28/tree/main) 
- 百度盘: https://pan.baidu.com/s/1zNHstoWZDJVynCBz2yS9vg 提取码: eu4c 

下载模型后，请将模型文件放入 `paraformer-offline-zh` 文件夹内（如果下载的压缩包则需解压）


## 安装依赖

安装 Python 后，在 `cmd` 窗口进入本文件夹，运行 `pip install -r requirements.txt` 安装依赖

`sherpa-onnx-bin` 文件夹中已经放置了在 Win10-64 端预先编译的 `sherpa-onnx` 二进制。

其它系统暂时需要按照 [sherpa-onnx — sherpa 1.2 documentation](https://k2-fsa.github.io/sherpa/onnx/index.html) 编译后，放入 `sherpa-onnx-bin` 文件夹。

## 运行和使用

1. 运行 `01sherpa-onnx-server.py` 脚本，会载入 Paraformer 模型识别模型（这会占用1GB的内存，载入时长约十几秒）
2. 运行 `02-CapsWriter-client.py` 脚本，它会打开系统默认麦克风，开始监听按键
3. 按住 `CapsLock` 键，录音开始，松开 `CapsLock` 键，录音结束，识别结果立马被输入（录音时长短于0.3秒不算）

## 注意事项

1. 目前使用的模型是 Paraformer 非实时模型，即录完再转，因此录音时间越长，上屏延迟越大。
2. 主流性能的 Windows 笔记本，RTF 大约 0.06，即大约每 10s 录音需 0.6s 转录时长。
3. 本地模型对算力要求非常低，基本无需担心性能问题
4. 暂不支持标点符号，暂不支持逆标准化（如把中文数字转阿拉伯数字）
5. 为方便用户检查录音质量、识别效果，脚本默认开启了保存录音，所有都被保存在了 audios 文件夹

## 打赏

如果你愿意，可以以打赏的方式支持我一下：

![sponsor](assets/sponsor.jpg)