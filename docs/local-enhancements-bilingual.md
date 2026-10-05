# CapsWriter-Offline local enhancements / 本地增强功能

## 中文

基于 CapsWriter-Offline v2.6 的本地改进：

1. **能量静音过滤**：仅对麦克风输入使用保守的分帧 RMS/峰值检测；整段接近静音时跳过 ASR，保留原始语音和录音时长，不影响文件转录。
2. **整段语气词过滤**：仅当最终麦克风结果全部由已知中英文语气词构成时，才清空该结果；包含实质内容的句子以及文件转录保持不变。
3. **Windows 录音状态悬浮窗**：显示录音计时、当前实际快捷键和识别状态；识别输出完成后自动隐藏。窗口不抢焦点、不拦截鼠标。此功能为可选组件，需单独构建并通过启动脚本启动。

### 验证

本机验证覆盖纯静音、容易被误识别成语气词的静音片段、正常语音、安静/短语音，以及悬浮窗的录音/识别/隐藏状态和快捷键显示。语气词检测采用明确词表，不能保证覆盖所有模型幻觉或所有语言；静音阈值也可能需要按麦克风噪声水平调整。

## English

Local enhancements based on CapsWriter-Offline v2.6:

1. **Energy-based silence gate**: Applies conservative frame-level RMS and peak checks to microphone input only. Near-silent recordings bypass ASR while preserving the original speech samples and recording duration; file transcription is unchanged.
2. **Filler-only result suppression**: Clears a final microphone result only when the entire result consists of recognized Chinese/English fillers. Sentences containing substantive content and file transcription are unchanged.
3. **Windows recording-status overlay**: Shows recording time, the actual shortcut used, and recognition status, then hides after output completes. It does not steal focus or intercept mouse input. This is an optional component that must be built and started separately.

### Validation

Local checks covered pure silence, quiet clips previously misrecognized as fillers, normal speech, quiet/short voiced audio, and overlay recording/recognition/hide states and shortcut labels. Filler detection uses a finite vocabulary and cannot cover every hallucination or language. Silence thresholds may need adjustment for a user's microphone noise floor.
