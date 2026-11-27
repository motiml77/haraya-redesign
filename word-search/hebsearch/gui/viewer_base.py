"""בסיס משותף למציגי המסמכים: סרגל כלים (שם, מיקום, מעבר בין תוצאות, פעולות) ודף המסמך.

גודל החלון: אפשר לגרור את השוליים, או לבחור גודל מוכן מהתפריט שבסרגל (קטן / בינוני / גדול / חצי מסך /
מסך מלא). הגודל והמקום האחרונים נשמרים, והחלון הבא נפתח בדיוק כך."""

from PySide6.QtCore import QPoint, QRect, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton, QVBoxLayout, QWidget

from .icons import file_icon, ui_icon
from .results import doc_name
from .theme import C, T, fit_geometry
from .widgets import ElidedLabel, icon_button, text_icon_button


# גדלים מוכנים: (מזהה, שם, רוחב וגובה כחלק מהשטח הפנוי של המסך)
SIZE_PRESETS = (("small", "קטן", 0.42, 0.66), ("medium", "בינוני", 0.56, 0.86), ("large", "גדול", 0.76, 0.96))
SIZE_HALVES = (("half-right", "חצי מסך – ימין"), ("half-left", "חצי מסך – שמאל"))
GEOMETRY_KEY = "viewer/geometry"


class HitViewer(QMainWindow):
    """חלון שמציג מסמך אחד ועובר בין התוצאות שבו.

        ┌ [סמל] שם המסמך                      ‹ 2 מתוך 8 ›  │  [הצג בתיקייה] [פתח את המסמך המקורי] ┐
        │       עמוד 1 · פסקה 2                                                                  │
        ├──────────────────────────────────────────────────────────────────────────────────┤
        │                       ┌──── דף המסמך (לבן, על רקע אפור) ────┐                      │
    """

    def __init__(self, searcher, highlight, hits, index, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.searcher, self.highlight = searcher, highlight
        self.hits, self.index = hits, index
        self.path = hits[index].path
        self.setWindowTitle(doc_name(self.path))
        self.settings = getattr(parent, "settings", None) or QSettings("HebWordSearch", "app")
        self._geo_timer = QTimer(self)                  # שמירת הגודל רגע אחרי שהמשתמש סיים לגרור
        self._geo_timer.setSingleShot(True)
        self._geo_timer.setInterval(400)
        self._geo_timer.timeout.connect(self._save_geometry)

        central = QWidget()
        central.setObjectName("viewer")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QFrame()
        bar.setObjectName("header")
        head = QHBoxLayout(bar)
        head.setContentsMargins(T.pad + 2, T.gap, T.pad + 2, T.gap)
        head.setSpacing(T.gap)
        icon = QLabel()
        icon.setPixmap(file_icon(self.path).pixmap(QSize(T.icon + 8, T.icon + 8)))
        head.addWidget(icon, 0, Qt.AlignTop)
        names = QVBoxLayout()
        names.setSpacing(0)
        self.title = ElidedLabel("", Qt.ElideMiddle)
        self.title.setObjectName("title")
        self.where = ElidedLabel("", Qt.ElideRight)
        self.where.setObjectName("caption")
        names.addWidget(self.title)
        names.addWidget(self.where)
        head.addLayout(names, 1)

        # מעבר בין התוצאות: ‹ 2 מתוך 8 ›. בממשק מימין לשמאל "הקודמת" היא לכיוון ימין
        nav = QFrame()
        nav.setObjectName("navgroup")
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(0, 0, 0, 0)
        nl.setSpacing(0)
        self.prev_btn = icon_button("chevron-right", "התוצאה הקודמת במסמך (Shift+F3)")
        self.prev_btn.clicked.connect(lambda: self.go(self.index - 1))
        self.next_btn = icon_button("chevron-left", "התוצאה הבאה במסמך (F3)")
        self.next_btn.clicked.connect(lambda: self.go(self.index + 1))
        self.counter = QLabel("")
        self.counter.setObjectName("counter")
        self.counter.setAlignment(Qt.AlignCenter)
        nl.addWidget(self.prev_btn)
        nl.addWidget(self.counter)
        nl.addWidget(self.next_btn)
        head.addWidget(nav, 0, Qt.AlignVCenter)
        sep = QFrame()
        sep.setObjectName("vsep")
        T.sized(sep, h="h_ctl")
        head.addWidget(sep, 0, Qt.AlignVCenter)
        self.actions_bar = QHBoxLayout()
        self.actions_bar.setSpacing(6)
        self.size_btn = text_icon_button("expand", "גודל", "גודל החלון – קטן, בינוני, גדול, חצי מסך או מסך מלא.\n"
                                                           "אפשר גם לגרור את שולי החלון. הגודל נשמר לפעם הבאה")
        self.size_btn.clicked.connect(self._show_size_menu)
        self.actions_bar.addWidget(self.size_btn)
        head.addLayout(self.actions_bar)
        outer.addWidget(bar)

        # הדף: על רקע אפור, כמו תצוגת הדפסה
        page_area = QWidget()
        page_area.setObjectName("pagearea")
        self.layout_ = QVBoxLayout(page_area)
        self.layout_.setContentsMargins(T.pad * 2, T.pad + 4, T.pad * 2, 0)
        self.layout_.setSpacing(0)
        outer.addWidget(page_area, 1)
        self.setCentralWidget(central)
        QShortcut(QKeySequence("F3"), self, lambda: self.go(self.index + 1))
        QShortcut(QKeySequence("Shift+F3"), self, lambda: self.go(self.index - 1))
        QShortcut(QKeySequence("Esc"), self, self.close)

    # ================================================================ גודל החלון
    def _avail(self) -> QRect:
        screen = self.screen() if self.isVisible() else None
        if screen is None:
            parent = self.parent()
            screen = (parent.screen() if parent is not None else None) or QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def fit(self, want_w, want_h):
        """הגודל והמקום שהמשתמש בחר בפעם הקודמת; בפעם הראשונה – גודל התחלתי בתוך המסך, ממורכז."""
        avail = self._avail()
        default = fit_geometry(avail, want_w, want_h, 0.92)
        self.setGeometry(default)
        self.setMinimumSize(min(480, default.width()), min(320, default.height()))
        saved = self.settings.value(GEOMETRY_KEY)
        if saved:
            try:
                ok = self.restoreGeometry(saved)
            except TypeError:
                ok = False
            frame = self.frameGeometry()
            screens = [sc.availableGeometry() for sc in QGuiApplication.screens()] or [avail]
            home = next((r for r in screens if r.intersects(frame)), None)
            # מסך שנותק או רזולוציה שהשתנתה: החלון חייב להיות כולו בתוך מסך קיים
            if not ok or home is None or frame.width() > home.width() + 4 or frame.height() > home.height() + 4:
                self.setWindowState(self.windowState() & ~(Qt.WindowMaximized | Qt.WindowFullScreen))
                self.setGeometry(default)
        if not self.isMaximized():
            self._cascade()

    def _cascade(self):
        """כמה מסמכים פתוחים: החלון החדש לא מסתיר בדיוק את הקודם."""
        taken = []
        for v in getattr(self.parent(), "viewers", []) or []:
            try:
                if v is not self and v.isVisible() and not v.isMaximized():
                    taken.append(v.pos())
            except RuntimeError:                      # חלון שכבר נסגר
                continue
        avail, step, pos = self._avail(), 28, self.pos()
        for _ in range(8):
            if not any(abs(t.x() - pos.x()) < 8 and abs(t.y() - pos.y()) < 8 for t in taken):
                break
            pos = QPoint(pos.x() + step, pos.y() + step)
        if pos != self.pos() and pos.x() + self.width() <= avail.right() + 1 and pos.y() + self.height() <= avail.bottom() + 1:
            self.move(pos)

    def _preset_rect(self, name) -> QRect:
        """המלבן (כולל מסגרת החלון) של גודל מוכן, במסך שבו החלון נמצא."""
        avail = self._avail()
        left, top, right, bottom = self._frame_margins()
        # לא קטן מהגודל המינימלי של החלון (במסך קטן), ולא גדול מהמסך
        min_w = min(avail.width(), self.minimumWidth() + left + right)
        min_h = min(avail.height(), self.minimumHeight() + top + bottom)
        if name == "half-right" or name == "half-left":
            w = max(avail.width() // 2, min_w)
            x = avail.x() + (avail.width() - w if name == "half-right" else 0)
            return QRect(x, avail.y(), w, avail.height())
        fw, fh = next((p[2], p[3]) for p in SIZE_PRESETS if p[0] == name)
        w, h = max(int(avail.width() * fw), min_w), max(int(avail.height() * fh), min_h)
        # נשאר סביב המרכז הנוכחי של החלון, בלי לצאת מהמסך
        c = self.frameGeometry().center() if self.isVisible() and not self.isMaximized() else avail.center()
        x = max(avail.x(), min(c.x() - w // 2, avail.right() + 1 - w))
        y = max(avail.y(), min(c.y() - h // 2, avail.bottom() + 1 - h))
        return QRect(x, y, w, h)

    def _frame_margins(self):
        g, f = self.geometry(), self.frameGeometry()
        return g.x() - f.x(), g.y() - f.y(), f.right() - g.right(), f.bottom() - g.bottom()

    def set_size(self, name):
        """גודל מוכן: small / medium / large / half-right / half-left / full."""
        if name == "full":
            self.showMaximized()
        else:
            if self.isMaximized() or self.isFullScreen():
                self.showNormal()
            rect = self._preset_rect(name)
            left, top, right, bottom = self._frame_margins()
            self.setGeometry(rect.adjusted(left, top, -right, -bottom))
        self._save_geometry()

    def current_size(self):
        """הגודל המוכן שהחלון נמצא בו עכשיו, או "" אם המשתמש קבע גודל משלו."""
        if self.isMaximized():
            return "full"
        frame = self.frameGeometry()
        for name in [p[0] for p in SIZE_PRESETS] + [h[0] for h in SIZE_HALVES]:
            want = self._preset_rect(name)
            if abs(frame.width() - want.width()) <= 6 and abs(frame.height() - want.height()) <= 6 \
                    and (not name.startswith("half") or abs(frame.x() - want.x()) <= 6):
                return name
        return ""

    def _size_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setLayoutDirection(Qt.RightToLeft)
        current = self.current_size()

        def add(name, text):
            act = QAction(text, menu)
            act.setData(name)
            if name == current:                         # הגודל הנוכחי מסומן ב-✓
                act.setIcon(ui_icon("check", C.accent, C.accent))
                font = act.font()
                font.setBold(True)
                act.setFont(font)
            act.triggered.connect(lambda _=False, n=name: self.set_size(n))
            menu.addAction(act)

        for name, text, _w, _h in SIZE_PRESETS:
            add(name, text)
        menu.addSeparator()
        for name, text in SIZE_HALVES:
            add(name, text)
        add("full", "מסך מלא")
        menu.addSeparator()
        note = menu.addAction("הגודל נשמר לפעם הבאה")
        note.setEnabled(False)
        return menu

    def _show_size_menu(self):
        menu = self._size_menu()
        menu.exec(self.size_btn.mapToGlobal(QPoint(0, self.size_btn.height() + 2)))

    def _save_geometry(self):
        self._geo_timer.stop()
        if not self.isMinimized():
            self.settings.setValue(GEOMETRY_KEY, self.saveGeometry())

    def showEvent(self, e):
        # כל הכפתורים שבסרגל תמיד נראים: החלון לא קטן מהרוחב שהם צריכים (עד רוחב המסך)
        avail = self._avail()
        left, _top, right, _bottom = self._frame_margins()
        room = avail.width() - max(16, left + right)           # במסך צר מאוד: החלון כולו, עם המסגרת, בתוך המסך
        self.setMinimumWidth(max(320, min(max(self.minimumWidth(), self.minimumSizeHint().width()), room)))
        super().showEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.isVisible():
            self._geo_timer.start()

    def moveEvent(self, e):
        super().moveEvent(e)
        if self.isVisible():
            self._geo_timer.start()

    def closeEvent(self, e):
        self._save_geometry()
        super().closeEvent(e)

    def add_action(self, text, slot, tip="", kind="", icon=""):
        """kind: "primary" לפעולה הראשית, "ghost" לכפתור שקוף, ריק – כפתור משני."""
        if kind == "ghost" and icon and not text:
            b = icon_button(icon, tip)
        else:
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            if kind:
                b.setObjectName(kind)
            if icon:
                color = "#ffffff" if kind == "primary" else C.text2
                b.setIcon(ui_icon(icon, color, color))
                b.setIconSize(QSize(T.icon, T.icon))
            b.setToolTip(tip)
        b.clicked.connect(slot)
        self.actions_bar.addWidget(b)
        return b

    @property
    def hit(self):
        return self.hits[self.index]

    def go(self, i):
        if not 0 <= i < len(self.hits):
            return
        self.index = i
        hit = self.searcher.materialize(self.hits[i], self.highlight)
        self.title.setFullText(doc_name(self.path))
        self.where.setFullText(hit.location)
        self.counter.setText(f"{i + 1:,} מתוך {len(self.hits):,}")
        self.counter.setToolTip("התוצאה הנוכחית מתוך התוצאות במסמך הזה")
        self.prev_btn.setEnabled(i > 0)
        self.next_btn.setEnabled(i < len(self.hits) - 1)
        self.show_hit(hit)

    def show_hit(self, hit):  # pragma: no cover - ממומש במחלקות היורשות
        raise NotImplementedError

    def navigate(self, hits, hit):
        """מעבר לתוצאה (מחלון התוצאות) בחלון שכבר פתוח."""
        self.hits = hits
        self.go(next(i for i, h in enumerate(hits) if h is hit))
        if self.isMinimized():                          # (בלי לבטל "מסך מלא" שהמשתמש בחר)
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()
