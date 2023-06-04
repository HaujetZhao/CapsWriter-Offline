@echo off
set PythonPath=D:\Portable_Programes\CapsWriter-Offline\ve

@REM =====================Server===========================

rmdir /s /q .\dist\start_server
%PythonPath%\Scripts\pyinstaller.exe -i "../assets/icon.ico"   "../start_server.py"

mkdir .\dist\start_server\libs
move .\dist\start_server\* .\dist\start_server\libs\
move .\dist\start_server\yaml .\dist\start_server\libs\
move .\dist\start_server\websockets .\dist\start_server\libs\
move .\dist\start_server\psutil .\dist\start_server\libs\

move  .\dist\start_server\libs\start_server.exe  .\dist\start_server\
move  .\dist\start_server\libs\python310.dll  .\dist\start_server\
move  .\dist\start_server\libs\_socket.pyd  .\dist\start_server\
move  .\dist\start_server\libs\base_library.zip  .\dist\start_server\
move  .\dist\start_server\libs\select.pyd  .\dist\start_server\
move  .\dist\start_server\libs\python310.dll  .\dist\start_server\
move  .\dist\start_server\libs\pyexpat.pyd  .\dist\start_server\
move  .\dist\start_server\libs\win32api.pyd  .\dist\start_server\

:: librosa
mkdir .\dist\start_server\librosa 
xcopy /S /Y %PythonPath%\Lib\site-packages\librosa .\dist\start_server\librosa 

:: numpy
rmdir /s /q .\dist\start_server\numpy
mkdir  .\dist\start_server\numpy
xcopy /S /Y %PythonPath%\Lib\site-packages\numpy .\dist\start_server\numpy

:: onnxruntime
rmdir /s /q .\dist\start_server\onnxruntime
mkdir  .\dist\start_server\onnxruntime
xcopy /S /Y %PythonPath%\Lib\site-packages\onnxruntime .\dist\start_server\onnxruntime


:: models
mkdir .\dist\start_server\models 
copy ..\models\请将语音和标点模型放到此文件夹 .\dist\start_server\models\
xcopy /S /Y ..\models .\dist\start_server\models 

:: core_server.py
copy ..\core_server.py .\dist\start_server\
copy ..\hot-zh.txt .\dist\start_server\
copy ..\hot-en.txt .\dist\start_server\
copy ..\hot-rule.txt .\dist\start_server\

@REM =====================Client===========================


rmdir /s /q .\dist\start_client

%PythonPath%\Scripts\pyinstaller.exe -i "../assets/icon.ico"   "../start_client.py" 

copy .\dist\start_client\start_client.exe .\dist\start_server\
copy ..\core_client.py .\dist\start_server\

@REM =====================About===========================

mkdir  .\dist\start_server\assets
xcopy /S /Y ..\assets .\dist\start_server\assets 
copy ..\readme.md .\dist\start_server\


pause