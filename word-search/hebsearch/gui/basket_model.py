"""מודל העץ של תוכן הסל.

עץ מקונן: תיקיות הסל ← תתי־תיקיות (לכל עומק) ← מסמכים, עם ספירת מסמכים בכל תיקייה
(למשל 3/5 = 3 מתוך 5 נכללים בחיפוש). המודל וירטואלי: הוא נבנה פעם אחת לכל סריקה והווידג'ט
מצייר רק את מה שנראה, ולכן גם סל של עשרות אלפי מסמכים נפתח מיד ולא נבנה מחדש בכל חיפוש.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor

from ..basket import CHECKED, PARTIAL
from .icons import file_icon, folder_icon
from .results import bidi_name, doc_name
from .theme import C

KIND_ROLE = Qt.UserRole + 1
PATH_ROLE = Qt.UserRole

_FILE_KINDS = ("file", "single")


class Node:
    __slots__ = ("name", "path", "key", "kind", "parent", "kids", "vkids", "vrow", "total", "scanned")

    def __init__(self, name, path, kind, parent=None):
        self.name, self.path, self.kind, self.parent = name, path, kind, parent
        self.key = os.path.normcase(path) if path else ""
        self.kids = []
        self.vkids = self.kids
        self.vrow = 0
        self.total = 1 if kind in _FILE_KINDS else 0
        self.scanned = True


class BasketModel(QAbstractItemModel):
    toggled = Signal(str, bool, bool)         # נתיב, תיקייה?, כלול?

    def __init__(self, editor, status_fn, parent=None):
        """status_fn(path) -> (מצב, הודעה, מזהה) או None אם עדיין לא נקרא."""
        super().__init__(parent)
        self.editor = editor
        self.status_fn = status_fn
        self.root = Node("", "", "root")
        self.by_key = {}
        self._tops = []
        self._filter = ""

    # ---------------------------------------------------------------- בנייה
    def load(self, items, entries):
        """items: [(נתיב, סוג)] מה-DB; entries: [(נתיב, סוג, [מסמכים])] מהסריקה."""
        self.beginResetModel()
        self.root = Node("", "", "root")
        self.by_key = {}
        files_of = {path: files for path, _kind, files in entries}
        for path, kind in items:
            if kind == "exclude":
                continue
            if kind == "folder":
                top = Node(os.path.basename(path.rstrip("\\/")) or path, path, "top", self.root)
                files = files_of.get(path)
                top.scanned = files is not None
                self.root.kids.append(top)
                self.by_key[top.key] = top
                if files:
                    self._build(top, files)
            else:
                n = Node(doc_name(path), path, "single", self.root)
                self.root.kids.append(n)
                self.by_key[n.key] = n
        self._finish(self.root)
        self._recompute_exclusions()
        self.apply_filter(self._filter, reset=False)
        self.endResetModel()

    def _build(self, top, files):
        dirs = {top.key: top}

        def ensure(dpath):
            key = os.path.normcase(dpath)
            node = dirs.get(key)
            if node is not None:
                return node
            parent_path = os.path.dirname(dpath)
            if parent_path == dpath or len(key) <= len(top.key):
                return top
            parent = ensure(parent_path)
            node = Node(os.path.basename(dpath), dpath, "dir", parent)
            parent.kids.append(node)
            dirs[key] = node
            self.by_key[key] = node
            return node

        for f in files:
            d = ensure(os.path.dirname(f))
            n = Node(doc_name(f), f, "file", d)
            d.kids.append(n)
            self.by_key[n.key] = n

    def _finish(self, node):
        """מיון (תיקיות לפני מסמכים), מספור שורות וספירת מסמכים."""
        if node.kind in _FILE_KINDS:
            return 1
        node.kids.sort(key=lambda n: (n.kind in _FILE_KINDS, n.name.casefold()))
        total = 0
        for i, k in enumerate(node.kids):
            k.vrow = i
            total += self._finish(k)
        node.vkids = node.kids
        node.total = total
        return total

    def _recompute_exclusions(self):
        nodes = [self.by_key[k] for k in self.editor.excluded if k in self.by_key]
        sep = os.sep
        self._tops = [n for n in nodes
                      if not any(m is not n and n.key.startswith(m.key + sep) for m in nodes)]

    def refresh(self):
        """אחרי שינוי סימון/החרגה: מעדכן את התצוגה (בלי לבנות מחדש)."""
        self._recompute_exclusions()
        self.layoutAboutToBeChanged.emit()
        self.layoutChanged.emit()

    # ---------------------------------------------------------------- סינון
    def apply_filter(self, text: str, reset: bool = True):
        text = (text or "").strip().casefold()
        if reset:
            self.beginResetModel()
        self._filter = text
        self._mark(self.root, text, False)
        if reset:
            self.endResetModel()

    def _mark(self, node, text, ancestor_match):
        if not text:
            node.vkids = node.kids
            for i, k in enumerate(node.kids):
                k.vrow = i
                if k.kids:
                    self._mark(k, text, False)
            return True
        own = text in node.name.casefold()
        show_all = own or ancestor_match
        if node.kind in _FILE_KINDS:
            return show_all
        visible = []
        for k in node.kids:
            if self._mark(k, text, show_all):
                k.vrow = len(visible)
                visible.append(k)
        node.vkids = visible
        return own or bool(visible) or ancestor_match

    # ---------------------------------------------------------------- מצב ספירה
    def _covered(self, node) -> bool:
        sep = os.sep
        return any(node.key == t.key or node.key.startswith(t.key + sep) for t in self._tops)

    def included_count(self, node) -> int:
        if node.kind in _FILE_KINDS:
            return 1 if self.editor.is_included(node.path) else 0
        if self._covered(node):
            return 0
        sep = os.sep
        return node.total - sum(t.total for t in self._tops if t.key.startswith(node.key + sep))

    def expanded_keys(self, view) -> set:
        """נתיבי התיקיות שפתוחות כרגע בעץ (לשחזור אחרי בנייה מחדש)."""
        out = set()

        def walk(parent_index):
            for r in range(self.rowCount(parent_index)):
                idx = self.index(r, 0, parent_index)
                if view.isExpanded(idx):
                    out.add(idx.internalPointer().key)
                    walk(idx)

        walk(QModelIndex())
        return out

    def restore_expanded(self, view, keys: set, default_open_tops: bool):
        def walk(parent_index):
            for r in range(self.rowCount(parent_index)):
                idx = self.index(r, 0, parent_index)
                node = idx.internalPointer()
                if node.kids and (node.key in keys or (default_open_tops and node.kind == "top")):
                    view.expand(idx)
                    walk(idx)

        walk(QModelIndex())

    # ---------------------------------------------------------------- QAbstractItemModel
    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        pnode = parent.internalPointer() if parent.isValid() else self.root
        kids = pnode.vkids
        if 0 <= row < len(kids):
            return self.createIndex(row, column, kids[row])
        return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        p = index.internalPointer().parent
        if p is None or p is self.root:
            return QModelIndex()
        return self.createIndex(p.vrow, 0, p)

    def rowCount(self, parent=QModelIndex()):
        if parent.column() > 0:
            return 0
        node = parent.internalPointer() if parent.isValid() else self.root
        return len(node.vkids)

    def columnCount(self, parent=QModelIndex()):
        return 2

    def flags(self, index):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.isValid() and index.column() == 0 and index.internalPointer().kind in ("dir", "file"):
            f |= Qt.ItemIsUserCheckable
        return f

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node = index.internalPointer()
        col = index.column()
        if col == 0:
            if role == Qt.DisplayRole:
                return bidi_name(node.name)
            if role == Qt.DecorationRole:
                return folder_icon() if node.kind in ("top", "dir") else file_icon(node.path)
            if role == Qt.CheckStateRole and node.kind in ("dir", "file"):
                if node.kind == "file":
                    return Qt.Checked if self.editor.is_included(node.path) else Qt.Unchecked
                st = self.editor.state(node.path, True)
                return Qt.Checked if st == CHECKED else Qt.PartiallyChecked if st == PARTIAL else Qt.Unchecked
            if role == Qt.ForegroundRole and node.kind in ("dir", "file") and self.included_count(node) == 0:
                return QBrush(QColor(C.muted))
            if role == Qt.ToolTipRole:
                return "‪" + node.path + "‬"
            if role == PATH_ROLE:
                return node.path
            if role == KIND_ROLE:
                return node.kind
            return None
        # עמודת המצב
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter)
        if node.kind in ("top", "dir"):
            if role == Qt.DisplayRole:
                if node.kind == "top" and not node.scanned:
                    return "סורק…"
                inc = self.included_count(node)
                return f"{node.total:,}" if inc == node.total else f"{inc:,}/{node.total:,}"
            if role == Qt.ForegroundRole:
                return QBrush(QColor(C.muted))
            if role == Qt.ToolTipRole:
                return f"{self.included_count(node):,} מתוך {node.total:,} מסמכים נכללים בחיפוש"
            return None
        included = self.editor.is_included(node.path) if node.kind == "file" else True
        status = self.status_fn(node.path)
        if not included:
            text, color, tip = "מוחרג", C.muted, "המסמך לא נכלל בחיפוש"
        elif status is None:
            text, color, tip = "…", C.muted, "ממתין לקריאה"
        elif status[0] == "ok":
            text, color, tip = "✓", C.ok, "נקרא ונכלל במפת החיפוש"
        else:
            text, color, tip = "⚠", C.warn, status[1] or "לא נקרא"
        if role == Qt.DisplayRole:
            return text
        if role == Qt.ForegroundRole:
            return QBrush(QColor(color))
        if role == Qt.ToolTipRole:
            return tip
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.CheckStateRole and index.isValid() and index.column() == 0:
            node = index.internalPointer()
            checked = value in (Qt.Checked, 2) or getattr(value, "value", None) == 2
            self.toggled.emit(node.path, node.kind == "dir", bool(checked))
            return True
        return False

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ("מסמך", "מצב")[section]
        return None

    # ---------------------------------------------------------------- עזרים
    def node_at(self, index):
        return index.internalPointer() if index.isValid() else None
