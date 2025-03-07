#!/bin/bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m wfastcgi-enable
gunicorn --bind=0.0.0.0 --timeout 600 --workers 1 main:app 