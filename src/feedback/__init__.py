"""
Feedback and learning modules.

This module contains components for collecting analyst feedback,
logging interactions, and supporting continuous learning from feedback.
"""

from .feedback_logger import FeedbackLogger, FeedbackEntry, FeedbackLabel

__all__ = ["FeedbackLogger", "FeedbackEntry", "FeedbackLabel"]

