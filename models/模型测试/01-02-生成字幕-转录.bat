@echo off
setlocal enabledelayedexpansion
:: 这个脚本调用 01-01-transcribe-core.py 为一个输入文件生成 txt json srt 字幕文件

:: 进入脚本所在目录
%~d0
cd %~dp0

:: 转录
if exist "model.int8.onnx" (
    python 01-01-transcribe-core.py --paraformer ./model.int8.onnx  --tokens ./tokens.txt %1
   ) else if exist "model_quant.onnx" (
    python 01-01-transcribe-core.py --paraformer ./model_quant.onnx  --tokens ./tokens.txt %1
) 
pause