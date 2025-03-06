#!/bin/bash

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies
pip install -r requirements.txt

# Khởi động ứng dụng với Gunicorn
gunicorn main:app -c gunicorn.conf.py 