from __future__ import annotations

import time
from enum import StrEnum

from PySide6.QtCore import QPoint, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLineEdit, QLabel, QTextEdit, QVBoxLayout, QWidget

from .macos_window import allow_fullscreen_overlay, order_front


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
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setObjectName("companion")
        self.setStyleSheet(
            "#companion { background: transparent; border: 0; }"
            "#outputFrame { background: transparent; border: 0; }"
            "QLabel { color: rgba(255, 255, 255, 230); font-size: 13px; } #statusLabel { color: rgba(255,255,255,160); font-size: 12px; font-weight: 600; }"
            "QTextEdit { color: rgba(255, 255, 255, 230); background: transparent; border: none; font-size: 13px; padding: 0; margin: 0; }"
            "QTextEdit::viewport { background: transparent; border: none; }"
            "QLineEdit { color: rgba(255, 255, 255, 230); background: rgba(255, 255, 255, 8); border: 1px solid rgba(255, 255, 255, 18); border-radius: 10px; padding: 8px; font-size: 14px; selection-background-color: #438cff; }"
        )
        self.state = CompanionState.HIDDEN
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.countdown_ring = CountdownRing()
        self.countdown_ring.setParent(self)
        self.header = QWidget()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.status_label)
        header.addStretch(1)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.output_frame = QFrame()
        self.output_frame.setObjectName("outputFrame")
        output_layout = QVBoxLayout(self.output_frame)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFrameShape(QFrame.Shape.NoFrame)
        self.output.setFrameShadow(QFrame.Shadow.Plain)
        self.output.setLineWidth(0)
        self.output.setMidLineWidth(0)
        self.output.setViewportMargins(0, 0, 0, 0)
        self.output.document().setDocumentMargin(0)
        self.output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        output_layout.addWidget(self.output)
        self.output_frame.hide()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask pi...")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.main_layout.addWidget(self.header)
        self.main_layout.addWidget(self.label)
        self.main_layout.addWidget(self.output_frame)
        self.main_layout.addWidget(self.input)
        self.setMinimumHeight(72)
        self.resize(380, 88)
        allow_fullscreen_overlay(self)
        self._follow_timer = QTimer(self)
        self._follow_timer.timeout.connect(self._follow_cursor)
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick_countdown)
        self._countdown_started = 0.0
        self._countdown_seconds = 0.0
        self._expanded_output = False

    def show_chat(self, on_submit) -> None:
        self.cancel_countdown()
        self.setMinimumHeight(72)
        self.state = CompanionState.CHAT_INPUT
        try:
            self.input.returnPressed.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.input.returnPressed.connect(lambda: on_submit(self.input.text()))
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.header.show()
        self.status_label.setText("OSPilot")
        self.label.setMaximumHeight(16777215)
        self.label.setText("")
        self.label.show()
        self.output.clear()
        self.output_frame.hide()
        self.input.setPlaceholderText("Ask pi...")
        self.input.setVisible(True)
        self._show_near_cursor(accept_keyboard=True)
        self.input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def show_voice_placeholder(self) -> None:
        self.cancel_countdown()
        self.setMinimumHeight(72)
        self.state = CompanionState.VOICE_INPUT
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.header.show()
        self.status_label.setText("Voice")
        self.label.setMaximumHeight(16777215)
        self.label.setText("Voice input placeholder. Type support can be wired next.")
        self.label.show()
        self.output_frame.hide()
        self.input.setVisible(False)
        self._show_near_cursor()

    def show_status(self, text: str, state: CompanionState = CompanionState.THINKING, tool_name: str = "") -> None:
        self.cancel_countdown()
        self.setMinimumHeight(72)
        self.state = state
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.header.show()
        if tool_name:
            self.status_label.setText(f"Running: {tool_name}")
        else:
            self.status_label.setText("Thinking" if state == CompanionState.THINKING else "OSPilot")
        self.label.setMaximumHeight(16777215)
        self.label.setText(text)
        self.label.show()
        if state == CompanionState.THINKING:
            self.output.clear()
        self.output_frame.hide()
        self.input.setVisible(False)
        self._show_near_cursor()

    def show_output(self, text: str, expanded: bool = False) -> None:
        self.cancel_countdown()
        self.setMinimumHeight(72)
        self.state = CompanionState.OUTPUT
        self._expanded_output = expanded
        self.main_layout.setContentsMargins(12, 8, 30, 8)
        self.header.hide()
        self.label.hide()
        self._set_output_markdown(text)
        self.output_frame.show()
        self.input.setVisible(False)
        self._show_near_cursor(width=self._output_width(expanded))

    def show_final_output(self, text: str) -> None:
        self.show_output(text, expanded=True)
        self.start_countdown(text)

    def reset(self) -> None:
        self.setMinimumHeight(72)
        self.state = CompanionState.HIDDEN
        self.input.clear()
        self.output.clear()
        self.label.setMaximumHeight(16777215)
        self.status_label.setText("")
        self._expanded_output = False
        self.header.show()
        self.label.show()
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.cancel_countdown()
        self._follow_timer.stop()
        self.hide()

    def start_countdown(self, text: str) -> None:
        seconds = min(18.0, max(5.0, 3.0 + len(text) / 55.0))
        self._countdown_seconds = seconds
        self._countdown_started = time.monotonic()
        self.countdown_ring.set_progress(1.0)
        self._position_countdown_ring()
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

    def _show_near_cursor(self, width: int = 380, accept_keyboard: bool = False) -> None:
        self.setFixedWidth(width)
        if self.output_frame.isVisible():
            self._fit_output_to_text(width)
        self.adjustSize()
        self._position_countdown_ring()
        target = self._position_near_cursor()
        allow_fullscreen_overlay(self, nonactivating=not accept_keyboard)
        if not self.isVisible():
            self.move(target)
            self.show()
            allow_fullscreen_overlay(self, nonactivating=not accept_keyboard)
        if not self._follow_timer.isActive():
            self._follow_timer.start(16)
        self.raise_()
        if accept_keyboard:
            order_front(self, make_key=True)
            self.input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        else:
            order_front(self)

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

    def _set_output_markdown(self, text: str) -> None:
        try:
            self.output.document().setDefaultStyleSheet(
                "body { color: rgba(255, 255, 255, 230); } "
                "p { margin: 0 0 6px 0; } "
                "ul, ol { margin-top: 0; margin-bottom: 6px; padding-left: 18px; } "
                "li { margin: 0 0 2px 0; } "
                "code { color: #d7e8ff; background-color: rgba(255, 255, 255, 18); } "
                "pre { background-color: rgba(255, 255, 255, 14); margin: 4px 0; } "
                "a { color: #8bbcff; }"
            )
            self.output.setMarkdown(text)
        except AttributeError:
            self.output.setPlainText(text)

    def _output_width(self, expanded: bool) -> int:
        if not expanded:
            return 420
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        bounds = screen.availableGeometry() if screen else QApplication.primaryScreen().availableGeometry()
        return max(420, min(720, bounds.width() - 96))

    def _fit_output_to_text(self, width: int) -> None:
        frame_padding = 18
        text_width = max(80, width - 28 - frame_padding)
        self.output.document().setTextWidth(text_width)
        document_height = self.output.document().size().height()
        row_height = self.output.fontMetrics().lineSpacing()
        if self._expanded_output:
            cursor = QCursor.pos()
            screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
            bounds = screen.availableGeometry() if screen else QApplication.primaryScreen().availableGeometry()
            max_text_height = max(row_height * 6, bounds.height() - 160)
            self.output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            max_text_height = row_height * 4 + 8
            self.output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        text_height = max(row_height + 8, min(document_height + 4, max_text_height))
        self.output.setFixedHeight(int(text_height))
        self.output_frame.setFixedHeight(int(text_height))
        if self._expanded_output:
            QTimer.singleShot(0, lambda: self.output.verticalScrollBar().setValue(0))
        else:
            self._scroll_output_to_bottom()

    def _scroll_output_to_bottom(self) -> None:
        QTimer.singleShot(0, lambda: self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum()))

    def _position_countdown_ring(self) -> None:
        self.countdown_ring.move(max(0, self.width() - self.countdown_ring.width() - 9), 8)

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

        # Base liquid glass fill - semi-transparent dark with slight blue tint
        painter.setBrush(QColor(32, 35, 45, 155))
        painter.setPen(QPen(QColor(255, 255, 255, 45), 1))
        painter.drawRoundedRect(rect, 20, 20)

