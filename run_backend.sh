#!/bin/bash

cd "$(dirname "$0")/backend" || exit 1

if [ ! -d "env" ]; then
    python3 -m venv env
fi

source env/bin/activate
pip install -r requirements.txt
python run.py
