00 用于把从 ModelScope 下载的 Paraformer-onnx 转为 Sherpa-onnx 可以使用的模型

01 用于快速调用 Sherpa-onnx 和 Paraformer-onnx 转录音频文件，生成 txt json srt，但每次转录都需要载入一次模型文件

02 用于启动 Sherpa-onnx 的 websocket 服务端，只需要载入一次模型文件，就可用客户端多次转录

03 用于测试 funasr 的标点模型