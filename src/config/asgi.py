"""
ASGI config for Easy Access Platform.

This is the entry point for async web servers like Daphne, Uvicorn, or Hypercorn.
For production deployment with async features (WebSockets, async views), use an ASGI server.
"""

import os

import django
from django.core.asgi import get_asgi_application

# Set the default settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Setup Django
# This must be done before importing anything else that might use Django models
django.setup()

# Export the ASGI application
application = get_asgi_application()
