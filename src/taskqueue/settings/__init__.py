"""
Django settings module.
"""

import os

from decouple import config

environment = config("DJANGO_ENV", default="development")

if environment == "production":
    from .production import *  # noqa: F401, F403
else:
    from .development import *  # noqa: F401, F403
