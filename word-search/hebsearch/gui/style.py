QSS = """
QWidget { font-family: "Segoe UI", "Arial", sans-serif; font-size: 10pt; color: #1f2937; }
QMainWindow, #central { background: #f4f6fb; }
#panel { background: #ffffff; border: 1px solid #e3e8f0; border-radius: 10px; }
QLabel#title { font-size: 13pt; font-weight: 700; color: #1e3a8a; }
QLabel#muted { color: #64748b; }
QLabel#summary { font-size: 11pt; color: #334155; }
QPushButton {
    background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 12px;
}
QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }
QPushButton:disabled { color: #94a3b8; }
QPushButton#primary {
    background: #2563eb; color: white; border: none; font-weight: 600;
    font-size: 12pt; padding: 8px 26px;
}
QPushButton#primary:hover { background: #1d4ed8; }
QPushButton#primary:disabled { background: #93c5fd; }
QToolButton { border: none; padding: 4px; border-radius: 4px; }
QToolButton:hover { background: #eef2f7; }
QLineEdit#search {
    font-size: 16pt; padding: 7px 12px; border: 2px solid #cbd5e1; border-radius: 8px;
    background: white; selection-background-color: #bfdbfe;
}
QLineEdit#search:focus { border-color: #2563eb; }
QComboBox, QSpinBox { padding: 3px 6px; border: 1px solid #cbd5e1; border-radius: 5px; background: white; }
QListWidget { border: 1px solid #e3e8f0; border-radius: 6px; background: #ffffff; outline: none; }
QListWidget::item { padding: 6px 4px; border-bottom: 1px solid #f1f5f9; }
QListWidget::item:selected { background: #dbeafe; color: #1e3a8a; }
QListWidget::item:hover:!selected { background: #f8fafc; }
QProgressBar {
    border: none; background: #e2e8f0; border-radius: 4px; max-height: 8px; text-align: center;
}
QProgressBar::chunk { background: #2563eb; border-radius: 4px; }
QTextBrowser { border: none; background: #f4f6fb; }
QSplitter::handle { background: transparent; }
QStatusBar { background: #ffffff; color: #64748b; border-top: 1px solid #e3e8f0; }
QCheckBox { spacing: 6px; }
"""
