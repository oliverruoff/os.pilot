from __future__ import annotations

import time
from enum import StrEnum

from PySide6.QtCore import QPoint, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLineEdit, QLabel, QTextEdit, QVBoxLayout, QWidget


class CompanionState(StrEnum):
    HIDDEN = "hidden"
    CHAT_INPUT = "chat_input"
    VOICE_INPUT = "voice_input"
    THINKING = "thinking"
    OUTPUT = "output"
    TOOL_RUNNING = "tool_running"
    EXTENSION_UI = "extension_ui"
    ERROR = "error"


class CountdownRing(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(18, 18)
        self.progress = 1.0
        self.hide()

    def set_progress(self, progress: float) -> None:
        self.progress = max(0.0, min(1.0, progress))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(2.5, 2.5, self.width() - 5, self.height() - 5)
        painter.setPen(QPen(QColor(255, 255, 255, 45), 2))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor(125, 178, 255, 230), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 90 * 16, int(-360 * self.progress * 16))


class CompanionBubble(QFrame):
    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("companion")
        self.setStyleSheet(
            "#companion { background: transparent; border: 0; }"
            "#outputFrame { background: #252833; border: 1px solid #4a5060; border-radius: 10px; }"
            "QLabel { color: white; font-size: 13px; } #statusLabel { color: rgba(255,255,255,175); font-size: 12px; font-weight: 600; }"
            "QTextEdit { color: white; background: transparent; border: 0; font-size: 13px; }"
            "QTextEdit::viewport { background: transparent; }"
            "QLineEdit { color: white; background: #252833; border: 1px solid #4a5060; border-radius: 8px; padding: 8px; font-size: 14px; selection-background-color: #438cff; }"
        )
        self.state = CompanionState.HIDDEN
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.countdown_ring = CountdownRing()
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.status_label)
        header.addStretch(1)
        header.addWidget(self.countdown_ring)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.output_frame = QFrame()
        self.output_frame.setObjectName("outputFrame")
        output_layout = QVBoxLayout(self.output_frame)
        output_layout.setContentsMargins(8, 6, 8, 6)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        output_layout.addWidget(self.output)
        self.output_frame.hide()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask pi...")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addLayout(header)
        layout.addWidget(self.label)
        layout.addWidget(self.output_frame)
        layout.addWidget(self.input)
        self.setMinimumHeight(72)
        self.resize(380, 88)
        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._follow_cursor)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick_countdown)
        self._countdown_started = 0.0
        self._countdown_seconds = 0.0

    def show_chat(self, on_submit) -> None:
        self.cancel_countdown()
        self.state = CompanionState.CHAT_INPUT
        try:
            self.input.returnPressed.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.input.returnPressed.connect(lambda: on_submit(self.input.text()))
        self.status_label.setText("OSPilot")
        self.label.setText("")
        self.output.clear()
        self.output_frame.hide()
        self.input.setPlaceholderText("Ask pi...")
        self.input.setVisible(True)
        self._show_near_cursor()
        self.input.setFocus()

    def show_voice_placeholder(self) -> None:
        self.cancel_countdown()
        self.state = CompanionState.VOICE_INPUT
        self.status_label.setText("Voice")
        self.label.setText("Voice input placeholder. Type support can be wired next.")
        self.output_frame.hide()
        self.input.setVisible(False)
        self._show_near_cursor()

    def show_status(self, text: str, state: CompanionState = CompanionState.THINKING) -> None:
        self.cancel_countdown()
        self.state = state
        self.status_label.setText("Thinking" if state == CompanionState.THINKING else "OSPilot")
        self.label.setText(text)
        self.output_frame.hide()
        self.input.setVisible(False)
        self._show_near_cursor()

    def show_output(self, text: str) -> None:
        self.cancel_countdown()
        self.state = CompanionState.OUTPUT
        self.status_label.setText("Answer")
        self.label.setText("")
        self.output.setPlainText(text)
        self._scroll_output_to_bottom()
        self.output_frame.show()
        self.input.setVisible(False)
        self._show_near_cursor(width=460)

    def show_final_output(self, text: str) -> None:
        self.show_output(text)
        self.start_countdown(text)

    def reset(self) -> None:
        self.state = CompanionState.HIDDEN
        self.input.clear()
        self.output.clear()
        self.status_label.setText("")
        self.cancel_countdown()
        self._follow_timer.stop()
        self.hide()

    def start_countdown(self, text: str) -> None:
        seconds = min(18.0, max(5.0, 3.0 + len(text) / 55.0))
        self._countdown_seconds = seconds
        self._countdown_started = time.monotonic()
        self.countdown_ring.set_progress(1.0)
        self.countdown_ring.show()
        self._countdown_timer.start(50)

    def cancel_countdown(self) -> None:
        self._countdown_timer.stop()
        self.countdown_ring.hide()

    def _tick_countdown(self) -> None:
        if self._countdown_seconds <= 0:
            return
        elapsed = time.monotonic() - self._countdown_started
        remaining = max(0.0, self._countdown_seconds - elapsed)
        self.countdown_ring.set_progress(remaining / self._countdown_seconds)
        if remaining <= 0:
            self.reset()

    def _show_near_cursor(self, width: int = 380) -> None:
        self.setFixedWidth(width)
        if self.output_frame.isVisible():
            self._fit_output_to_text(width)
        self.adjustSize()
        target = self._position_near_cursor()
        if not self.isVisible():
            self.move(target)
            self.show()
        if not self._follow_timer.isActive():
            self._follow_timer.start(16)
        self.raise_()
        self.activateWindow()

    def _follow_cursor(self) -> None:
        if not self.isVisible():
            self._follow_timer.stop()
            return
        target = self._position_near_cursor()
        current = self.pos()
        eased = QPoint(
            current.x() + round((target.x() - current.x()) * 0.28),
            current.y() + round((target.y() - current.y()) * 0.28),
        )
        if abs(eased.x() - target.x()) <= 1 and abs(eased.y() - target.y()) <= 1:
            eased = target
        if eased != current:
            self.move(eased)

    def _fit_output_to_text(self, width: int) -> None:
        frame_padding = 18
        text_width = max(80, width - 28 - frame_padding)
        self.output.document().setTextWidth(text_width)
        document_height = self.output.document().size().height()
        row_height = self.output.fontMetrics().lineSpacing()
        max_text_height = row_height * 4 + 8
        text_height = max(row_height + 8, min(document_height + 4, max_text_height))
        self.output.setFixedHeight(int(text_height))
        self.output_frame.setFixedHeight(int(text_height + 14))
        self._scroll_output_to_bottom()

    def _scroll_output_to_bottom(self) -> None:
        QTimer.singleShot(0, lambda: self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum()))

    def _position_near_cursor(self) -> QPoint:
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        bounds = screen.availableGeometry() if screen else QApplication.primaryScreen().availableGeometry()
        offset = 24
        x = cursor.x() + offset
        y = cursor.y() + offset
        if x + self.width() > bounds.right():
            x = cursor.x() - self.width() - offset
        if y + self.height() > bounds.bottom():
            y = cursor.y() - self.height() - offset
        x = max(bounds.left(), min(x, bounds.right() - self.width()))
        y = max(bounds.top(), min(y, bounds.bottom() - self.height()))
        return QPoint(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor("#1a1c22"))
        painter.setPen(QPen(QColor("#555b68"), 1))
        painter.drawRoundedRect(rect, 14, 14)
