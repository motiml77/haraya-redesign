"""עריכת סל לפי סימון ✓ על קובץ או תיקייה (מעיון במחשב או מתוכן הסל).

הסל שמור כרשימת פריטים: תיקיות (כולל כל תתי-התיקיות), מסמכים בודדים,
והחרגות – מסמך או תת-תיקייה שבתוך תיקייה שבסל ואינם נכללים בחיפוש.
כאן מחושב מצב הסימון של כל נתיב, ומתורגם סימון/ביטול לשינוי ברשימה.
"""

import os

from .index import _key

CHECKED, PARTIAL, UNCHECKED = "checked", "partial", "unchecked"


def _under(key, parent_key):
    return key.startswith(parent_key.rstrip("\\/") + os.sep)


class BasketEditor:
    def __init__(self, db, basket_id):
        self.db, self.basket_id = db, basket_id
        self.reload()

    def reload(self):
        items = self.db.basket_items(self.basket_id) if self.basket_id is not None else []
        self.folders = {_key(p): p for p, k in items if k == "folder"}
        self.files = {_key(p): p for p, k in items if k == "file"}
        self.excluded = {_key(p): p for p, k in items if k == "exclude"}

    # ---------- מצב ----------
    def covering_folder(self, key):
        """תיקיית הסל הקרובה ביותר שמכילה את הנתיב (או None)."""
        best = None
        for f in self.folders:
            if _under(key, f) and (best is None or len(f) > len(best)):
                best = f
        return best

    def _excluded_below(self, key, root):
        k = key
        while k != root:
            if k in self.excluded:
                return True
            parent = os.path.dirname(k)
            if parent == k:
                return False
            k = parent
        return False

    def is_included(self, path) -> bool:
        key = _key(path)
        if key in self.files or key in self.folders:
            return True
        root = self.covering_folder(key)
        return root is not None and not self._excluded_below(key, root)

    def state(self, path, is_dir) -> str:
        key = _key(path)
        if self.is_included(path):
            if is_dir and any(_under(x, key) for x in self.excluded):
                return PARTIAL
            return CHECKED
        if is_dir and any(_under(x, key) for x in list(self.folders) + list(self.files)):
            return PARTIAL
        return UNCHECKED

    # ---------- שינוי ----------
    def set_checked(self, path, is_dir, checked):
        path = os.path.abspath(path)
        key = _key(path)
        bid = self.basket_id
        if checked:
            root = self.covering_folder(key)
            if root is not None and key in self.excluded:
                self.db.set_excluded(bid, path, False)
            else:
                if is_dir:  # תיקייה חדשה מכסה פריטים שנבחרו בתוכה
                    inner = [p for k, p in list(self.folders.items()) + list(self.files.items()) if _under(k, key)]
                    if inner:
                        self.db.remove_basket_items(bid, inner)
                    self.db.set_excluded(bid, path, False)
                self.db.add_basket_items(bid, [(path, "folder" if is_dir else "file")])
        else:
            if key in self.folders or key in self.files:
                self.db.remove_basket_items(bid, [self.folders.get(key) or self.files[key]])
                self.reload()
            if self.covering_folder(key) is not None and self.is_included(path):
                self.db.set_excluded(bid, path, True)
            elif is_dir:
                inner = [p for k, p in list(self.folders.items()) + list(self.files.items()) if _under(k, key)]
                if inner:
                    self.db.remove_basket_items(bid, inner)
        self.reload()
