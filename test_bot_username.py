#!/usr/bin/env python
"""Quick test to check BOT_USERNAME setting"""
import os
from dotenv import load_dotenv

load_dotenv()

print(f"BOT_USERNAME from env: {os.environ.get('BOT_USERNAME', 'NOT SET')}")
print(f"Expected: DDUVent_bot")
