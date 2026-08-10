#!/bin/bash

set -e

cd "$(dirname "$0")/backend"

if [ ! -d "env" ]; then
    python3 -m venv env
fi

source env/bin/activate
python -m pip install -r requirements.txt
python run.py
