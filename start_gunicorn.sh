#!/bin/bash

# Change to project directory
cd /home/height-api/htdocs/api.height.fit/public

# Activate virtual environment
source venv/bin/activate

# Start Gunicorn
exec gunicorn --workers 3 --bind 0.0.0.0:8000 apibackend.wsgi:application

