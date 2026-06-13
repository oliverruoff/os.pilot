from __future__ import annotations

import sys
import time
from enum import StrEnum

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLineEdit, QLabel, QTextEdit, QVBoxLayout, QWidget

from ospilot.desktop.window import allow_fullscreen_overlay, focus_widget, order_front


class CompanionState(StrEnum):
    HIDDEN = "hidden"
    CHAT_INPUT = "chat_input"
    VOICE_INPUT = "voice_input"
    THINKING = "thinking"
    OUTPUT = "output"
    TOOL_RUNNING = "tool_running"
    EXTENSION_UI = "extension_ui"
    ERROR = "error"


FONT_STACK = '"JetBrains Mono", "Cascadia Code", "SF Mono", Menlo, Consolas, monospace'
FONT_FAMILIES = ["JetBrains Mono", "Cascadia Code", "SF Mono", "Menlo", "Consolas", "monospace"]

ACCENTS = {
    CompanionState.CHAT_INPUT: (QColor(123, 165, 214), QColor(105, 126, 158)),
    CompanionState.VOICE_INPUT: (QColor(121, 172, 184), QColor(105, 126, 158)),
    CompanionState.THINKING: (QColor(132, 151, 190), QColor(113, 123, 149)),
    CompanionState.OUTPUT: (QColor(122, 171, 165), QColor(105, 137, 174)),
    CompanionState.TOOL_RUNNING: (QColor(190, 157, 105), QColor(104, 145, 165)),
    CompanionState.EXTENSION_UI: (QColor(145, 132, 183), QColor(105, 142, 168)),
    CompanionState.ERROR: (QColor(205, 104, 119), QColor(185, 131, 93)),
}


def _tech_font(point_size: int = 13, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPointSize(point_size)
    font.setWeight(weight)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font


class CountdownRing(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(18, 18)
        self.progress = 1.0
        self.accent = QColor(125, 178, 255, 230)
        self.hide()

    def set_accent(self, color: QColor) -> None:
        self.accent = QColor(color)
        self.accent.setAlpha(230)
        self.update()

    def set_progress(self, progress: float) -> None:
        self.progress = max(0.0, min(1.0, progress))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(2.5, 2.5, self.width() - 5, self.height() - 5)
        painter.setPen(QPen(QColor(255, 255, 255, 45), 2))
        painter.drawEllipse(rect)
        painter.setPen(QPen(self.accent, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 90 * 16, int(-360 * self.progress * 16))


COUNTDOWN_RING_RIGHT_PADDING = 9
COUNTDOWN_RING_TEXT_GAP = 10


class TranscriptView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._messages: list[tuple[str, str]] = []
        self._block_gap = 10
        self._line_gap = 2
        self._text_width = 320
        self._base_color = QColor(235, 246, 255)
        self.setFont(_tech_font(13))
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

    def set_messages(self, messages: list[tuple[str, str]]) -> None:
        self._messages = [(speaker, text.strip()) for speaker, text in messages if text.strip()]
        self.updateGeometry()
        self.update()

    def set_text_width(self, width: int) -> None:
        self._text_width = max(80, width)
        self.updateGeometry()
        self.update()

    def content_height(self) -> int:
        if not self._messages:
            return self.fontMetrics().lineSpacing() + 8
        total = 0
        for index, (speaker, text) in enumerate(self._messages):
            total += self._block_height(speaker, text)
            if index:
                total += self._block_gap
        return total

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._text_width, self.content_height())

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self.font())
        y = self.height()
        for speaker, text in reversed(self._messages):
            block_height = self._block_height(speaker, text)
            y -= block_height
            if y < self.height() and y + block_height > 0:
                center = y + block_height / 2
                progress = max(0.0, min(1.0, center / max(1, self.height())))
                alpha = int(55 + (232 - 55) * progress)
                color = QColor(self._base_color)
                color.setAlpha(alpha)
                painter.setPen(color)
                painter.drawText(QRect(0, int(y), self._text_width, block_height), _TEXT_FLAGS, self._format_block(speaker, text))
            y -= self._block_gap
            if y + block_height < 0:
                break

    def _block_height(self, speaker: str, text: str) -> int:
        rect = self.fontMetrics().boundingRect(QRect(0, 0, self._text_width, 10000), _TEXT_FLAGS, self._format_block(speaker, text))
        return max(self.fontMetrics().lineSpacing(), rect.height()) + self._line_gap

    def _format_block(self, speaker: str, text: str) -> str:
        return f"{speaker}: {text}"


_TEXT_FLAGS = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap)


class CompanionBubble(QFrame):
    def __init__(self) -> None:
        # Do not use Qt.Tool on macOS: AppKit/Qt may hide tool panels as soon
        # as OSPilot loses activation, which is exactly what happens after the
        # user presses Enter and we focus/click/type in the target app. Use a
        # normal borderless top-level overlay instead and make it non-activating
        # via allow_fullscreen_overlay() for passive thinking/status updates.
        window_type = Qt.WindowType.Window if sys.platform == "darwin" else Qt.WindowType.Tool
        super().__init__(None, window_type | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setObjectName("companion")
        self.setStyleSheet(
            "#companion { background: transparent; border: 0; }"
            "#outputFrame { background: transparent; border: 0; }"
            f"QLabel {{ color: rgba(235, 246, 255, 232); font-family: {FONT_STACK}; font-size: 13px; }}"
            f"#hintLabel {{ color: rgba(164, 184, 205, 135); font-family: {FONT_STACK}; font-size: 11px; padding-left: 2px; }}"
            f"#outputHintLabel {{ color: rgba(172, 186, 202, 105); font-family: {FONT_STACK}; font-size: 10px; padding-top: 1px; }}"
            f"#statusLabel {{ color: rgba(175, 214, 255, 160); font-family: {FONT_STACK}; font-size: 12px; font-weight: 600; }}"
            f"QTextEdit {{ color: rgba(235, 246, 255, 232); background: transparent; border: none; font-family: {FONT_STACK}; font-size: 13px; padding: 0; margin: 0; }}"
            "QTextEdit::viewport { background: transparent; border: none; }"
            f"QLineEdit {{ color: rgba(238, 249, 255, 238); background: transparent; border: none; padding: 9px 10px; font-family: {FONT_STACK}; font-size: 14px; selection-background-color: #3f6fa8; }}"
        )
        self.state = CompanionState.HIDDEN
        self._accent_primary, self._accent_secondary = ACCENTS[CompanionState.OUTPUT]
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setFont(_tech_font(12, QFont.Weight.DemiBold))
        self.countdown_ring = CountdownRing()
        self.countdown_ring.setParent(self)
        self.header = QWidget()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.status_label)
        header.addStretch(1)
        self.label = QLabel("")
        self.label.setFont(_tech_font(13))
        self.label.setWordWrap(True)
        self.output_frame = QFrame()
        self.output_frame.setObjectName("outputFrame")
        output_layout = QVBoxLayout(self.output_frame)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output = QTextEdit()
        self.output.setFont(_tech_font(13))
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
        self.transcript = TranscriptView()
        output_layout.addWidget(self.transcript)
        self.transcript.hide()
        self.output_frame.hide()
        self.output_hint_label = QLabel(_output_shortcut_hint())
        self.output_hint_label.setObjectName("outputHintLabel")
        self.output_hint_label.setFont(_tech_font(10))
        self.output_hint_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.output_hint_label.hide()
        self.input = QLineEdit()
        self.input.setFont(_tech_font(14))
        self.input.setPlaceholderText("> ask pi...")
        self.hint_label = QLabel("Enter to send | /new for new session")
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setFont(_tech_font(11))
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.main_layout.addWidget(self.header)
        self.main_layout.addWidget(self.label)
        self.main_layout.addWidget(self.output_frame)
        self.main_layout.addWidget(self.output_hint_label)
        self.main_layout.addWidget(self.input)
        self.main_layout.addWidget(self.hint_label)
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
        self._fit_final_output = False
        self._inline_final_output = False
        self._showing_transcript = False
        self._mouse_passthrough = False
        self._passive_front_attempt = 0
        self._escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._escape_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._escape_shortcut.activated.connect(self._hide_from_escape)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape and self.isVisible():
            self._hide_from_escape()
            event.accept()
            return
        super().keyPressEvent(event)

    def _hide_from_escape(self) -> None:
        if self.isVisible():
            self.reset()

    def show_chat(self, on_submit, messages: list[tuple[str, str]] | None = None) -> None:
        self.cancel_countdown()
        self.setMinimumHeight(72)
        self._set_mouse_passthrough(False)
        if self.isVisible() and self.state != CompanionState.CHAT_INPUT:
            # Re-show the bubble when switching from passive output/status mode
            # to input mode. On macOS a window previously shown as
            # non-activating may not reliably become key until it is ordered in
            # again with the non-activating style removed.
            self.hide()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        allow_fullscreen_overlay(self, nonactivating=False)
        self.state = CompanionState.CHAT_INPUT
        self._set_visual_state(self.state)
        try:
            self.input.returnPressed.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.input.returnPressed.connect(lambda: on_submit(self.input.text()))
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.header.hide()
        self.status_label.setText("")
        self.label.setMaximumHeight(16777215)
        self._inline_final_output = False
        self._showing_transcript = False
        self.label.setText("")
        self.label.hide()
        self.output.clear()
        transcript_messages = list(messages or [])
        if transcript_messages:
            self._showing_transcript = True
            self.output.hide()
            self.transcript.set_messages(transcript_messages)
            self.transcript.show()
            self.output_frame.show()
        else:
            self.output.show()
            self.transcript.hide()
            self.output_frame.hide()
        self.output_hint_label.hide()
        self.input.setPlaceholderText("> ask pi...")
        self.input.setVisible(True)
        self.hint_label.show()
        width = self._transcript_width(transcript_messages) if transcript_messages else 380
        self._show_near_cursor(width=width, accept_keyboard=True)
        self._schedule_input_focus()

    def show_voice_placeholder(self) -> None:
        self.cancel_countdown()
        self.setMinimumHeight(72)
        self._set_mouse_passthrough(True)
        self._relinquish_keyboard_focus()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.state = CompanionState.VOICE_INPUT
        self._set_visual_state(self.state)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.header.hide()
        self.status_label.setText("")
        self.label.setMaximumHeight(16777215)
        self.label.setText("Voice input placeholder. Type support can be wired next.")
        self.label.show()
        self._showing_transcript = False
        self.output.show()
        self.transcript.hide()
        self.output_frame.hide()
        self.output_hint_label.hide()
        self.input.setVisible(False)
        self.hint_label.hide()
        self._show_near_cursor()

    def show_status(self, text: str, state: CompanionState = CompanionState.THINKING, tool_name: str = "") -> None:
        self.cancel_countdown()
        if state == CompanionState.THINKING and not text and not tool_name:
            return
        if state == CompanionState.THINKING and text:
            self.show_stream(text)
            return
        self.setMinimumHeight(72)
        self._set_mouse_passthrough(True)
        self._relinquish_keyboard_focus()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.state = state
        self._set_visual_state(state)
        self._fit_final_output = False
        self._inline_final_output = False
        self._showing_transcript = False
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.header.hide()
        self.status_label.setText("")
        self.label.setMaximumHeight(16777215)
        self.label.setWordWrap(True)
        if not text and tool_name:
            text = f"Running {tool_name}..."
        self.label.setText(text)
        self.label.setVisible(bool(text))
        if state == CompanionState.THINKING:
            self.output.clear()
        self.output.show()
        self.transcript.hide()
        self.output_frame.hide()
        self.output_hint_label.hide()
        self.input.setVisible(False)
        self.hint_label.hide()
        self._show_near_cursor()

    def begin_thinking(self) -> None:
        self.cancel_countdown()
        self.setMinimumHeight(0)
        self._set_mouse_passthrough(True)
        self._relinquish_keyboard_focus()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.state = CompanionState.THINKING
        self._set_visual_state(self.state)
        self._expanded_output = False
        self._fit_final_output = False
        self._inline_final_output = False
        self._showing_transcript = False
        self.main_layout.setContentsMargins(12, 8, 30, 8)
        self.header.hide()
        self.status_label.setText("")
        self.label.hide()
        self.transcript.hide()
        self.output.show()
        self.output.setPlainText("Thinking...")
        self.output_frame.show()
        self.output_hint_label.hide()
        self.input.setVisible(False)
        self.hint_label.hide()
        self._show_near_cursor(width=380)

    def show_stream(self, text: str) -> None:
        self.cancel_countdown()
        self.setMinimumHeight(0)
        self._relinquish_keyboard_focus()
        if not self.output_frame.isVisible() or self.state != CompanionState.THINKING:
            self.begin_thinking()
        self.state = CompanionState.THINKING
        self._set_visual_state(self.state)
        self._fit_final_output = False
        self._inline_final_output = False
        self._showing_transcript = False
        self.transcript.hide()
        self.output.show()
        if not text.strip():
            text = "Thinking..."
        self.output.setPlainText(text)
        self._show_near_cursor(width=380)

    def show_output(self, text: str, expanded: bool = False, fit_to_content: bool = False) -> None:
        self.cancel_countdown()
        self.setMinimumHeight(0)
        self._set_mouse_passthrough(True)
        self._relinquish_keyboard_focus()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.state = CompanionState.OUTPUT
        self._set_visual_state(self.state)
        self._expanded_output = expanded
        self._fit_final_output = fit_to_content
        self._inline_final_output = fit_to_content and _is_inline_final_output(text) and self._inline_final_output_fits(text)
        self._showing_transcript = False
        self.transcript.hide()
        self.output.show()
        right_margin = self._countdown_reserved_margin() if fit_to_content else 30
        self.main_layout.setContentsMargins(12, 8, right_margin, 8)
        self.header.hide()
        if self._inline_final_output:
            self.main_layout.setContentsMargins(16, 8, right_margin, 8)
            self.label.setWordWrap(False)
            self.label.setText(text)
            self.label.show()
            self.output.clear()
            self.output_frame.hide()
        else:
            self.label.hide()
            self._set_output_markdown(text)
            self.output_frame.show()
        self.output_hint_label.setText(_output_shortcut_hint())
        self.output_hint_label.show()
        self.input.setVisible(False)
        self.hint_label.hide()
        self._show_near_cursor(width=self._output_width(text, expanded))

    def show_final_output(self, text: str) -> None:
        self.show_output(text, expanded=False, fit_to_content=True)
        self.start_countdown(text)

    def show_final_transcript(self, messages: list[tuple[str, str]], countdown_text: str = "") -> None:
        self.cancel_countdown()
        self.setMinimumHeight(0)
        self._set_mouse_passthrough(True)
        self._relinquish_keyboard_focus()
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.state = CompanionState.OUTPUT
        self._set_visual_state(self.state)
        self._expanded_output = False
        self._fit_final_output = True
        self._inline_final_output = False
        self._showing_transcript = True
        self.main_layout.setContentsMargins(12, 8, self._countdown_reserved_margin(), 8)
        self.header.hide()
        self.label.hide()
        self.output.hide()
        self.transcript.set_messages(messages)
        self.transcript.show()
        self.output_frame.show()
        self.output_hint_label.setText(_output_shortcut_hint())
        self.output_hint_label.show()
        self.input.setVisible(False)
        self.hint_label.hide()
        width = self._transcript_width(messages)
        self._show_near_cursor(width=width)
        self.start_countdown(countdown_text or "\n".join(f"{speaker}: {text}" for speaker, text in messages))

    def reset(self) -> None:
        self.setMinimumHeight(72)
        self._set_mouse_passthrough(False)
        self.state = CompanionState.HIDDEN
        self.input.clear()
        self.output.clear()
        self.label.setMaximumHeight(16777215)
        self.status_label.setText("")
        self._expanded_output = False
        self._fit_final_output = False
        self._inline_final_output = False
        self._showing_transcript = False
        self.output.show()
        self.transcript.hide()
        self.header.show()
        self.label.show()
        self.output_hint_label.hide()
        self.hint_label.hide()
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.cancel_countdown()
        self._follow_timer.stop()
        self.hide()

    def start_countdown(self, text: str) -> None:
        seconds = min(18.0, max(5.0, 3.0 + len(text) / 55.0))
        self._countdown_seconds = seconds
        self._countdown_started = time.monotonic()
        self.countdown_ring.set_progress(1.0)
        self.countdown_ring.set_accent(self._accent_primary)
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
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, not accept_keyboard)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, not accept_keyboard)
        self.setFixedWidth(width)
        if self.output_frame.isVisible():
            self._fit_output_to_text(width)
        self.adjustSize()
        if self.output_frame.isVisible():
            self.resize(width, self.sizeHint().height())
        self._position_countdown_ring()
        target = self._position_near_cursor()
        allow_fullscreen_overlay(self, nonactivating=not accept_keyboard)
        if not self.isVisible():
            self.move(target)
            self.show()
            allow_fullscreen_overlay(self, nonactivating=not accept_keyboard)
        if not self._follow_timer.isActive():
            self._follow_timer.start(16)
        if accept_keyboard:
            self.raise_()
            order_front(self, make_key=True)
            self._focus_input()
        else:
            # Passive thinking/status updates must be visible without stealing
            # focus; otherwise fragile macOS UI such as open menus/popovers can
            # disappear between tool clicks. Re-order a few times because the
            # foreground app may be changing exactly when the user submits a
            # prompt or when OSPilot focuses the target app for a click/type.
            self._schedule_passive_order_front()

    def _order_passive_front(self, attempt: int) -> None:
        if attempt != self._passive_front_attempt or self.state == CompanionState.HIDDEN:
            return
        if not self.isVisible():
            self.show()
        allow_fullscreen_overlay(self, nonactivating=True)
        if sys.platform != "darwin":
            self.raise_()
        order_front(self)

    def _schedule_passive_order_front(self) -> None:
        self._passive_front_attempt += 1
        attempt = self._passive_front_attempt
        self._order_passive_front(attempt)
        for delay_ms in (50, 150, 300):
            QTimer.singleShot(delay_ms, lambda attempt=attempt: self._order_passive_front(attempt))

    def _focus_input(self) -> None:
        if self.state != CompanionState.CHAT_INPUT or not self.input.isVisible():
            return
        order_front(self, make_key=True)
        QApplication.setActiveWindow(self)
        self.raise_()
        self.activateWindow()
        self.input.activateWindow()
        self.input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        focus_widget(self.input, self)

    def _schedule_input_focus(self) -> None:
        self._focus_input()
        for delay_ms in (75, 150, 300):
            QTimer.singleShot(delay_ms, self._focus_input)

    def _set_mouse_passthrough(self, enabled: bool) -> None:
        if self._mouse_passthrough == enabled:
            return
        self._mouse_passthrough = enabled
        was_visible = self.isVisible()
        if was_visible:
            self.hide()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
        if was_visible:
            self.show()

    def _relinquish_keyboard_focus(self) -> None:
        self.input.clearFocus()
        self.output.clearFocus()
        self.clearFocus()

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
                f"body {{ color: rgba(235, 246, 255, 232); font-family: {FONT_STACK}; }} "
                "p { margin: 0 0 7px 0; } "
                "ul, ol { margin-top: 0; margin-bottom: 7px; padding-left: 18px; } "
                "li { margin: 0 0 3px 0; } "
                "blockquote { color: rgba(196, 213, 232, 210); border-left: 2px solid #7ba5d6; margin: 4px 0; padding-left: 8px; } "
                "code { color: #dcecff; background-color: rgba(126, 158, 194, 24); font-family: monospace; } "
                "pre { color: #e4eef8; background-color: rgba(6, 11, 20, 145); border: 1px solid rgba(139, 166, 196, 42); margin: 6px 0; padding: 7px; } "
                "a { color: #9dc2ec; text-decoration: none; } "
                "strong { color: #ffffff; }"
            )
            self.output.setMarkdown(text)
        except AttributeError:
            self.output.setPlainText(text)

    def _transcript_width(self, messages: list[tuple[str, str]]) -> int:
        hint_min_width = self._output_hint_min_width()
        longest = ""
        for speaker, text in messages:
            for line in f"{speaker}: {text}".splitlines():
                if len(line) > len(longest):
                    longest = line
        text_width = self.transcript.fontMetrics().horizontalAdvance(longest)
        return max(hint_min_width, 300, min(460, text_width + 56))

    def _output_width(self, text: str, expanded: bool) -> int:
        hint_min_width = self._output_hint_min_width()
        if not expanded:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            longest = max(lines, key=len, default=text)
            metrics = self.label.fontMetrics() if self._inline_final_output else self.output.fontMetrics()
            text_width = metrics.horizontalAdvance(longest)
            if self._inline_final_output:
                return max(hint_min_width, 140, min(self._max_inline_output_width(), text_width + 16 + self._countdown_reserved_margin()))
            return max(hint_min_width, 140, min(420, text_width + 56))
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        bounds = screen.availableGeometry() if screen else QApplication.primaryScreen().availableGeometry()
        return max(hint_min_width, 420, min(720, bounds.width() - 96))

    def _output_hint_min_width(self) -> int:
        return self.output_hint_label.fontMetrics().horizontalAdvance(_output_shortcut_hint()) + 28

    def _fit_output_to_text(self, width: int) -> None:
        frame_padding = 18
        text_width = max(80, width - 28 - frame_padding)
        if self._showing_transcript:
            self.transcript.set_text_width(text_width)
            row_height = self.transcript.fontMetrics().lineSpacing()
            cursor = QCursor.pos()
            screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
            bounds = screen.availableGeometry() if screen else QApplication.primaryScreen().availableGeometry()
            max_text_height = max(row_height * 4, bounds.height() - 160)
            text_height = max(row_height + 8, min(self.transcript.content_height() + 4, max_text_height))
            self.transcript.setFixedHeight(int(text_height))
            self.output_frame.setFixedHeight(int(text_height))
            return
        self.output.document().setTextWidth(text_width)
        document_height = self.output.document().size().height()
        row_height = self.output.fontMetrics().lineSpacing()
        vertical_inset = 4 if self.state == CompanionState.THINKING else 0
        self.output.setViewportMargins(0, vertical_inset, 0, vertical_inset)
        if self._expanded_output:
            cursor = QCursor.pos()
            screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
            bounds = screen.availableGeometry() if screen else QApplication.primaryScreen().availableGeometry()
            max_text_height = max(row_height * 6, bounds.height() - 160)
            self.output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        elif self._fit_final_output:
            cursor = QCursor.pos()
            screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
            bounds = screen.availableGeometry() if screen else QApplication.primaryScreen().availableGeometry()
            max_text_height = max(row_height + 8, bounds.height() - 160)
            scrollbar_policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded if document_height + 4 > max_text_height else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            self.output.setVerticalScrollBarPolicy(scrollbar_policy)
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
        self.countdown_ring.move(max(0, self.width() - self.countdown_ring.width() - COUNTDOWN_RING_RIGHT_PADDING), 8)

    def _countdown_reserved_margin(self) -> int:
        return self.countdown_ring.width() + COUNTDOWN_RING_RIGHT_PADDING + COUNTDOWN_RING_TEXT_GAP

    def _inline_final_output_fits(self, text: str) -> bool:
        text_width = self.label.fontMetrics().horizontalAdvance(text.strip())
        return text_width + 16 + self._countdown_reserved_margin() <= self._max_inline_output_width()

    def _max_inline_output_width(self) -> int:
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        bounds = screen.availableGeometry() if screen else QApplication.primaryScreen().availableGeometry()
        return max(140, bounds.width() - 96)

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

    def _set_visual_state(self, state: CompanionState) -> None:
        self._accent_primary, self._accent_secondary = ACCENTS.get(state, ACCENTS[CompanionState.OUTPUT])
        self.countdown_ring.set_accent(self._accent_primary)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        # Keep the companion window fully transparent; child widgets render the text.
        return


def _output_shortcut_hint() -> str:
    if sys.platform == "darwin":
        return "esc hide · ⌘B keep/last"
    if sys.platform.startswith("win"):
        return "esc hide · AltGr+B keep/last"
    return "esc hide"


def _is_inline_final_output(text: str) -> bool:
    stripped = text.strip()
    if not stripped or "\n" in stripped:
        return False
    return not any(marker in stripped for marker in ("`", "*", "_", "#", "[", "]", "<", ">"))
