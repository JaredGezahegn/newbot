#!/bin/bash
# build.sh
mkdir -p staticfiles
echo "Static files directory created"
# Run database migrations on every deploy
python manage.py migrate --noinput
echo "Migrations applied"
