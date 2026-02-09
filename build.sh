#!/bin/bash
# build.sh
# Ensure staticfiles directory exists for Vercel
mkdir -p staticfiles
echo "Static files directory created"
# Note: Dependencies are installed by Vercel using uv from requirements.txt
# Migrations will run automatically on first request via Django