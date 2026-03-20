import sys, subprocess, tempfile, os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QFileDialog,
    QAction, QWidget, QVBoxLayout, QPushButton, QPlainTextEdit as OutputBox
)
from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QPainter
from PyQt5.QtCore import Qt, QRect, QSize
from PyQt5.QtWidgets import QTextEdit

from pygments import lex
from pygments.lexers import PythonLexer, CppLexer
from pygments.token import Token


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_paint(event)


class Editor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setFont(QFont("Consolas", 11))
        self.lexer = PythonLexer()

        self.textChanged.connect(self.highlight)

        self.line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_width)
        self.updateRequest.connect(self.update_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_width(0)

    def line_number_width(self):
        digits = len(str(self.blockCount()))
        return 10 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_width(self, _):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def update_area(self, rect, dy):
        if dy:
            self.line_area.scroll(0, dy)
        else:
            self.line_area.update(0, rect.y(), self.line_area.width(), rect.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def line_number_paint(self, event):
        painter = QPainter(self.line_area)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))

        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#858585"))
                painter.drawText(0, top, self.line_area.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignRight, str(number + 1))

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            number += 1

    def highlight_current_line(self):
        extra = []

        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#2a2a2a"))
        selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)

        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()

        extra.append(selection)
        self.setExtraSelections(extra)

    def set_language(self, filename):
        if filename.endswith(".py"):
            self.lexer = PythonLexer()
        elif filename.endswith((".cpp", ".h")):
            self.lexer = CppLexer()

    def highlight(self):
        text = self.toPlainText()
        self.blockSignals(True)

        cursor = self.textCursor()
        pos = cursor.position()

        self.selectAll()
        self.setCurrentCharFormat(self.default_format())

        index = 0
        for ttype, value in lex(text, self.lexer):
            length = len(value)
            fmt = self.get_format(ttype)

            cursor.setPosition(index)
            cursor.setPosition(index + length, cursor.KeepAnchor)
            cursor.setCharFormat(fmt)
            index += length

        cursor.setPosition(pos)
        self.setTextCursor(cursor)
        self.blockSignals(False)

    def default_format(self):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#d4d4d4"))
        return fmt

    def get_format(self, ttype):
        fmt = QTextCharFormat()

        if ttype in Token.Keyword:
            fmt.setForeground(QColor("#569CD6"))
            fmt.setFontWeight(QFont.Bold)
        elif ttype in Token.String:
            fmt.setForeground(QColor("#CE9178"))
        elif ttype in Token.Comment:
            fmt.setForeground(QColor("#6A9955"))
        elif ttype in Token.Name.Function:
            fmt.setForeground(QColor("#DCDCAA"))
        else:
            fmt.setForeground(QColor("#d4d4d4"))

        return fmt


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CodePulse")
        self.resize(1100, 700)

        self.editor = Editor()
        self.output = OutputBox()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(150)
        self.output.setStyleSheet("background:#111;color:#ccc;padding:5px;")

        run_btn = QPushButton("▶ Run")
        run_btn.clicked.connect(self.run_code)

        layout = QVBoxLayout()
        layout.addWidget(run_btn)
        layout.addWidget(self.editor)
        layout.addWidget(self.output)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.file = None

        self.init_menu()
        self.theme()

    def init_menu(self):
        m = self.menuBar().addMenu("File")

        new = QAction("New", self)
        open_ = QAction("Open", self)
        save = QAction("Save", self)

        new.setShortcut("Ctrl+N")
        open_.setShortcut("Ctrl+O")
        save.setShortcut("Ctrl+S")

        new.triggered.connect(self.new_file)
        open_.triggered.connect(self.open_file)
        save.triggered.connect(self.save_file)

        m.addAction(new)
        m.addAction(open_)
        m.addAction(save)

    def theme(self):
        self.setStyleSheet("""
            QMainWindow { background:#1e1e1e; }
            QPlainTextEdit { background:#1e1e1e; color:#d4d4d4; border:none; padding:10px; }
            QPushButton { background:#2d2d2d; color:white; padding:6px; }
            QPushButton:hover { background:#3c3c3c; }
        """)

    def new_file(self):
        self.editor.clear()
        self.file = None

    def open_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Open")
        if f:
            with open(f, "r", encoding="utf-8") as file:
                self.editor.setPlainText(file.read())
            self.file = f
            self.editor.set_language(f)

    def save_file(self):
        if not self.file:
            f, _ = QFileDialog.getSaveFileName(self, "Save")
            if not f:
                return
            self.file = f

        with open(self.file, "w", encoding="utf-8") as file:
            file.write(self.editor.toPlainText())

    def run_code(self):
        code = self.editor.toPlainText()

        if not self.file:
            self.output.setPlainText("Сначала сохрани файл")
            return

        ext = os.path.splitext(self.file)[1]

        try:
            if ext == ".py":
                result = subprocess.run(["python", self.file], capture_output=True, text=True)

            elif ext in [".cpp"]:
                exe = self.file.replace(".cpp", ".exe")
                subprocess.run(["g++", self.file, "-o", exe])
                result = subprocess.run([exe], capture_output=True, text=True)

            else:
                self.output.setPlainText("Не поддерживается")
                return

            self.output.setPlainText(result.stdout + result.stderr)

        except Exception as e:
            self.output.setPlainText(str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
