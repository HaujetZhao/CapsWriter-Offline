@echo off
set PythonPath=D:\Users\Haujet\AppData\Local\Programs\Python\Python310

@REM =====================Server===========================

rmdir /s /q .\dist\start_server
%PythonPath%\Scripts\pyinstaller.exe -i "../assets/icon.ico" -D  "../start_server.py"

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
@REM copy ..\models\请将语音和标点模型放到此文件夹 .\dist\start_server\models\
xcopy /S /Y ..\models .\dist\start_server\models 

:: core_server.py
copy ..\core_server.py .\dist\start_server\

@REM =====================Client===========================


rmdir /s /q .\dist\start_client

%PythonPath%\Scripts\pyinstaller.exe -i "../assets/icon.ico" -D  "../start_client.py"

copy .\dist\start_client\start_client.exe .\dist\start_server\
copy ..\core_client.py .\dist\start_server\

@REM =====================About===========================

mkdir  .\dist\start_server\assets
xcopy /S /Y ..\assets .\dist\start_server\assets 
copy ..\readme.md .\dist\start_server\



@REM %PythonPath%\Scripts\pyinstaller.exe -F  "../init_client.py"

::pyinstaller --hidden-import sqlite3 --hidden-import PySide2.QtSql   --noconfirm   -i "../src/misc/icon.ico" "../src/__init__.py"

@REM echo d | xcopy /y /s .\dist\rely .\dist\__init__

@REM ren .\dist\__init__\__init__.exe  "_CapsWriter语音输入工具.exe"

@REM move .\dist\__init__ .\dist\CapsWriter

@REM del /F /Q CapsWriter_Win64.7z

@REM 7z a -t7z CapsWriter_Win64.7z .\dist\CapsWriter -mx=9 -ms=200m -mf -mhc -mhcf  -mmt -r

pause