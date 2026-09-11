#!/usr/bin/env bash

ROOT="$(pwd)"

tmux new-window -n exec_r -c "$ROOT"
tmux send-keys -t exec_r 'venv/bin/python run.py' C-m
tmux new-window -n code -c "$ROOT/app"
tmux send-keys -t code 'nvim' C-m
tmux new-window -n bash
tmux new-window -n psql
tmux send-keys -t psql 'psql -h 192.168.1.254 -p 8745 -U postgres encomendas' C-m
tmux new-window -n git
