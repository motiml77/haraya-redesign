"""חיפוש טקסט חכם במסמכי Word ו-PDF בעברית."""

import os

__version__ = "1.0.0"

APP_NAME = "חיפוש במסמכים"          # השם שמוצג למשתמש
APP_ID = "HebDocSearch"              # שם הקובץ / ההתקנה


def asset(name: str) -> str:
    """נתיב לקובץ משאב (לוגו) – עובד גם מתוך התוכנה הארוזה."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", name)
