#!/bin/bash

# 首先判断是否安装了tmux
if ! command -v tmux &> /dev/null; then
    echo "tmux is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install tmux -y
else
    echo "tmux is already installed."
fi

# 使用tmux实现命令行的左右分屏 (左边是 start_server, 右边是 start_client)

# 清除旧 tmux 的会话和面板
tmux kill-server

sleep 2

# 启动 tmux 会话，并创建左右分屏
tmux new-session -d -s mysession
tmux split-window -h

# 在左侧面板中执行 start_server 命令
tmux send-keys -t mysession:0.0 './start_server' Enter

# 切换到右侧面板
tmux select-pane -t mysession:0.1

# 在右侧面板中执行 start_client 命令 (your_password替换为sudo密码, 会自动输入, 而且不会保存在bash_history)
tmux send-keys -t mysession:0.1 'export HISTIGNORE="*sudo -S*"; echo "your_password" | sudo -S ./start_client' Enter

# 切换到左侧面板（可选）
# tmux select-pane -t mysession:0.0

# 进入 tmux 会话
tmux attach-session -t mysession