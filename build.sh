#!/bin/bash

# Tạo và kích hoạt môi trường ảo
python -m venv antenv
source antenv/bin/activate

# Nâng cấp pip
python -m pip install --upgrade pip

# Cài đặt các dependencies
pip install -r requirements.txt

# Deactivate virtual environment
deactivate 