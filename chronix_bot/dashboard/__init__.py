"""Chronix Dashboard package.

This module provides a small FastAPI-based dashboard skeleton used for Phase 18.
The full dashboard will be developed iteratively; this file simply marks the
package and exposes helpers for app discovery.
"""

from .app import create_app

__all__ = ("create_app",)
