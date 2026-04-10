"""Scheduled tasks package."""

from .get_hot_news import run_get_hot_news
from .get_latest_news import run_get_latest_news

__all__ = ["run_get_latest_news", "run_get_hot_news"]

