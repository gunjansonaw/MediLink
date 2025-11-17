#!/usr/bin/env python
import os
import sys
import subprocess
import time

os.chdir(r'd:\medilink\backend')
proc = subprocess.Popen([sys.executable, 'manage.py', 'runserver', '0.0.0.0:8000'], 
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Give it time to start
time.sleep(3)

# Check if it's running
import requests
try:
    response = requests.get('http://127.0.0.1:8000/api/users/login/', json={})
    print("✓ Server is running")
except:
    print("✗ Server failed to start")
    
# Keep the process alive
proc.wait()
