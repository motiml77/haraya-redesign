"""סרטון הדרכה: מפעיל את התוכנה האמיתית (בלי חלון), מקליט כל שלב ומרכיב סרטון מעוצב
עם רקע, מסגרת חלון, סמן עכבר, אנימציית לחיצות, הקלדה וכיתוביות.

    python tools/tutorial_video.py OUT.mp4

נדרש ffmpeg בנתיב.
"""

import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

W, H, FPS = 1920, 1080, 30


def main():
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "tutorial.mp4")
    tmp = tempfile.mkdtemp(prefix="hebvideo-")
    os.environ["HEBSEARCH_DATA"] = os.path.join(tmp, "data")

    from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSettings, Qt
    from PySide6.QtGui import (
        QColor, QFont, QImage, QLinearGradient, QPageSize, QPainter, QPainterPath, QPdfWriter, QPen,
        QPolygonF, QRadialGradient, QTextDocument, QTextOption,
    )
    from PySide6.QtWidgets import QApplication, QPushButton

    from docx_builder import build_docx
    from hebsearch import asset
    from hebsearch.gui import main_window as mw
    from hebsearch.paths import default_db_path

    # ------------------------------------------------------------ מסמכי דוגמה
    # תיקיית הדוגמה בתיקיית הבית, כדי שעץ המחשב בסרטון ייראה כמו אצל משתמש (ולא תיקיות זמניות)
    docs = os.path.join(os.path.expanduser("~"), "המסמכים שלי")
    if os.path.exists(docs):
        shutil.rmtree(docs)
    for sub in ("תורה", "הלכה", "ספרים"):
        os.makedirs(os.path.join(docs, sub))
    build_docx(os.path.join(docs, "תורה", "בראשית פרק יב.docx"), [
        "וַיֹּאמֶר יְהוָה אֶל-אַבְרָם, לֶךְ-לְךָ מֵאַרְצְךָ וּמִמּוֹלַדְתְּךָ וּמִבֵּית אָבִיךָ, אֶל-הָאָרֶץ, אֲשֶׁר אַרְאֶךָּ.",
        "וַיֵּלֶךְ אַבְרָם, כַּאֲשֶׁר דִּבֶּר אֵלָיו יְהוָה, וַיֵּלֶךְ אִתּוֹ, לוֹט; וְאַבְרָם, בֶּן-חָמֵשׁ שָׁנִים וְשִׁבְעִים שָׁנָה.",
        "וַיִּסַּע אַבְרָם, הָלוֹךְ וְנָסוֹעַ הַנֶּגְבָּה.",
    ])
    build_docx(os.path.join(docs, "הלכה", "הלכות שבת – סיכום.docx"), [
        "פרק א: מלאכות שבת",
        "ההולך בשבת ברשות הרבים צריך לשמור שלא יוציא דבר מרשות לרשות, ומי שהלך בדרך וחשכה לו נותן כיסו לנכרי.",
        "כתב הרמב\"ם שההליכה בשבת צריכה להיות שונה מהליכת החול, ולכן אין לפסוע פסיעה גסה.",
        "שמירת שבת שקולה כנגד כל המצוות, וכל השומר שבת כהלכתו מוחלין לו על כל עוונותיו.",
        "והלכה כרבי יהודה שאסור להלך יותר מאלפיים אמה חוץ לתחום, ומי שהלכו בהיתר מותר לחזור.",
    ])
    build_docx(os.path.join(docs, "מכתב לחבר.docx"), [
        "שלום וברכה לידידי היקר,",
        "רציתי לספר לך שבשבוע שעבר הלכנו כל המשפחה לטיול בהרי ירושלים, וההליכה בשבילים היתה מרוממת ומלאת שמחה.",
    ])

    app = QApplication(sys.argv[:1])

    doc = QTextDocument()
    doc.setDefaultFont(QFont("DejaVu Sans", 12))
    doc.setHtml('<div dir="rtl"><p>פרק ב: בביאור מידת הזהירות</p><p>ומשל למה הדבר דומה, לעור שהולך על שפת הנהר. '
                'כי ההולך בדרך בלא זהירות הוא כמי שהלך בעיניים עצומות.</p></div>')
    writer = QPdfWriter(os.path.join(docs, "ספרים", "מסילת ישרים – פרק ב.pdf"))
    writer.setPageSize(QPageSize(QPageSize.A5))
    doc.print_(writer)
    del writer

    settings = QSettings(os.path.join(tmp, "settings.ini"), QSettings.IniFormat)
    mw.MainWindow._screen_rect = lambda self: QRect(0, 0, 1366, 728)
    mw.prepare_app(app, settings)
    win = mw.MainWindow(default_db_path(), settings)
    win.show()

    # ------------------------------------------------------------ בימוי
    ACCENT = QColor("#2563eb")
    FONT = "DejaVu Sans"
    logo = QImage(asset("icon-512.png"))

    def font(px, bold=False):
        f = QFont(FONT)
        f.setPixelSize(px)
        f.setBold(bold)
        return f

    background = QImage(W, H, QImage.Format_ARGB32)
    p = QPainter(background)
    g = QLinearGradient(0, 0, W, H)
    g.setColorAt(0, QColor("#0b1430"))
    g.setColorAt(1, QColor("#1b2f6b"))
    p.fillRect(0, 0, W, H, g)
    for cx, cy, r, col in ((1650, 150, 620, QColor(56, 120, 255, 70)), (250, 980, 700, QColor(120, 80, 255, 55))):
        rg = QRadialGradient(cx, cy, r)
        rg.setColorAt(0, col)
        rg.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, W, H, rg)
    p.end()

    class Stage:
        def __init__(self):
            self.ffmpeg = subprocess.Popen(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                 "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
            self.frames = 0
            self.win_img = None
            self.scale = 1.0
            self.origin = QPointF(0, 0)
            self.overlays = []            # (QImage, נקודה בקואורדינטות החלון, קנה מידה)
            self.cursor = QPointF(600, 400)
            self.cursor_visible = True
            self.pressed = 0.0
            self.ripples = []             # (נקודה, מסגרת התחלה)
            self.caption = ("", "", "")   # (מספר, כותרת, הסבר)
            self.caption_since = 0
            self.keycap = None
            self.refresh()

        # ----- תמונת החלון -----
        def refresh(self, settle=3):
            for _ in range(settle):
                app.processEvents()
                time.sleep(0.005)
            img = win.grab().toImage()
            avail_w, avail_h = 1640, 820
            self.scale = min(avail_w / img.width(), (avail_h - 40) / img.height())
            sw, sh = int(img.width() * self.scale), int(img.height() * self.scale)
            self.win_img = img.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.origin = QPointF((W - sw) / 2, 56 + 40)

        def to_canvas(self, pt):
            return QPointF(self.origin.x() + pt.x() * self.scale, self.origin.y() + pt.y() * self.scale)

        # ----- ציור מסגרת -----
        def render(self):
            img = QImage(background)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            sw, sh = self.win_img.width(), self.win_img.height()
            frame = QRectF(self.origin.x(), self.origin.y() - 40, sw, sh + 40)
            # צל
            for i in range(14, 0, -1):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 0, 0, 7))
                p.drawRoundedRect(frame.adjusted(-i * 2, -i * 2 + 10, i * 2, i * 2 + 10), 16 + i, 16 + i)
            path = QPainterPath()
            path.addRoundedRect(frame, 14, 14)
            p.setClipPath(path)
            p.fillRect(frame, QColor("#e9edf4"))
            # שורת כותרת של חלון
            bar = QRectF(frame.x(), frame.y(), frame.width(), 40)
            p.fillRect(bar, QColor("#f8fafc"))
            for k, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
                p.setBrush(QColor(col))
                p.drawEllipse(QPointF(bar.x() + 22 + k * 22, bar.center().y()), 6.5, 6.5)
            p.setPen(QColor("#475569"))
            p.setFont(font(15, True))
            title_opt = QTextOption(Qt.AlignCenter)
            title_opt.setTextDirection(Qt.RightToLeft)
            p.drawText(bar, "\u202bחיפוש במסמכים – Word ו-PDF\u202c", title_opt)
            p.drawImage(self.origin, self.win_img)
            for oimg, pt, sc in self.overlays:
                tl = self.to_canvas(pt)
                tw, th = oimg.width() * self.scale * sc, oimg.height() * self.scale * sc
                r = QRectF(tl.x(), tl.y(), tw, th)
                for i in range(10, 0, -1):
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(0, 0, 0, 10))
                    p.drawRoundedRect(r.adjusted(-i, -i + 6, i, i + 6), 8 + i, 8 + i)
                p.drawImage(r, oimg)
                p.setPen(QPen(QColor("#c8cfdb"), 1))
                p.setBrush(Qt.NoBrush)
                p.drawRect(r)
            p.setClipping(False)
            self._draw_caption(p)
            if self.keycap:
                self._draw_keycap(p, self.keycap)
            for pos, start in list(self.ripples):
                t = (self.frames - start) / (0.55 * FPS)
                if t > 1:
                    self.ripples.remove((pos, start))
                    continue
                c = self.to_canvas(pos)
                col = QColor(ACCENT)
                col.setAlpha(int(200 * (1 - t)))
                p.setPen(QPen(col, 4))
                p.setBrush(QColor(37, 99, 235, int(60 * (1 - t))))
                rad = 10 + 34 * (1 - (1 - t) ** 3)
                p.drawEllipse(c, rad, rad)
            if self.cursor_visible:
                self._draw_cursor(p, self.to_canvas(self.cursor))
            p.end()
            return img

        def _draw_cursor(self, p, c):
            s = 1.35 * (1 - 0.15 * self.pressed)
            pts = [(0, 0), (0, 24), (6, 18.5), (10.5, 28), (14.5, 26.2), (10.2, 17), (18, 17)]
            poly = QPolygonF([QPointF(c.x() + x * s, c.y() + y * s) for x, y in pts])
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 70))
            p.drawPolygon(poly.translated(2, 3))
            p.setPen(QPen(QColor("#0f172a"), 1.6))
            p.setBrush(QColor("#ffffff"))
            p.drawPolygon(poly)

        def _draw_caption(self, p):
            num, title, text = self.caption
            if not title:
                return
            a = min(1.0, (self.frames - self.caption_since) / (0.45 * FPS))
            ease = 1 - (1 - a) ** 3
            box = QRectF(W / 2 - 760, H - 132 + (1 - ease) * 18, 1520, 100)
            p.setOpacity(ease)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 238))
            p.drawRoundedRect(box, 22, 22)
            badge = QRectF(box.right() - 86, box.y() + 22, 56, 56)
            p.setBrush(ACCENT)
            p.drawEllipse(badge)
            p.setPen(QColor("white"))
            p.setFont(font(26, True))
            p.drawText(badge, Qt.AlignCenter, num)
            opt = QTextOption(Qt.AlignRight | Qt.AlignVCenter)
            opt.setTextDirection(Qt.RightToLeft)
            p.setPen(QColor("#0f172a"))
            p.setFont(font(27, True))
            p.drawText(QRectF(box.x() + 30, box.y() + 12, box.width() - 140, 40), title, opt)
            p.setPen(QColor("#475569"))
            p.setFont(font(21))
            p.drawText(QRectF(box.x() + 30, box.y() + 52, box.width() - 140, 36), text, opt)
            p.setOpacity(1)

        def _draw_keycap(self, p, keys):
            x = W / 2 + 120
            y = H - 230
            p.setFont(font(30, True))
            for k in keys:
                w = max(64, p.fontMetrics().horizontalAdvance(k) + 40)
                r = QRectF(x - w, y, w, 64)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 0, 0, 90))
                p.drawRoundedRect(r.translated(0, 5), 12, 12)
                p.setBrush(QColor("#f8fafc"))
                p.setPen(QPen(QColor("#94a3b8"), 2))
                p.drawRoundedRect(r, 12, 12)
                p.setPen(QColor("#0f172a"))
                p.drawText(r, Qt.AlignCenter, k)
                x -= w + 20

        # ----- זמן -----
        def emit(self, img=None):
            img = img or self.render()
            self.ffmpeg.stdin.write(bytes(img.constBits()))
            self.frames += 1
            app.processEvents()

        def hold(self, sec, live=False):
            for _ in range(int(sec * FPS)):
                if live and _ % 3 == 0:
                    self.refresh(settle=1)
                self.emit()

        def move(self, target, sec=0.7):
            start = QPointF(self.cursor)
            n = max(1, int(sec * FPS))
            for i in range(1, n + 1):
                t = i / n
                e = t * t * (3 - 2 * t)
                arc = math.sin(math.pi * t) * 40
                self.cursor = QPointF(start.x() + (target.x() - start.x()) * e,
                                      start.y() + (target.y() - start.y()) * e - arc * 0.4)
                self.emit()

        def click(self, target, action=None, move_sec=0.7, after=0.5):
            self.move(target, move_sec)
            for i in range(4):
                self.pressed = (i + 1) / 4
                self.emit()
            self.ripples.append((QPointF(target), self.frames))
            if action:
                action()
            self.refresh()
            for i in range(4):
                self.pressed = 1 - (i + 1) / 4
                self.emit()
            self.hold(after)

        def type(self, edit, text, per_char=0.09):
            for i in range(1, len(text) + 1):
                edit.setText(text[:i])
                self.refresh(settle=1)
                for _ in range(max(1, int(per_char * FPS))):
                    self.emit()

        def set_caption(self, num, title, text):
            self.caption = (num, title, text)
            self.caption_since = self.frames

        def wait_jobs(self, limit=20):
            t0 = time.time()
            while time.time() - t0 < limit:
                self.refresh(settle=1)
                self.emit()
                if not (win._scan_job or win._search_job or win._search_waiting_scan or win.results.overlay.is_active()):
                    break

        def card(self, title, subtitle, sec=3.6):
            """כרטיס פתיחה/סיום: לוגו, כותרת ותת-כותרת עם כניסה רכה."""
            n = int(sec * FPS)
            for i in range(n):
                t = min(1.0, i / (0.8 * FPS))
                fade_out = min(1.0, (n - i) / (0.5 * FPS))
                e = (1 - (1 - t) ** 3) * fade_out
                img = QImage(background)
                p = QPainter(img)
                p.setRenderHint(QPainter.Antialiasing)
                p.setRenderHint(QPainter.SmoothPixmapTransform)
                p.setOpacity(e)
                size = 220
                p.drawImage(QRectF(W / 2 - size / 2, 250 - (1 - t) * 30, size, size), logo)
                opt = QTextOption(Qt.AlignCenter)
                opt.setTextDirection(Qt.RightToLeft)
                p.setPen(QColor("white"))
                p.setFont(font(84, True))
                p.drawText(QRectF(0, 520 + (1 - t) * 20, W, 110), title, opt)
                p.setPen(QColor("#c7d2fe"))
                p.setFont(font(36))
                p.drawText(QRectF(0, 640 + (1 - t) * 20, W, 60), subtitle, opt)
                p.end()
                self.emit(img)

        def close(self):
            self.ffmpeg.stdin.close()
            self.ffmpeg.wait()

    st = Stage()

    def center_of(widget, dx=0, dy=0):
        c = widget.mapTo(win, widget.rect().center())
        return QPointF(c.x() + dx, c.y() + dy)

    def row_point(view, index, host_origin, host, from_right=0, dx=0):
        """נקודה בשורת עץ (בקואורדינטות החלון). from_right – מרחק מהקצה הימני של השורה (תיבת סימון)."""
        r = view.visualRect(index)
        x = r.right() - from_right if from_right else r.center().x() + dx
        pt = view.viewport().mapTo(host, QPoint(int(x), r.center().y()))
        return QPointF(host_origin.x() + pt.x(), host_origin.y() + pt.y())

    panel = win.baskets
    bid = win.db.baskets()[0][0]

    # ============================================================ פתיחה
    st.card("חיפוש במסמכים", "מדריך קצר · חיפוש מהיר וגמיש בתוך מסמכי Word ו-PDF")
    st.refresh()
    st.cursor = QPointF(560, 360)

    # ============================================================ 1. הוספה לסל
    st.set_caption("1", "מוסיפים תיקייה לסל", "לוחצים על 'בחירה מהמחשב…' ומסמנים ✓ ליד התיקייה – כל תתי-התיקיות נכנסות לסל")
    st.hold(1.4)
    btn = next(b for b in panel.empty_page.findChildren(QPushButton) if b.text().startswith("בחירה מהמחשב"))
    dlg_holder = {}

    def open_dialog():
        dlg = panel.open_browser(bid, modal=False)
        dlg.resize(560, 600)
        dlg.browser.reveal(docs)
        t0 = time.time()
        while time.time() - t0 < 2.5:
            app.processEvents()
            time.sleep(0.01)
        dlg.browser.view.scrollTo(dlg.browser.model.index(docs), dlg.browser.view.ScrollHint.PositionAtCenter)
        app.processEvents()
        dlg_holder["dlg"] = dlg

    st.click(center_of(btn), open_dialog, after=0.1)
    dlg = dlg_holder["dlg"]
    dlg_pos = QPointF((win.width() - dlg.width() * 0.95) / 2, 20)

    def show_dialog():
        st.overlays = [(dlg.grab().toImage(), dlg_pos, 0.95)]

    show_dialog()
    st.hold(1.2)
    view = dlg.browser.view
    idx = dlg.browser.model.index(docs)
    scaled_origin = dlg_pos

    def dialog_point(widget_point):
        return QPointF(scaled_origin.x() + widget_point.x() * 0.95, scaled_origin.y() + widget_point.y() * 0.95)

    r = view.visualRect(idx)
    check = view.viewport().mapTo(dlg, QPoint(r.right() - 8, r.center().y()))

    def tick():
        panel._browser_toggled(bid, docs, True, True)
        app.processEvents()
        show_dialog()

    st.click(dialog_point(check), tick, after=1.4)
    done = next(b for b in dlg.findChildren(QPushButton) if b.text() == "סיום")
    done_pt = done.mapTo(dlg, done.rect().center())

    def close_dialog():
        dlg.close()
        panel._dialog = None
        st.overlays = []

    st.click(dialog_point(done_pt), close_dialog, after=0.2)
    st.wait_jobs()
    st.hold(1.6, live=True)

    # ============================================================ 2. חיפוש
    st.set_caption("2", "מחפשים", "מקלידים מילה או כמה מילים ולוחצים Enter – ניקוד, גרשיים ואותיות סופיות לא משנים")
    st.click(center_of(win.search_edit, 120), lambda: win.search_edit.setFocus(), after=0.2)
    st.type(win.search_edit, "הלך")
    st.click(center_of(win.search_btn), win.run_search, after=0.1)
    st.wait_jobs()
    st.set_caption("2", "התוצאות – הכי מדויקות ראשונות",
                   "המילים שנמצאו מסומנות בצהוב, ולכל תוצאה: המסמך, העמוד והפסקה (ב-PDF – עמוד ושורה)")
    first_card = win.results.list.visualRect(win.results.list.model().index(0, 0))
    card_pt = win.results.list.viewport().mapTo(win, first_card.center())
    st.move(QPointF(card_pt.x(), card_pt.y()), 1.0)
    st.hold(2.6)

    # ============================================================ 3. אפשרויות
    st.set_caption("3", "אפשרויות חיפוש", "הטיות: 'הלך' ימצא גם הלכה, הליכה, הולכים, וילך · רווח בין מילים · אותיות אהו״י")
    pop_pos = {}

    def open_options():
        win._show_options()
        app.processEvents()
        b = win.options_btn
        below = b.mapTo(win, QPoint(0, b.height() + 4))
        x = below.x() + b.width() - win.options.width()
        pop_pos["p"] = QPointF(max(8, min(x, win.width() - win.options.width() - 8)), below.y())
        st.overlays = [(win.options.grab().toImage(), pop_pos["p"], 1.0)]

    st.click(center_of(win.options_btn), open_options, after=0.8)
    cb = win.options.cb_inflect
    cb_pt = cb.mapTo(win.options, QPoint(cb.width() - 12, cb.height() // 2))

    def inflect():
        cb.setChecked(True)
        app.processEvents()
        st.overlays = [(win.options.grab().toImage(), pop_pos["p"], 1.0)]

    st.click(QPointF(pop_pos["p"].x() + cb_pt.x(), pop_pos["p"].y() + cb_pt.y()), inflect, after=0.6)
    st.wait_jobs()

    def close_options():
        win.options.close()
        st.overlays = []

    st.click(center_of(win.results, -150, 120), close_options, after=0.3)
    st.hold(2.4, live=True)

    # ============================================================ 4. פתיחת תוצאה
    st.set_caption("4", "פותחים את המסמך בדיוק במקום",
                   "לחיצה על תוצאה פותחת את המסמך במקום שלה (בחלונות עם וורד – ישר לשורה, מסומן). הבאה/הקודמת: F3")
    viewer = {}

    def open_hit():
        win.preview_hit(win.result.hits[0])
        app.processEvents()
        v = win.viewers[-1]
        v.resize(820, 560)
        app.processEvents()
        time.sleep(0.2)
        app.processEvents()
        viewer["v"] = v
        viewer["pos"] = QPointF((win.width() - 820 * 0.9) / 2, 40)
        st.overlays = [(v.grab().toImage(), viewer["pos"], 0.9)]

    card_rect = win.results.list.visualRect(win.results.list.model().index(0, 0))
    st.click(QPointF(*(lambda q: (q.x(), q.y()))(win.results.list.viewport().mapTo(win, card_rect.center()))),
             open_hit, after=1.6)
    v = viewer["v"]
    nxt = v.next_btn.mapTo(v, v.next_btn.rect().center())

    def go_next():
        v.go(v.index + 1)
        app.processEvents()
        st.overlays = [(v.grab().toImage(), viewer["pos"], 0.9)]

    st.click(QPointF(viewer["pos"].x() + nxt.x() * 0.9, viewer["pos"].y() + nxt.y() * 0.9), go_next, after=1.8)

    def close_viewer():
        v.close()
        st.overlays = []

    st.click(center_of(win.results, 200, -150), close_viewer, after=0.4)

    # ============================================================ 5. ביטוי מדויק
    st.set_caption("5", "ביטוי מדויק במירכאות", "\"ההולך בשבת\" – המילים צמודות ובסדר הזה, בלי קשר להגדרות הרווח")

    def select_all():
        win.search_edit.setFocus()
        win.search_edit.clear()

    st.click(center_of(win.search_edit, 80), select_all, after=0.2)
    st.type(win.search_edit, "\"ההולך בשבת\"", per_char=0.07)
    st.keycap = ["Enter"]
    st.hold(0.4)
    win.run_search()
    st.wait_jobs()
    st.keycap = None
    st.move(center_of(win.summary, 120), 0.9)
    st.hold(2.6)

    # ============================================================ 6. כמה סלים
    st.set_caption("6", "כמה סלים – בוחרים במה לחפש",
                   "כל סל מסומן ✓ – מחפשים בו. ביטול הסימון מוציא אותו מהחיפוש, ולחיצה כפולה – חיפוש רק בו")
    new_bid = {}

    def new_basket():
        b2 = panel.create_basket("שיעורים")
        panel.add_paths([os.path.join(docs, "תורה")], b2)
        new_bid["b"] = b2

    st.click(center_of(panel.new_btn), new_basket, after=0.2)
    st.wait_jobs()
    st.hold(1.0, live=True)
    model = panel.model
    b_idx = model.basket_index(new_bid["b"])
    pt = row_point(panel.tree, b_idx, QPointF(0, 0), win, from_right=8)

    def uncheck():
        model.setData(model.basket_index(new_bid["b"]), Qt.Unchecked, Qt.CheckStateRole)

    st.click(pt, uncheck, after=0.3)
    st.wait_jobs()
    st.move(center_of(win.scope_label, 60), 0.9)
    st.hold(2.2, live=True)

    # ============================================================ 7. גודל תצוגה
    st.set_caption("7", "התצוגה בגודל שנוח לכם", "Ctrl + מגדיל, Ctrl − מקטין, Ctrl 0 מחזיר – כל הממשק יחד, והבחירה נשמרת")
    st.keycap = ["+", "Ctrl"]
    win.set_zoom(1.15)
    st.refresh()
    st.hold(1.8)
    st.keycap = ["0", "Ctrl"]
    win.set_zoom(1.0)
    st.refresh()
    st.hold(1.4)
    st.keycap = None
    st.caption = ("", "", "")
    st.hold(0.6)

    # ============================================================ סיום
    st.cursor_visible = False
    st.card("זהו, אפשר להתחיל", "יוצרים סל · מוסיפים תיקיות · מחפשים", 3.8)
    st.close()
    win.close()
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(docs, ignore_errors=True)
    print(f"{out}: {st.frames} frames, {st.frames / FPS:.1f}s")


if __name__ == "__main__":
    main()
