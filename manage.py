#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys

from environs import Env

env = Env()
env.read_env()


def main():
    """Run administrative tasks."""
    is_debug = env.bool("DEBUG", default=True)

    if is_debug:
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE", "next_refuels.settings.dev"
        )
    else:
        os.environ.setdefault(
            "DJANGO_SETTINGS_MODULE", "next_refuels.settings.prod"
        )

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Ensure it's installed and "
            "your virtual environment is activated."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
