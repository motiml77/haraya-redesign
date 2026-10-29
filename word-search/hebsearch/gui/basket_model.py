"""מודל העץ של הסלים: כל הסלים ברשימה אחת.

    ☑ שיעורים                1,240     ← סל: הסימון קובע אם מחפשים בו
        📁 שיעורי הרב          820     ← מה שהוספתם לסל (תיקיות ומסמכים)
            📁 תת־תיקייה   3 מתוך 5     ← ביטול סימון = החרגה מהחיפוש
            📄 מסמך
        ＋ הוספה לסל…

המודל וירטואלי: נבנה פעם אחת לכל סריקה והעץ מצייר רק את מה שנראה, ולכן גם סלים של
עשרות אלפי מסמכים נפתחים מיד ולא נבנים מחדש בכל חיפוש.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont

from ..basket import CHECKED, PARTIAL, BasketEditor
from .icons import file_icon, folder_icon, ui_icon
from .results import bidi_name, doc_name
from .theme import C

PATH_ROLE = Qt.UserRole
KIND_ROLE = Qt.UserRole + 1

_FILE_KINDS = ("file", "single")
_FOLDER_KINDS = ("top", "dir")


class Node:
    __slots__ = ("name", "path", "key", "kind", "parent", "kids", "vkids", "vrow", "total", "scanned", "bid")

    def __init__(self, name, path, kind, parent=None, bid=None):
        self.name, self.path, self.kind, self.parent, self.bid = name, path, kind, parent, bid
        self.key = os.path.normcase(path) if path else ""
        self.kids = []
        self.vkids = self.kids
        self.vrow = 0
        self.total = 1 if kind in _FILE_KINDS else 0
        self.scanned = True


class BasketModel(QAbstractItemModel):
    toggled = Signal(int, str, bool, bool)       # סל, נתיב, תיקייה?, כלול?
    searchToggled = Signal(int, bool)            # סל, מחפשים בו?

    def __init__(self, db, status_fn, parent=None):
        """status_fn(path) -> (מצב, הודעה, מזהה) או None אם עדיין לא נקרא."""
        super().__init__(parent)
        self.db = db
        self.status_fn = status_fn
        self.root = Node("", "", "root")
        self.editors = {}
        self.search_ids = set()
        self.files_of = {}                         # סל → המסמכים שנכללים (מהסריקה) או None
        self._tops = {}
        self._filter = ""

    # ---------------------------------------------------------------- בנייה
    def load(self, baskets, items_of, entries_of, files_of):
        """baskets: [(מזהה, שם, מספר)]; items_of[סל]: [(נתיב, סוג)];
        entries_of[סל]: [(נתיב, סוג, [מסמכים])] מהסריקה; files_of[סל]: המסמכים הנכללים (או None)."""
        self.beginResetModel()
        self.root = Node("", "", "root")
        self.files_of = files_of
        for bid, name, _count in baskets:
            editor = self.editors.get(bid)
            if editor is None:
                editor = self.editors[bid] = BasketEditor(self.db, bid)
            else:
                editor.reload()
            b = Node(name, "", "basket", self.root, bid)
            b.key = f"#basket{bid}"
            self.root.kids.append(b)
            found = {path: files for path, _kind, files in entries_of.get(bid, [])}
            for path, kind in items_of.get(bid, []):
                if kind == "exclude":
                    continue
                if kind == "folder":
                    top = Node(os.path.basename(path.rstrip("\\/")) or path, path, "top", b, bid)
                    files = found.get(path)
                    top.scanned = files is not None
                    b.kids.append(top)
                    if files:
                        self._build(top, files)
                else:
                    b.kids.append(Node(doc_name(path), path, "single", b, bid))
            self._finish(b)
            b.kids.append(Node("הוספה לסל…", "", "add", b, bid))
            for i, k in enumerate(b.kids):
                k.vrow = i
        for i, b in enumerate(self.root.kids):
            b.vrow = i
        for bid in list(self.editors):
            if bid not in {b[0] for b in baskets}:
                del self.editors[bid]
        self._recompute_exclusions()
        self.apply_filter(self._filter, reset=False)
        self.endResetModel()

    def _build(self, top, files):
        dirs = {top.key: top}
        bid = top.bid

        def ensure(dpath):
            key = os.path.normcase(dpath)
            node = dirs.get(key)
            if node is not None:
                return node
            parent_path = os.path.dirname(dpath)
            if parent_path == dpath or len(key) <= len(top.key):
                return top
            parent = ensure(parent_path)
            node = Node(os.path.basename(dpath), dpath, "dir", parent, bid)
            parent.kids.append(node)
            dirs[key] = node
            return node

        for f in files:
            d = ensure(os.path.dirname(f))
            d.kids.append(Node(doc_name(f), f, "file", d, bid))

    def _finish(self, node):
        """מיון (תיקיות לפני מסמכים), מספור שורות וספירת מסמכים."""
        if node.kind in _FILE_KINDS:
            return 1
        if node.kind != "basket":
            node.kids.sort(key=lambda n: (n.kind in _FILE_KINDS, n.name.casefold()))
        total = 0
        for i, k in enumerate(node.kids):
            k.vrow = i
            total += self._finish(k) if k.kind != "add" else 0
        node.vkids = node.kids
        node.total = total
        return total

    def _recompute_exclusions(self):
        """לכל סל: התיקיות/המסמכים המוחרגים העליונים (לספירת "3 מתוך 5")."""
        self._tops = {}
        sep = os.sep
        for b in self.root.kids:
            by_key = {}
            self._index(b, by_key)
            nodes = [by_key[k] for k in self.editors[b.bid].excluded if k in by_key]
            self._tops[b.bid] = [n for n in nodes
                                 if not any(m is not n and n.key.startswith(m.key + sep) for m in nodes)]

    def _index(self, node, out):
        for k in node.kids:
            if k.key and k.kind != "basket":
                out[k.key] = k
            if k.kids:
                self._index(k, out)

    def refresh(self):
        """אחרי שינוי סימון/החרגה: מעדכן את התצוגה (בלי לבנות מחדש)."""
        for e in self.editors.values():
            e.reload()
        self._recompute_exclusions()
        self.layoutAboutToBeChanged.emit()
        self.layoutChanged.emit()

    def set_search_ids(self, ids):
        self.search_ids = set(ids)
        if self.root.kids:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.root.vkids) - 1, 1))

    # ---------------------------------------------------------------- סינון
    def apply_filter(self, text: str, reset: bool = True):
        text = (text or "").strip().casefold()
        if reset:
            self.beginResetModel()
        self._filter = text
        for b in self.root.kids:
            self._mark(b, text, False)
        self.root.vkids = self.root.kids
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
        own = node.kind not in ("basket", "add") and text in node.name.casefold()
        show_all = own or ancestor_match
        if node.kind in _FILE_KINDS:
            return show_all
        if node.kind == "add":
            return False
        visible = []
        for k in node.kids:
            if self._mark(k, text, show_all):
                k.vrow = len(visible)
                visible.append(k)
        node.vkids = visible
        return node.kind == "basket" or own or bool(visible) or ancestor_match

    # ---------------------------------------------------------------- ספירה
    def editor(self, node) -> BasketEditor:
        return self.editors[node.bid]

    def _covered(self, node) -> bool:
        sep = os.sep
        return any(node.key == t.key or node.key.startswith(t.key + sep) for t in self._tops.get(node.bid, ()))

    def included_count(self, node) -> int:
        if node.kind == "basket":
            files = self.files_of.get(node.bid)
            if files is not None:
                return len(files)
            return sum(self.included_count(k) for k in node.kids if k.kind in ("top", "single"))
        if node.kind == "add":
            return 0
        if node.kind in _FILE_KINDS:
            return 1 if self.editor(node).is_included(node.path) else 0
        if self._covered(node):
            return 0
        sep = os.sep
        return node.total - sum(t.total for t in self._tops.get(node.bid, ()) if t.key.startswith(node.key + sep))

    def problems(self, node) -> int:
        """מסמכים בסל שלא נקראו (לסימן ⚠ ליד הסל)."""
        files = self.files_of.get(node.bid) or []
        bad = 0
        for f in files:
            st = self.status_fn(f)
            if st is not None and st[0] != "ok":
                bad += 1
        return bad

    def has_items(self, bid=None) -> bool:
        return any(k.kind in ("top", "single") for b in self.root.kids if bid is None or b.bid == bid for k in b.kids)

    # ---------------------------------------------------------------- מצב פתיחה
    def expanded_keys(self, view) -> set:
        out = set()

        def walk(parent_index):
            for r in range(self.rowCount(parent_index)):
                idx = self.index(r, 0, parent_index)
                if view.isExpanded(idx):
                    node = idx.internalPointer()
                    out.add(node.key)
                    walk(idx)

        walk(QModelIndex())
        return out

    def restore_expanded(self, view, keys, default_open=True):
        """keys=None (פעם ראשונה): הסלים פתוחים, וגם התיקיות בהם אם הסל קטן."""
        def walk(parent_index, depth):
            for r in range(self.rowCount(parent_index)):
                idx = self.index(r, 0, parent_index)
                node = idx.internalPointer()
                if not node.kids:
                    continue
                if keys is None:
                    want = node.kind == "basket" or (default_open and depth == 1 and node.total <= 80)
                else:
                    want = node.key in keys
                if want:
                    view.expand(idx)
                    walk(idx, depth + 1)

        walk(QModelIndex(), 0)

    def basket_index(self, bid) -> QModelIndex:
        for b in self.root.vkids:
            if b.bid == bid:
                return self.createIndex(b.vrow, 0, b)
        return QModelIndex()

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
        if not index.isValid():
            return Qt.NoItemFlags
        node = index.internalPointer()
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == 0 and node.kind in ("basket", "dir", "file"):
            f |= Qt.ItemIsUserCheckable
        if node.kind in ("basket", "top", "dir", "add"):
            f |= Qt.ItemIsDropEnabled
        return f

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node = index.internalPointer()
        kind = node.kind
        if index.column() == 0:
            return self._data_name(node, kind, role)
        return self._data_count(node, kind, role)

    def _data_name(self, node, kind, role):
        if role == Qt.DisplayRole:
            return node.name if kind in ("basket", "add") else bidi_name(node.name)
        if role == Qt.DecorationRole:
            if kind == "basket":
                return ui_icon("folder", C.accent, C.accent)
            if kind == "add":
                return ui_icon("plus", C.accent, C.accent)
            return folder_icon() if kind in _FOLDER_KINDS else file_icon(node.path)
        if role == Qt.CheckStateRole:
            if kind == "basket":
                return Qt.Checked if node.bid in self.search_ids else Qt.Unchecked
            if kind == "file":
                return Qt.Checked if self.editor(node).is_included(node.path) else Qt.Unchecked
            if kind == "dir":
                st = self.editor(node).state(node.path, True)
                return Qt.Checked if st == CHECKED else Qt.PartiallyChecked if st == PARTIAL else Qt.Unchecked
            return None
        if role == Qt.FontRole and kind == "basket":
            f = QFont()
            f.setBold(True)
            return f
        if role == Qt.ForegroundRole:
            if kind == "add":
                return QBrush(QColor(C.accent))
            if kind == "basket" and node.bid not in self.search_ids:
                return QBrush(QColor(C.text2))
            if kind in ("dir", "file") and self.included_count(node) == 0:
                return QBrush(QColor(C.muted))
            return None
        if role == Qt.ToolTipRole:
            if kind == "basket":
                return ("מחפשים בסל הזה – ביטול הסימון מוציא אותו מהחיפוש" if node.bid in self.search_ids
                        else "הסל לא נכלל בחיפוש – סמנו כדי לחפש בו") + "\nלחיצה כפולה: חיפוש רק בסל הזה"
            if kind == "add":
                return "פותח את עץ המחשב לבחירת תיקיות ומסמכים (אפשר גם לגרור לכאן מהסייר)"
            if kind == "top":
                return "‪" + node.path + "‬\nתיקייה שהוספתם לסל (כולל כל תתי־התיקיות)"
            return "‪" + node.path + "‬"
        if role == PATH_ROLE:
            return node.path
        if role == KIND_ROLE:
            return kind
        return None

    def _data_count(self, node, kind, role):
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignVCenter | Qt.AlignLeft)
        if kind == "add":
            return None
        if kind == "basket":
            if role == Qt.DisplayRole:
                if self.files_of.get(node.bid) is None and self.has_items(node.bid):
                    return "סורק…"
                n = self.included_count(node)
                bad = self.problems(node)
                return f"{n:,}" + (f"  ⚠ {bad:,}" if bad else "")
            if role == Qt.ForegroundRole:
                return QBrush(QColor(C.warn if self.problems(node) else C.muted))
            if role == Qt.ToolTipRole:
                bad = self.problems(node)
                text = f"{self.included_count(node):,} מסמכים בחיפוש"
                return text + (f"\n{bad:,} מסמכים לא נקראו (לחיצה ימנית ← מסמכים שלא נקראו)" if bad else "")
            return None
        if kind in _FOLDER_KINDS:
            if role == Qt.DisplayRole:
                if kind == "top" and not node.scanned:
                    return "סורק…"
                inc = self.included_count(node)
                return f"{node.total:,}" if inc == node.total else f"{inc:,} מתוך {node.total:,}"
            if role == Qt.ForegroundRole:
                return QBrush(QColor(C.muted))
            if role == Qt.ToolTipRole:
                return f"{self.included_count(node):,} מתוך {node.total:,} מסמכים נכללים בחיפוש"
            return None
        included = self.editor(node).is_included(node.path) if kind == "file" else True
        status = self.status_fn(node.path)
        if not included:
            text, color, tip = "מוחרג", C.muted, "המסמך לא נכלל בחיפוש"
        elif status is None:
            text, color, tip = "…", C.muted, "ממתין לקריאה"
        elif status[0] == "ok":
            text, color, tip = "", C.ok, "נקרא ונכלל בחיפוש"
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
            if node.kind == "basket":
                self.searchToggled.emit(node.bid, bool(checked))
            else:
                self.toggled.emit(node.bid, node.path, node.kind == "dir", bool(checked))
            return True
        return False

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ("סל / מסמך", "מסמכים")[section]
        return None

    def node_at(self, index):
        return index.internalPointer() if index.isValid() else None
