#!/bin/bash
# build.sh
pip install -r requirements.txt
python3 manage.py migrate --no-input
python3 manage.py collectstatic --no-input
# Ensure staticfiles directory exists for Vercel
mkdir -p staticfiles
echo "Static files directory created"