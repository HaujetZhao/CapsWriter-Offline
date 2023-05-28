# coding: utf-8

import subprocess
import shlex
from os.path import dirname; BASE_DIR = dirname(__file__)

import colorama; colorama.init()

port = 6008

command = f'''
./sherpa-onnx-bin/sherpa-onnx-offline-websocket-server 
  --port={port} 
  --num-work-threads=3 
  --num-io-threads=2 
  --tokens=./paraformer-offline-zh/tokens.txt 
  --paraformer=./paraformer-offline-zh/model.onnx 
  --log-file=./log.txt 
  --max-batch-size=5 
'''

print(f'\x9b32m服务端运行端口：{port}\x9b0m\n')
subprocess.run(shlex.split(command), cwd=BASE_DIR)
