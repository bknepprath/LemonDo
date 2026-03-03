import math
import random
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEvent,
    QEasingCurve,
    QPoint,
    QPointF,
    QParallelAnimationGroup,
    QRect,
    QRectF,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QScroller,
    QScrollerProperties,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


def lerp_color(start: QColor, end: QColor, t: float) -> QColor:
    """Linearly interpolate between two QColor values."""
    t = max(0.0, min(1.0, t))
    r = int(round(start.red() + (end.red() - start.red()) * t))
    g = int(round(start.green() + (end.green() - start.green()) * t))
    b = int(round(start.blue() + (end.blue() - start.blue()) * t))
    return QColor(r, g, b)


def get_contrast_color(color: QColor | str) -> QColor:
    """Return black or white text color based on perceived luminance."""
    qcolor = QColor(color) if isinstance(color, str) else QColor(color)
    luminance = qcolor.red() * 0.299 + qcolor.green() * 0.587 + qcolor.blue() * 0.114
    return QColor("#111111") if luminance >= 150 else QColor("#F7F7F7")


def minute_of_day(now: datetime) -> int:
    return now.hour * 60 + now.minute


def build_lemon_icon() -> QIcon:
    pix = QPixmap(128, 128)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    font = QFont("Segoe UI Emoji", 86)
    painter.setFont(font)
    painter.setPen(QColor("#F7D24B"))
    painter.drawText(pix.rect(), int(Qt.AlignmentFlag.AlignCenter), "🍋")
    painter.end()
    return QIcon(pix)


@dataclass
class Particle:
    pos: QPointF
    vel: QPointF
    color: QColor
    radius: float
    life: float
    fade_speed: float


class ParticleOverlay(QWidget):
    def __init__(self, owner: "LemonDoWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, event) -> None:
        if not self.owner.particles:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self.owner.pill_path.isEmpty():
            painter.setClipPath(self.owner.pill_path)
        for p in self.owner.particles:
            alpha = int(max(0, min(255, p.life * 255)))
            c = QColor(p.color)
            c.setAlpha(alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c)
            painter.drawEllipse(p.pos, p.radius, p.radius)


class LemonLogoWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        white = QColor(255, 255, 255, int(255 * 0.30))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(white)
        cx = self.width() / 2
        cy = self.height() / 2 + 2
        # Flat minimal body: plain circle.
        body_d = 32.0
        painter.drawEllipse(QRectF(cx - body_d / 2, cy - body_d / 2, body_d, body_d))
        # Detached minimalist leaf.
        leaf_w = 16.0
        leaf_h = 8.0
        leaf_x = cx + 14.0
        leaf_y = cy - 24.0
        painter.drawEllipse(QRectF(leaf_x - leaf_w / 2, leaf_y - leaf_h / 2, leaf_w, leaf_h))


class BirdsEyeGridWidget(QWidget):
    day_hovered = pyqtSignal(object)
    day_selected = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._year = date.today().year
        self._completed_days: set[date] = set()
        self._hover_index: int | None = None
        self._mouse_pos: QPointF | None = None
        self._hover_scale = 1.0
        self._hover_anim: QVariantAnimation | None = None
        self.setMouseTracking(True)

    def set_data(self, year: int, completed_days: set[date]) -> None:
        self._year = year
        self._completed_days = completed_days
        self.update()

    def _grid_metrics(self) -> tuple[int, int, int, int, int, int, int]:
        cols = 19
        rows = 20
        total_days = 365
        pad_x = 12
        pad_y = 10
        gap = 3
        cell_w = max(6, int((self.width() - pad_x * 2 - (cols - 1) * gap) / cols))
        cell_h = max(6, int((self.height() - pad_y * 2 - (rows - 1) * gap) / rows))
        return cols, rows, total_days, pad_x, pad_y, gap, min(cell_w, cell_h)

    def _animate_hover_scale(self, target: float) -> None:
        if self._hover_anim is not None and self._hover_anim.state() == QAbstractAnimation.State.Running:
            self._hover_anim.stop()
        anim = QVariantAnimation(self)
        anim.setDuration(140)
        anim.setStartValue(float(self._hover_scale))
        anim.setEndValue(float(target))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: setattr(self, "_hover_scale", float(v)))
        anim.valueChanged.connect(lambda _v: self.update())
        self._hover_anim = anim
        anim.start()

    def _index_at_pos(self, pos: QPointF) -> int | None:
        cols, _rows, total_days, pad_x, pad_y, gap, cell = self._grid_metrics()
        x = pos.x() - pad_x
        y = pos.y() - pad_y
        if x < 0 or y < 0:
            return None
        stride = cell + gap
        c = int(x // stride)
        r = int(y // stride)
        if c < 0 or c >= cols or r < 0:
            return None
        in_cell_x = x - c * stride
        in_cell_y = y - r * stride
        if in_cell_x > cell or in_cell_y > cell:
            return None
        idx = r * cols + c
        if idx < 0 or idx >= total_days:
            return None
        return idx

    def _date_for_index(self, idx: int | None) -> date | None:
        if idx is None:
            return None
        return date(self._year, 1, 1) + timedelta(days=idx)

    def mouseMoveEvent(self, event) -> None:
        self._mouse_pos = event.position()
        idx = self._index_at_pos(event.position())
        if idx != self._hover_index:
            self._hover_index = idx
            self._animate_hover_scale(1.32 if idx is not None else 1.0)
            self.day_hovered.emit(self._date_for_index(idx))
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._mouse_pos = None
        self._hover_index = None
        self._animate_hover_scale(1.0)
        self.day_hovered.emit(None)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._index_at_pos(event.position())
            target = self._date_for_index(idx)
            if target is not None:
                self.day_selected.emit(target)
                event.accept()
                return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        cols, _rows, total_days, pad_x, pad_y, gap, cell = self._grid_metrics()
        year_start = date(self._year, 1, 1)

        for idx in range(total_days):
            r = idx // cols
            c = idx % cols
            x = float(pad_x + c * (cell + gap))
            y = float(pad_y + r * (cell + gap))
            if self._mouse_pos is not None and idx != self._hover_index:
                center_x = x + cell / 2
                center_y = y + cell / 2
                dx = center_x - self._mouse_pos.x()
                dy = center_y - self._mouse_pos.y()
                dist = max(1.0, math.hypot(dx, dy))
                # Wider influence radius + smoother falloff for eye-pleasing motion.
                influence_radius = 320.0
                if dist < influence_radius:
                    t = (influence_radius - dist) / influence_radius
                    repel = 6.0 * (t ** 1.35)
                    x += (dx / dist) * repel
                    y += (dy / dist) * repel
            size = float(cell)
            if idx == self._hover_index:
                size = float(cell) * float(self._hover_scale)
                x -= (size - cell) / 2.0
                y -= (size - cell) / 2.0
            rect = QRectF(x, y, size, size)
            day_value = year_start + timedelta(days=idx)
            if day_value in self._completed_days:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#000000"))
                painter.drawRect(rect)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#000000"), 1.0))
                painter.drawRect(rect)


class FocusOverlay(QWidget):
    long_pressed = pyqtSignal()

    def __init__(self, owner: "LemonDoWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgb(0, 0, 0);")
        self._press_global: QPoint | None = None
        self._moved = False
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(500)
        self._long_press_timer.timeout.connect(self._emit_long_press)

    def _emit_long_press(self) -> None:
        if self._press_global is not None and not self._moved:
            self.long_pressed.emit()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._moved = False
            self._long_press_timer.start()
            self.owner._drag_offset = event.globalPosition().toPoint() - self.owner.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._press_global is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            current = event.globalPosition().toPoint()
            if (current - self._press_global).manhattanLength() > 8:
                self._moved = True
            if self.owner._drag_offset is not None:
                self.owner.move(current - self.owner._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._long_press_timer.stop()
            self._press_global = None
            self._moved = False
            self.owner._drag_offset = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.owner.enter_hibernate()
        event.accept()


class StripeTextEdit(QTextEdit):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    tab_move_requested = pyqtSignal(int)
    mouse_pressed = pyqtSignal(object)
    mouse_released = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setPlaceholderText("")

    def mousePressEvent(self, event) -> None:
        self.mouse_pressed.emit(event.button())
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.mouse_released.emit(event.button())
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Tab:
            self.tab_move_requested.emit(1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Backtab:
            self.tab_move_requested.emit(-1)
            event.accept()
            return
        super().keyPressEvent(event)


class TaskStripe(QWidget):
    EMPTY = "EMPTY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

    completed = pyqtSignal(QPoint)
    height_changed = pyqtSignal()
    state_changed = pyqtSignal()
    focus_move_requested = pyqtSignal(object, int)
    completed_clicked = pyqtSignal(object)
    delete_requested = pyqtSignal(object)
    long_pressed = pyqtSignal(object)
    focus_complete_requested = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(68)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.state = self.EMPTY
        self.task_text = ""
        self.completion_rank: int | None = None
        self.completion_fade = 1.0
        self._anim_group: QSequentialAnimationGroup | None = None
        self._base_color = QColor("#1A237E")
        self._placeholder_color = QColor(255, 255, 255, 150)
        self._is_hovered = False
        self._shadow_effect: QGraphicsDropShadowEffect | None = None
        self._opacity_effect: QGraphicsOpacityEffect | None = None
        self.is_deleting = False
        self.deletion_progress = 0.0
        self._focus_mode = False
        self._focus_dimmed = False
        self._focus_blackout = 0.0
        self._long_press_armed = False
        self._long_press_triggered = False
        self._pending_click_edit = False

        self.editor = StripeTextEdit(self)
        self.editor.setReadOnly(False)
        self.editor.clicked.connect(self._on_click_inside)
        self.editor.double_clicked.connect(self._on_double_click_inside)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.tab_move_requested.connect(self._on_tab_move_requested)
        self.editor.setMouseTracking(True)
        self.editor.mouse_pressed.connect(self._on_editor_mouse_pressed)
        self.editor.mouse_released.connect(self._on_editor_mouse_released)

        self.focus_label = QLabel(self)
        self.focus_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.focus_label.setWordWrap(True)
        self.focus_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.focus_label.setVisible(False)
        self.focus_blackout_cover = QWidget(self)
        self.focus_blackout_cover.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.focus_blackout_cover.setStyleSheet("background-color: rgba(0, 0, 0, 0);")
        self.focus_blackout_cover.setVisible(False)

        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(500)
        self._long_press_timer.timeout.connect(self._emit_long_press)
        self.check_button = QPushButton("✓", self)
        self.check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_button.setFixedSize(30, 30)
        self.check_button.setVisible(False)
        self.check_button.clicked.connect(self._on_check_clicked)

        self.trash_button = QPushButton("✕", self)
        self.trash_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trash_button.setFixedSize(28, 28)
        self.trash_button.setVisible(False)
        self.trash_button.clicked.connect(self._on_delete_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(6)
        layout.addWidget(self.editor)
        layout.addWidget(self.focus_label)
        layout.addWidget(self.check_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.trash_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.apply_theme(self._base_color)
        self._sync_state_with_text()
        self._adjust_height_to_content()

    def mousePressEvent(self, event) -> None:
        if self._focus_mode and event.button() == Qt.MouseButton.LeftButton and self.state == self.ACTIVE:
            self.focus_complete_requested.emit(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.focus_blackout_cover.setGeometry(self.rect())
        if self.focus_blackout_cover.isVisible():
            self.focus_blackout_cover.raise_()
        self._adjust_height_to_content()

    def _on_click_inside(self) -> None:
        if self.state == self.COMPLETED:
            self.completed_clicked.emit(self)
            return
        if self._long_press_armed:
            self._pending_click_edit = True
            return
        self._begin_inline_edit()

    def _on_double_click_inside(self) -> None:
        if self.state == self.COMPLETED:
            self.completed_clicked.emit(self)
            return
        self._begin_inline_edit()

    def _on_check_clicked(self) -> None:
        self.set_completed()

    def _on_delete_clicked(self) -> None:
        if self.is_deleting:
            return
        self.delete_requested.emit(self)

    def _on_editor_mouse_pressed(self, button) -> None:
        if button == Qt.MouseButton.LeftButton and self.state != self.COMPLETED:
            self._long_press_armed = True
            self._long_press_triggered = False
            self._pending_click_edit = False
            self._long_press_timer.start()

    def _on_editor_mouse_released(self, button) -> None:
        if button == Qt.MouseButton.LeftButton:
            self._long_press_armed = False
            self._long_press_timer.stop()
            if self._pending_click_edit and not self._long_press_triggered and not self._focus_mode:
                self._begin_inline_edit()
            self._pending_click_edit = False

    def _emit_long_press(self) -> None:
        if not self._long_press_armed:
            return
        if self.state == self.COMPLETED or self.is_deleting:
            return
        self._long_press_triggered = True
        self._pending_click_edit = False
        self.long_pressed.emit(self)

    def _begin_inline_edit(self) -> None:
        if self.state == self.COMPLETED:
            return
        self.editor.setReadOnly(False)
        self.editor.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)

    def focus_for_input(self) -> None:
        self._begin_inline_edit()

    def _on_text_changed(self) -> None:
        self._sync_state_with_text()
        self.apply_theme(self._base_color)
        self._adjust_height_to_content()

    def _on_tab_move_requested(self, direction: int) -> None:
        self.focus_move_requested.emit(self, direction)

    def _sync_state_with_text(self) -> None:
        if self.state == self.COMPLETED:
            return
        previous_state = self.state
        text = self.editor.toPlainText()
        stripped = text.strip()
        self.state = self.ACTIVE if stripped else self.EMPTY
        self.task_text = stripped
        self.editor.setPlaceholderText("")
        self._update_check_visibility()
        if self.state != previous_state:
            self.state_changed.emit()

    def _adjust_height_to_content(self) -> None:
        margins = self.layout().contentsMargins()
        document_height = max(24.0, self.editor.document().size().height())
        target = max(68, int(math.ceil(document_height)) + margins.top() + margins.bottom() + 10)
        if target != self.height():
            self.setFixedHeight(target)
            self.height_changed.emit()

    def set_completed(self) -> None:
        if self.state != self.ACTIVE:
            return
        self.raise_()
        self.state = self.COMPLETED
        self.completion_fade = 0.0
        self.editor.setReadOnly(True)
        self.apply_theme(self._base_color)
        self._update_check_visibility()
        global_center = self.mapToGlobal(self.rect().center())
        self.completed.emit(global_center)
        self.state_changed.emit()

    def reopen_from_completed(self) -> None:
        if self.state != self.COMPLETED:
            return
        self.state = self.ACTIVE
        self.completion_rank = None
        self.completion_fade = 0.0
        self.editor.setReadOnly(False)
        self.editor.setFocus(Qt.FocusReason.MouseFocusReason)
        self.apply_theme(self._base_color)
        self._update_check_visibility()
        self.state_changed.emit()

    def reset_slot(self) -> None:
        self.state = self.EMPTY
        self.completion_fade = 1.0
        self.task_text = ""
        self.editor.clear()
        self.editor.setReadOnly(False)
        self.editor.setPlaceholderText("")
        self.editor.setFocus(Qt.FocusReason.MouseFocusReason)
        self.apply_theme(self._base_color)
        self._update_check_visibility()
        self._adjust_height_to_content()
        self.state_changed.emit()

    def load_state(self, text: str, status: str, completion_rank: int | None = None) -> None:
        self.editor.blockSignals(True)
        self.editor.setPlainText(text or "")
        self.editor.blockSignals(False)
        self.task_text = (text or "").strip()
        if status == self.COMPLETED and self.task_text:
            self.state = self.COMPLETED
            self.completion_rank = completion_rank
            self.completion_fade = 1.0
            self.editor.setReadOnly(True)
        else:
            self.state = self.ACTIVE if self.task_text else self.EMPTY
            self.completion_rank = None
            self.completion_fade = 0.0
            self.editor.setReadOnly(False)
        self._update_check_visibility()
        self._adjust_height_to_content()

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._update_check_visibility()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._update_check_visibility()
        super().leaveEvent(event)

    def _update_check_visibility(self) -> None:
        if self.is_deleting:
            self.check_button.setVisible(False)
            self.trash_button.setVisible(False)
            return
        if self._focus_mode:
            self.check_button.setVisible(False)
            self.trash_button.setVisible(False)
            return
        show_check = self._is_hovered and self.state == self.ACTIVE
        show_delete = self._is_hovered
        self.check_button.setVisible(show_check)
        self.trash_button.setVisible(show_delete)

    def begin_delete_visual(self) -> None:
        self.is_deleting = True
        self.set_focus_mode(False)
        self.editor.setReadOnly(True)
        self.editor.setCursor(Qt.CursorShape.ForbiddenCursor)
        self._update_check_visibility()
        if self._opacity_effect is None:
            self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

    def set_delete_progress(self, progress: float) -> None:
        self.deletion_progress = max(0.0, min(1.0, progress))
        self.apply_theme(self._base_color)

    def set_delete_opacity(self, opacity: float) -> None:
        if self._opacity_effect is None:
            self._opacity_effect = QGraphicsOpacityEffect(self)
            self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(max(0.0, min(1.0, opacity)))

    def clear_delete_visual(self) -> None:
        self.is_deleting = False
        self.deletion_progress = 0.0
        self.setGraphicsEffect(None)
        self._update_check_visibility()

    def set_focus_mode(self, enabled: bool) -> None:
        self._focus_mode = enabled
        if enabled:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.set_focus_blackout(0.0)
            self.editor.clearFocus()
            self.editor.setReadOnly(True)
            self.editor.hide()
            self.check_button.hide()
            self.trash_button.hide()
            self.focus_label.setText(self.editor.toPlainText())
            self.focus_label.show()
        else:
            self.setCursor(Qt.CursorShape.IBeamCursor)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self.focus_label.hide()
            self.editor.show()
            self.editor.setReadOnly(self.state == self.COMPLETED)
            self._update_check_visibility()
        self.update()

    def set_focus_dimmed(self, enabled: bool) -> None:
        self._focus_dimmed = enabled
        self._focus_blackout = 1.0 if enabled else 0.0
        self.update()

    def set_focus_blackout(self, value: float) -> None:
        self._focus_blackout = max(0.0, min(1.0, float(value)))
        alpha = int(255 * self._focus_blackout)
        if alpha <= 0:
            self.focus_blackout_cover.hide()
        else:
            self.focus_blackout_cover.setStyleSheet(f"background-color: rgba(0, 0, 0, {alpha});")
            self.focus_blackout_cover.setGeometry(self.rect())
            self.focus_blackout_cover.show()
            self.focus_blackout_cover.raise_()
        self.update()

    def apply_theme(self, base_color: QColor) -> None:
        self._base_color = QColor(base_color)
        if self._focus_mode:
            self.setStyleSheet("background-color: transparent; border: none;")
            text_color = get_contrast_color(QColor("#000000"))
            self.focus_label.setStyleSheet(
                "QLabel {"
                f"color: rgb({text_color.red()}, {text_color.green()}, {text_color.blue()});"
                "font-size: 20px;"
                "font-weight: 700;"
                "padding: 0px;"
                "background: transparent;"
                "border: none;"
                "}"
            )
            return
        if self.is_deleting:
            deep_red = QColor("#6B1111")
            mixed = lerp_color(QColor(self._base_color), deep_red, self.deletion_progress)
            frame_css = (
                f"background-color: rgb({mixed.red()}, {mixed.green()}, {mixed.blue()});"
                "border-radius: 0px; border: 1px solid rgba(255, 120, 120, 70);"
            )
            text_color = QColor("#F7E9E9")
            self.setStyleSheet(frame_css)
            self.editor.setStyleSheet(
                "QTextEdit {"
                "background: transparent;"
                "border: none;"
                f"color: rgb({text_color.red()}, {text_color.green()}, {text_color.blue()});"
                f"selection-background-color: rgba({text_color.red()}, {text_color.green()}, {text_color.blue()}, 58);"
                "font-size: 18px;"
                "font-weight: 600;"
                "}"
            )
            return
        if self.state == self.COMPLETED:
            p = max(0.0, min(1.0, self.completion_fade))
            completed_bg = QColor("#565656")
            mixed = lerp_color(QColor(self._base_color), completed_bg, p)
            text_color = QColor("#E8E8E8")
            frame_css = (
                f"background-color: rgb({mixed.red()}, {mixed.green()}, {mixed.blue()});"
                "border-radius: 0px; border: 1px solid rgba(220, 220, 220, 28);"
            )
            font = QFont(self.editor.font())
            font.setStrikeOut(False)
            font.setItalic(False)
            self.editor.setFont(font)
            self.editor.setCursor(Qt.CursorShape.ForbiddenCursor)
            self._placeholder_color = QColor(210, 210, 210, 90)
            try:
                if self._shadow_effect is None:
                    raise RuntimeError("missing shadow")
                _ = self._shadow_effect.blurRadius()
            except Exception:
                self._shadow_effect = QGraphicsDropShadowEffect(self)
            self._shadow_effect.setOffset(0, 2)
            self._shadow_effect.setBlurRadius(9)
            self._shadow_effect.setColor(QColor(0, 0, 0, 90))
            self.setGraphicsEffect(self._shadow_effect)
        else:
            text_color = get_contrast_color(self._base_color)
            stripe_bg = QColor(self._base_color)
            if self._is_hovered and not self.editor.hasFocus():
                stripe_bg = lerp_color(stripe_bg, QColor("#FFFFFF"), 0.12)
            frame_css = (
                f"background-color: rgb({stripe_bg.red()}, {stripe_bg.green()}, {stripe_bg.blue()});"
                "border-radius: 0px;"
                "border: 1px solid rgba(255, 255, 255, 32);"
            )
            font = QFont(self.editor.font())
            font.setStrikeOut(False)
            font.setItalic(self.state == self.EMPTY)
            self.editor.setFont(font)
            self.editor.setCursor(Qt.CursorShape.IBeamCursor)
            self._placeholder_color = QColor(text_color.red(), text_color.green(), text_color.blue(), 140)
            if not self._focus_mode:
                self.setGraphicsEffect(None)

        self.setStyleSheet(frame_css)
        ph = self._placeholder_color
        check_text = get_contrast_color(self._base_color)
        self.check_button.setStyleSheet(
            "QPushButton {"
            "background-color: rgba(0, 0, 0, 35);"
            f"color: rgb({check_text.red()}, {check_text.green()}, {check_text.blue()});"
            "border: 1px solid rgba(255, 255, 255, 45);"
            "border-radius: 15px;"
            "font-size: 18px;"
            "font-weight: 700;"
            "padding-bottom: 1px;"
            "}"
            "QPushButton:hover {"
            "background-color: rgba(255, 255, 255, 55);"
            "}"
        )
        self.trash_button.setStyleSheet(
            "QPushButton {"
            "background-color: rgba(0, 0, 0, 28);"
            f"color: rgb({check_text.red()}, {check_text.green()}, {check_text.blue()});"
            "border: 1px solid rgba(255, 255, 255, 40);"
            "border-radius: 14px;"
            "font-size: 14px;"
            "font-weight: 700;"
            "padding: 0px;"
            "}"
            "QPushButton:hover {"
            "background-color: rgba(255, 88, 88, 118);"
            "}"
        )
        self.editor.setStyleSheet(
            "QTextEdit {"
            "background: transparent;"
            "border: none;"
            f"color: rgb({text_color.red()}, {text_color.green()}, {text_color.blue()});"
            f"selection-background-color: rgba({text_color.red()}, {text_color.green()}, {text_color.blue()}, 58);"
            "font-size: 18px;"
            "font-weight: 600;"
            "}"
            "QTextEdit::placeholder {"
            f"color: rgba({ph.red()}, {ph.green()}, {ph.blue()}, {ph.alpha()});"
            "}"
        )
        self.focus_label.setStyleSheet(
            "QLabel {"
            f"color: rgb({text_color.red()}, {text_color.green()}, {text_color.blue()});"
            "font-size: 20px;"
            "font-weight: 700;"
            "padding: 0px;"
            "}"
        )

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        # Blackout in focus mode is handled by focus_blackout_cover.

    def play_bounce_animation(self) -> None:
        original = self.geometry()
        shrink_w = int(original.width() * 0.97)
        shrink_h = int(original.height() * 0.9)
        shrink_rect = original.adjusted(
            (original.width() - shrink_w) // 2,
            (original.height() - shrink_h) // 2,
            -(original.width() - shrink_w) // 2,
            -(original.height() - shrink_h) // 2,
        )

        anim_down = QPropertyAnimation(self, b"geometry")
        anim_down.setDuration(80)
        anim_down.setStartValue(original)
        anim_down.setEndValue(shrink_rect)
        anim_down.setEasingCurve(QEasingCurve.Type.InOutQuad)

        anim_up = QPropertyAnimation(self, b"geometry")
        anim_up.setDuration(180)
        anim_up.setStartValue(shrink_rect)
        anim_up.setEndValue(original)
        anim_up.setEasingCurve(QEasingCurve.Type.OutBounce)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(anim_down)
        group.addAnimation(anim_up)
        self._anim_group = group
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


class FullTaskStripe(QFrame):
    """Compact task item for the 'Full Task' view."""
    completed = pyqtSignal(object)  # Emits self
    bumped = pyqtSignal(object)     # Emits self
    priority_changed = pyqtSignal(object) # Emits self
    drag_started = pyqtSignal(object, QPoint) # Emits self, local_pos

    def __init__(self, task_data: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task_data = task_data
        self.setFixedHeight(46)
        self.setMouseTracking(True)
        self._base_color = QColor("#FAEE69")
        self._is_dragging = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)

        # Check button
        self.check_button = QPushButton("○", self)
        self.check_button.setFixedSize(26, 26)
        self.check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_button.clicked.connect(lambda: self.completed.emit(self))
        layout.addWidget(self.check_button)

        # Content: Date + Text
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(0)
        
        self.date_label = QLabel(task_data.get("day", ""), self)
        self.date_label.setStyleSheet("font-size: 9px; font-weight: 800; opacity: 0.7;")
        self.content_layout.addWidget(self.date_label)

        self.text_label = QLabel(task_data.get("text", ""), self)
        self.text_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.content_layout.addWidget(self.text_label)
        layout.addLayout(self.content_layout, 1)

        # Stars
        self.stars_layout = QHBoxLayout()
        self.stars_layout.setSpacing(2)
        self.star_buttons = []
        for i in range(1, 4):
            btn = QPushButton("★", self)
            btn.setFixedSize(20, 20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, idx=i: self._set_priority(idx))
            self.stars_layout.addWidget(btn)
            self.star_buttons.append(btn)
        layout.addLayout(self.stars_layout)

        # Bump button
        self.bump_button = QPushButton("→", self)
        self.bump_button.setFixedSize(26, 26)
        self.bump_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bump_button.setToolTip("Move to tomorrow")
        self.bump_button.clicked.connect(lambda: self.bumped.emit(self))
        layout.addWidget(self.bump_button)

        self._refresh_stars()

    def _set_priority(self, p: int) -> None:
        old_p = self.task_data.get("priority", 0)
        if old_p == p:
            self.task_data["priority"] = 0
        else:
            self.task_data["priority"] = p
        self._refresh_stars()
        self.priority_changed.emit(self)

    def _refresh_stars(self) -> None:
        p = self.task_data.get("priority", 0)
        for i, btn in enumerate(self.star_buttons):
            if (i + 1) <= p:
                btn.setStyleSheet("color: #FFD700; background: transparent; border: none; font-size: 16px;")
            else:
                btn.setStyleSheet("color: rgba(255, 255, 255, 40); background: transparent; border: none; font-size: 16px;")

    def apply_theme(self, base_color: QColor) -> None:
        self._base_color = base_color
        text_color = get_contrast_color(base_color)
        bg = lerp_color(base_color, QColor("#000000"), 0.05)
        self.setStyleSheet(
            f"FullTaskStripe {{ background-color: rgb({bg.red()}, {bg.green()}, {bg.blue()}); "
            f"border-bottom: 1px solid rgba(255, 255, 255, 20); }}"
        )
        self.text_label.setStyleSheet(f"color: rgb({text_color.red()}, {text_color.green()}, {text_color.blue()}); font-size: 14px; font-weight: 600;")
        self.date_label.setStyleSheet(f"color: rgba({text_color.red()}, {text_color.green()}, {text_color.blue()}, 160); font-size: 9px; font-weight: 800;")
        
        btn_style = (
            "QPushButton {"
            "background-color: rgba(0, 0, 0, 30);"
            f"color: rgb({text_color.red()}, {text_color.green()}, {text_color.blue()});"
            "border: 1px solid rgba(255, 255, 255, 30);"
            "border-radius: 13px;"
            "font-weight: 700;"
            "}"
            "QPushButton:hover { background-color: rgba(255, 255, 255, 40); }"
        )
        self.check_button.setStyleSheet(btn_style)
        self.bump_button.setStyleSheet(btn_style)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started.emit(self, event.pos())
        super().mousePressEvent(event)


class FullTaskOverlay(QWidget):
    """Scrollable list of all outstanding tasks with drag-and-drop reordering."""
    def __init__(self, owner: "LemonDoWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Header area
        self.header = QWidget(self)
        self.header.setFixedHeight(60)
        h_layout = QVBoxLayout(self.header)
        h_layout.setContentsMargins(0, 20, 0, 0)
        self.title_label = QLabel("Outstanding Tasks", self.header)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 24px; font-weight: 800;")
        h_layout.addWidget(self.title_label)
        self.layout.addWidget(self.header)

        # Scroll Area
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        # Enable touch-style kinetic scrolling
        QScroller.grabGesture(self.scroll.viewport(), QScroller.ScrollerGesture.LeftMouseButtonGesture)
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        # We'll use manual positioning for animations, so no layout on container
        
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)

        self.items: list[FullTaskStripe] = []
        self._dragging_item: FullTaskStripe | None = None
        self._drag_start_pos = QPoint()
        self._drag_initial_rect = QRect()
        self._placeholder_index = -1

    def apply_theme(self, base_color: QColor) -> None:
        bg = lerp_color(base_color, QColor("#000000"), 0.1)
        self.setStyleSheet(f"background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 245);")
        text_color = get_contrast_color(base_color)
        self.title_label.setStyleSheet(f"color: rgb({text_color.red()}, {text_color.green()}, {text_color.blue()}); font-size: 24px; font-weight: 800;")
        for item in self.items:
            item.apply_theme(base_color)

    def refresh_tasks(self) -> None:
        # Clear existing
        for item in self.items:
            item.setParent(None)
            item.deleteLater()
        self.items.clear()
        
        # Load from DB
        # Order: priority DESC, sort_index ASC, created_at ASC
        rows = self.owner.db.execute(
            "SELECT day, task_id, status, text, completion_rank, priority, created_at, sort_index "
            "FROM tasks WHERE status = 'ACTIVE' "
            "ORDER BY priority DESC, sort_index ASC, created_at ASC"
        ).fetchall()
        
        for row in rows:
            data = {
                "day": row[0], "task_id": row[1], "status": row[2],
                "text": row[3], "completion_rank": row[4],
                "priority": row[5], "created_at": row[6], "sort_index": row[7]
            }
            item = FullTaskStripe(data, self.container)
            item.completed.connect(self._on_item_completed)
            item.bumped.connect(self._on_item_bumped)
            item.priority_changed.connect(self._on_item_priority_changed)
            item.drag_started.connect(self._on_drag_started)
            item.apply_theme(self.owner.button_color)
            item.setParent(self.container)
            self.items.append(item)
        
        self._update_item_positions(animated=False)

    def _update_item_positions(self, animated: bool = True) -> None:
        margin = 10
        spacing = 4
        y = margin
        for i, item in enumerate(self.items):
            if item == self._dragging_item:
                continue
            
            target_idx = i
            if self._dragging_item and i >= self._placeholder_index:
                target_idx = i + 1
            
            target_y = margin + target_idx * (item.height() + spacing)
            
            if animated:
                if not hasattr(item, "_pos_anim"):
                    item._pos_anim = QPropertyAnimation(item, b"pos")
                
                if item._pos_anim.endValue() != QPoint(20, target_y):
                    item._pos_anim.stop()
                    item._pos_anim.setDuration(200)
                    item._pos_anim.setStartValue(item.pos())
                    item._pos_anim.setEndValue(QPoint(20, target_y))
                    item._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                    item._pos_anim.start()
            else:
                if hasattr(item, "_pos_anim"):
                    item._pos_anim.stop()
                item.move(20, target_y)
            y = target_y + item.height() + spacing
        
        self.container.setMinimumSize(self.width(), y + 60)

    def _on_item_completed(self, item: FullTaskStripe) -> None:
        d = item.task_data
        self.owner.db.execute(
            "UPDATE tasks SET status = 'COMPLETED', completion_rank = ? WHERE day = ? AND task_id = ?",
            (int(time.time()), d["day"], d["task_id"])
        )
        self.owner.db.commit()
        self.owner._full_tasks_dirty = True
        self.refresh_tasks()

    def _on_item_bumped(self, item: FullTaskStripe) -> None:
        d = item.task_data
        curr_date = date.fromisoformat(d["day"])
        next_date = curr_date + timedelta(days=1)
        next_day_str = next_date.isoformat()
        
        # Find new task_id for that day
        res = self.owner.db.execute("SELECT MAX(task_id) FROM tasks WHERE day = ?", (next_day_str,)).fetchone()
        new_id = (res[0] or 0) + 1
        
        self.owner.db.execute(
            "UPDATE tasks SET day = ?, task_id = ? WHERE day = ? AND task_id = ?",
            (next_day_str, new_id, d["day"], d["task_id"])
        )
        self.owner.db.commit()
        self.owner._full_tasks_dirty = True
        self.refresh_tasks()

    def _on_item_priority_changed(self, item: FullTaskStripe) -> None:
        d = item.task_data
        self.owner.db.execute(
            "UPDATE tasks SET priority = ? WHERE day = ? AND task_id = ?",
            (d["priority"], d["day"], d["task_id"])
        )
        self.owner.db.commit()
        self.refresh_tasks() # Re-sort

    def _on_drag_started(self, item: FullTaskStripe, local_pos: QPoint) -> None:
        self._dragging_item = item
        self._drag_start_pos = local_pos
        self._drag_initial_rect = item.geometry()
        self._placeholder_index = self.items.index(item)
        item.raise_()
        item.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging_item:
            # Move visually
            container_pos = self.container.mapFrom(self, event.pos())
            target_y = container_pos.y() - self._drag_start_pos.y()
            self._dragging_item.move(self._drag_initial_rect.x(), target_y)
            
            # Find new placeholder index
            new_idx = -1
            mid_y = target_y + self._dragging_item.height() // 2
            for i, other in enumerate(self.items):
                if other == self._dragging_item: continue
                other_mid = other.y() + other.height() // 2
                if mid_y < other_mid:
                    new_idx = i
                    break
            if new_idx == -1:
                new_idx = len(self.items) - 1
            
            if new_idx != self._placeholder_index:
                self._placeholder_index = new_idx
                self._reorder_visuals()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging_item:
            self._dragging_item.setCursor(Qt.CursorShape.PointingHandCursor)
            self._finalize_reorder()
            self._dragging_item = None
        super().mouseReleaseEvent(event)

    def _reorder_visuals(self) -> None:
        self._update_item_positions(animated=True)

    def _finalize_reorder(self) -> None:
        if not self._dragging_item: return
        old_idx = self.items.index(self._dragging_item)
        new_idx = self._placeholder_index
        if old_idx == new_idx:
            self.refresh_tasks()
            return
            
        item = self.items.pop(old_idx)
        self.items.insert(new_idx, item)
        
        # Update sort_index for all items in the same priority group
        # Actually simplest: update all sort_index for all ACTIVE tasks in this priority
        p = item.task_data["priority"]
        affected = [x for x in self.items if x.task_data["priority"] == p]
        for i, itm in enumerate(affected):
            itm.task_data["sort_index"] = i
            self.owner.db.execute(
                "UPDATE tasks SET sort_index = ? WHERE day = ? AND task_id = ?",
                (i, itm.task_data["day"], itm.task_data["task_id"])
            )
        self.owner.db.commit()
        self.refresh_tasks()


class LemonDoWidget(QWidget):
    MORNING_BG = QColor("#FAEE69")          # 04:00 (extended)
    MORNING_BUTTON = QColor("#1A237E")
    AFTERNOON_BG = QColor("#FF9933")        # 15:59
    AFTERNOON_BUTTON = QColor("#0D47A1")    # Navy Blue
    FLIP_BG = QColor("#3C98E8")             # 16:00
    FLIP_BUTTON = QColor("#FF9933")         # 16:00 flip
    EVENING_BG = QColor("#442F72")          # 21:59
    EVENING_BUTTON = QColor("#FCFCDE")      # Cream
    SLEEP_BG = QColor("#000000")

    PALETTES = {
        "yellow": {
            "MORNING_BG": "#FAEE69", "MORNING_BUTTON": "#1A237E",
            "AFTERNOON_BG": "#FF9933", "AFTERNOON_BUTTON": "#0D47A1",
            "FLIP_BG": "#3C98E8", "FLIP_BUTTON": "#FF9933",
            "EVENING_BG": "#442F72", "EVENING_BUTTON": "#FCFCDE"
        },
        "mint": {
            "MORNING_BG": "#B2FFD1", "MORNING_BUTTON": "#004D40",
            "AFTERNOON_BG": "#4DB6AC", "AFTERNOON_BUTTON": "#00695C",
            "FLIP_BG": "#80CBC4", "FLIP_BUTTON": "#004D40",
            "EVENING_BG": "#002B24", "EVENING_BUTTON": "#E0F2F1"
        },
        "maroon": {
            "MORNING_BG": "#E57373", "MORNING_BUTTON": "#4A148C",
            "AFTERNOON_BG": "#800000", "AFTERNOON_BUTTON": "#3E2723",
            "FLIP_BG": "#A52A2A", "FLIP_BUTTON": "#FDD835",
            "EVENING_BG": "#3E2723", "EVENING_BUTTON": "#FFEBEE"
        },
        "grayscale": {
            "MORNING_BG": "#E0E0E0", "MORNING_BUTTON": "#424242",
            "AFTERNOON_BG": "#9E9E9E", "AFTERNOON_BUTTON": "#212121",
            "FLIP_BG": "#BDBDBD", "FLIP_BUTTON": "#212121",
            "EVENING_BG": "#212121", "EVENING_BUTTON": "#F5F5F5"
        }
    }

    def __init__(self, title_font_family: str | None = None) -> None:
        super().__init__()
        self.data_path = Path(__file__).resolve().parent / "lemon_do_history.db"
        self.db = sqlite3.connect(self.data_path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self._ensure_schema()

        self.setWindowTitle("Lemon Do")
        self.setMinimumSize(300, 820)
        self.resize(330, 820)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setWindowIcon(build_lemon_icon())

        # Settings
        self.debug_mode_enabled = False
        self.current_palette = "yellow"

        self.background_color = self.MORNING_BG
        self.button_color = self.MORNING_BUTTON
        self.text_color = QColor("#111111")
        self.sleep_mode = False
        self.pending_sleep_mode = False
        self.time_offset = timedelta(0)
        self.debug_visible = False
        self.add_button_visible = False
        self.title_font_family = title_font_family
        self.current_segment: int | None = None
        self.color_anim: QVariantAnimation | None = None
        self.stack_overlap = 15
        self.stripe_gap = 2
        self.add_button_gap = 8
        self.completed_step = 12
        self._completed_counter = 0
        self._stack_animations: list[QAbstractAnimation] = []
        self._completion_sequence_group: QSequentialAnimationGroup | None = None
        self._window_resize_anim: QPropertyAnimation | None = None
        self._running_animations: list[QAbstractAnimation] = []
        self._animation_targets: dict[QWidget, QRect] = {}
        self._last_layout_targets: dict[TaskStripe, QRect] = {}
        self._last_add_target: QRect | None = None
        self._loading_state = False
        self._accordion_open = False
        self._suppress_state_signal = False
        self.nav_controls_visible = False
        self.zone_separation = 26
        self._animation_epoch = 0
        self._completion_in_progress = False
        self.is_hibernated = False
        self._hibernate_saved_geometry: QRect | None = None
        self._hibernate_hovered = False
        self._hibernate_anim_group: QParallelAnimationGroup | None = None
        self._ui_fade_anims: list[QPropertyAnimation] = []
        self._pre_hibernate_min_size: tuple[int, int] | None = None
        self._focus_mode_active = False
        self._focused_stripe: TaskStripe | None = None
        self._focus_transition_group: QParallelAnimationGroup | None = None
        self._focus_reparented = False
        self._delete_in_progress = False
        self._pending_deletes: list[tuple[float, TaskStripe]] = []
        self._pending_adds: list[tuple[float, TaskStripe]] = []
        self._pending_completions: list[tuple[float, TaskStripe]] = []
        self._delete_queue_timer = QTimer(self)
        self._delete_queue_timer.setSingleShot(True)
        self._delete_queue_timer.timeout.connect(self._process_delete_queue)
        self._action_queue_timer = QTimer(self)
        self._action_queue_timer.setSingleShot(True)
        self._action_queue_timer.timeout.connect(self._process_pending_actions)
        self._hibernate_from_focus = False
        self._hibernate_focus_target: TaskStripe | None = None
        self._wake_overlay_anim: QPropertyAnimation | None = None
        self._overlay_mode: str | None = None
        self._overlay_anim: QPropertyAnimation | None = None
        self._focus_started_at: float | None = None
        self.stat_clicks = 0
        self.stat_tasks_created = 0
        self.stat_tasks_deleted = 0
        self.stat_tasks_completed = 0
        self.stat_focus_seconds = 0.0
        self._last_click_count_time = 0.0
        self._last_click_count_pos = QPoint(-10000, -10000)
        self._day_nav_anim_group: QParallelAnimationGroup | None = None
        self._hibernate_overlay_mode: str | None = None
        self._lifetime_stats_dirty = False
        self._full_tasks_dirty = True
        self.pill_path = QPainterPath()
        self.today_date = self.get_app_time().date()
        self.view_date = self.today_date

        self._drag_offset: QPoint | None = None
        self.particles: list[Particle] = []
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_ui()
        self._position_title()
        self._position_debug_overlay()
        self._setup_shortcuts()
        self._setup_timers()
        self._load_lifetime_stats()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._reset_idle_timer()
        self._load_day(self.view_date)
        self.update_color_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.main_layout = layout
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget(self)
        header.setFixedHeight(0)
        self.title = LemonLogoWidget(self)
        self.title.raise_()

        self.back_button = QPushButton("◀", self)
        self.back_button.setFixedSize(28, 28)
        self.back_button.clicked.connect(lambda _checked=False: self.navigate_days(-1))
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.raise_()

        self.forward_button = QPushButton("▶", self)
        self.forward_button.setFixedSize(28, 28)
        self.forward_button.clicked.connect(lambda _checked=False: self.navigate_days(1))
        self.forward_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forward_button.raise_()

        self.day_label = QLabel(self)
        self.day_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.day_label.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: 0.6px;")
        self.day_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.day_label.raise_()

        self.debug_label = QLabel(self)
        self.debug_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.debug_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.debug_label.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 700;"
            "padding: 4px 10px;"
            "border-radius: 10px;"
            "color: rgb(245, 245, 245);"
            "background-color: rgba(0, 0, 0, 115);"
        )
        self.debug_label.raise_()

        self.sleep_label = QLabel("Go to bed, come back tomorrow.")
        self.sleep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sleep_label.setWordWrap(True)
        self.sleep_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        self.sleep_label.hide()

        self.buttons: list[TaskStripe] = []

        layout.addWidget(header)
        layout.addStretch(1)
        layout.addWidget(self.sleep_label)
        layout.addStretch(1)

        self.stripe_wrapper = QWidget(self)
        self.stripe_wrapper.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.add_task_button = QPushButton("+", self.stripe_wrapper)
        self.add_task_button.setFixedSize(28, 28)
        self.add_task_button.setCursor(Qt.CursorShape.PointingHandCursor)
        plus_font = QFont(self.font().family(), 16)
        plus_font.setBold(True)
        self.add_task_button.setFont(plus_font)
        self.add_task_button.setContentsMargins(0, 0, 0, 0)
        self.add_task_button.clicked.connect(lambda _checked=False: self.add_task_stripe(True))

        layout.addWidget(self.stripe_wrapper)
        layout.addStretch(2)
        layout.addSpacing(36)

        self.particle_overlay = ParticleOverlay(self)
        self.particle_overlay.setGeometry(self.rect())
        self.particle_overlay.raise_()
        self.focus_tint_overlay = FocusOverlay(self)
        self.focus_tint_overlay.setGeometry(self.rect())
        self.focus_tint_overlay.long_pressed.connect(self.exit_focus_mode)
        self.focus_tint_overlay.hide()
        self.wake_overlay = QWidget(self)
        self.wake_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.wake_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.wake_overlay.setGeometry(self.rect())
        self.wake_overlay.hide()
        self.info_overlay = QWidget(self)
        self.info_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.info_overlay.setGeometry(self.rect())
        self.info_overlay.hide()
        self.info_overlay_layout = QVBoxLayout(self.info_overlay)
        self.info_overlay_layout.setContentsMargins(28, 28, 28, 28)
        self.info_overlay_layout.setSpacing(14)
        self.info_overlay_layout.addStretch(1)
        self.info_overlay_title = QLabel(self.info_overlay)
        self.info_overlay_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_overlay_layout.addWidget(self.info_overlay_title)
        self.birds_eye_grid = BirdsEyeGridWidget(self.info_overlay)
        self.birds_eye_grid.setMinimumSize(180, 190)
        self.birds_eye_grid.setVisible(False)
        self.birds_eye_grid.day_hovered.connect(self.on_birds_eye_day_hovered)
        self.birds_eye_grid.day_selected.connect(self.on_birds_eye_day_selected)
        self.info_overlay_layout.addWidget(self.birds_eye_grid, 0, Qt.AlignmentFlag.AlignCenter)
        self.info_overlay_body = QLabel(self.info_overlay)
        self.info_overlay_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_overlay_body.setWordWrap(True)
        self.info_overlay_layout.addWidget(self.info_overlay_body)
        self.info_overlay_layout.addStretch(1)
        self._update_overlay_theme()
        self._position_birds_eye_grid()

        self.full_task_overlay = FullTaskOverlay(self)
        self.full_task_overlay.setGeometry(self.rect())
        self.full_task_overlay.hide()

        self._update_nav_buttons()

    def _setup_timers(self) -> None:
        # Color scheduler: update every minute.
        self.color_timer = QTimer(self)
        self.color_timer.setInterval(60_000)
        self.color_timer.timeout.connect(self.update_color_state)
        self.color_timer.start()

        # Particle engine: run only while particles are active.
        self.particle_timer = QTimer(self)
        self.particle_timer.setInterval(16)
        self.particle_timer.timeout.connect(self.update_particles)
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.setInterval(600_000)
        self.idle_timer.timeout.connect(self.enter_hibernate)
        self.overlay_timer = QTimer(self)
        self.overlay_timer.setInterval(1000)
        self.overlay_timer.timeout.connect(self._refresh_overlay_content)
        self.overlay_timer.start()

    def _setup_shortcuts(self) -> None:
        self.nuke_shortcut = QShortcut(QKeySequence("N"), self)
        self.nuke_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.nuke_shortcut.activated.connect(self.nuke_all_task_data)

    def toggle_history_controls(self) -> None:
        return

    def closeEvent(self, event) -> None:
        self._save_lifetime_stats()
        self._save_current_day()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        try:
            self.db.close()
        except Exception:
            pass
        super().closeEvent(event)

    def _ensure_schema(self) -> None:
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                day TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'COMPLETED', 'EMPTY')),
                text TEXT NOT NULL DEFAULT '',
                completion_rank INTEGER,
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sort_index INTEGER DEFAULT 0,
                PRIMARY KEY (day, task_id)
            )
            """
        )
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_day_status ON tasks(day, status)")
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS app_stats (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 0,
                value_str TEXT
            )
            """
        )
        # Migrations for task priorities and ordering
        try:
            self.db.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            self.db.execute("ALTER TABLE tasks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        try:
            self.db.execute("ALTER TABLE tasks ADD COLUMN sort_index INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        
        # Attempt to add value_str column if it doesn't exist (for existing databases)
        try:
            self.db.execute("ALTER TABLE app_stats ADD COLUMN value_str TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        self.db.commit()

    def _load_lifetime_stats(self) -> None:
        keys = [
            "lifetime_clicks",
            "lifetime_tasks_created",
            "lifetime_tasks_deleted",
            "lifetime_tasks_completed",
        ]
        values: dict[str, int] = {}
        for key in keys:
            row = self.db.execute("SELECT value FROM app_stats WHERE key = ?", (key,)).fetchone()
            if row is None:
                values[key] = 0
            else:
                values[key] = int(row[0])
        self.stat_tasks_completed = values["lifetime_tasks_completed"]

        # Load Settings from DB
        debug_row = self.db.execute("SELECT value FROM app_stats WHERE key = 'settings_debug_mode'").fetchone()
        self.debug_mode_enabled = bool(debug_row[0]) if debug_row else False

        palette_row = self.db.execute("SELECT value_str FROM app_stats WHERE key = 'settings_palette'").fetchone()
        self.current_palette = str(palette_row[0]) if palette_row and palette_row[0] else "yellow"

    def _save_lifetime_stats(self) -> None:
        if not self._lifetime_stats_dirty:
            return
        rows = [
            ("lifetime_clicks", int(self.stat_clicks)),
            ("lifetime_tasks_created", int(self.stat_tasks_created)),
            ("lifetime_tasks_deleted", int(self.stat_tasks_deleted)),
            ("lifetime_tasks_completed", int(self.stat_tasks_completed)),
        ]
        with self.db:
            for key, value in rows:
                self.db.execute(
                    """
                    INSERT INTO app_stats(key, value) VALUES(?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )
            self.db.execute(
                """
                INSERT INTO app_stats(key, value) VALUES('settings_debug_mode', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (int(self.debug_mode_enabled),),
            )
            self.db.execute(
                """
                INSERT INTO app_stats(key, value_str) VALUES('settings_palette', ?)
                ON CONFLICT(key) DO UPDATE SET value_str = excluded.value_str
                """,
                (self.current_palette,),
            )
        self._lifetime_stats_dirty = False

    def _best_completed_day_count(self) -> int:
        row = self.db.execute(
            """
            SELECT MAX(c) FROM (
                SELECT day, COUNT(*) AS c
                FROM tasks
                WHERE status = 'COMPLETED'
                GROUP BY day
            )
            """
        ).fetchone()
        db_best = int(row[0]) if row and row[0] is not None else 0
        current_best = len([b for b in self.buttons if b.state == TaskStripe.COMPLETED and not b.is_deleting])
        return max(db_best, current_best)

    def _collect_day_rows(self) -> list[tuple[int, str, str, int | None]]:
        rows: list[tuple[int, str, str, int | None]] = []
        for idx, stripe in enumerate(self.buttons):
            if stripe.is_deleting:
                continue
            text = stripe.editor.toPlainText()
            rows.append((idx, stripe.state, text, stripe.completion_rank))
        return rows

    def _save_current_day(self) -> None:
        if not hasattr(self, "buttons"):
            return
        day_key = self.view_date.isoformat()
        rows = self._collect_day_rows()
        with self.db:
            self.db.execute("DELETE FROM tasks WHERE day = ?", (day_key,))
            for task_id, status, text, completion_rank in rows:
                self.db.execute(
                    """
                    INSERT INTO tasks(day, task_id, status, text, completion_rank)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (day_key, task_id, status, text, completion_rank),
                )

    def _fetch_day_rows(self, day_value: date) -> list[tuple[int, str, str, int | None]]:
        day_key = day_value.isoformat()
        cur = self.db.execute(
            """
            SELECT task_id, status, text, completion_rank
            FROM tasks
            WHERE day = ?
            ORDER BY task_id ASC
            """,
            (day_key,),
        )
        return [(int(a), str(b), str(c), int(d) if d is not None else None) for a, b, c, d in cur.fetchall()]

    def _clear_all_stripes(self) -> None:
        for stripe in self.buttons:
            stripe.setParent(None)
            stripe.deleteLater()
        self.buttons.clear()

    def _load_day(self, day_value: date) -> None:
        self._interrupt_and_snap_animations()
        rows = self._fetch_day_rows(day_value)
        self._loading_state = True
        self._clear_all_stripes()
        if rows:
            for _task_id, status, text, completion_rank in rows:
                stripe = self._create_task_stripe()
                stripe.load_state(text, status, completion_rank)
                stripe.apply_theme(self.button_color)
        else:
            for _ in range(3):
                stripe = self._create_task_stripe()
                stripe.load_state("", TaskStripe.EMPTY, None)
                stripe.apply_theme(self.button_color)
        self._accordion_open = False
        self._completed_counter = max(
            [b.completion_rank for b in self.buttons if b.completion_rank is not None] + [0]
        ) + 1
        self.view_date = day_value
        self._loading_state = False
        self.relayout_stripes(animated=False)
        self._resize_window_to_fit(animated=False)
        self._update_nav_buttons()

    def _check_for_new_day(self) -> None:
        now_day = self.get_app_time().date()
        if now_day == self.today_date:
            return
        old_today = self.today_date
        if self.view_date == old_today:
            self._save_current_day()
        self.today_date = now_day
        self.db.execute("DELETE FROM tasks WHERE day = ?", (now_day.isoformat(),))
        self.db.commit()
        if self.view_date == old_today:
            self._load_day(now_day)
        self._update_nav_buttons()

    def _navigation_today(self) -> date:
        # Navigation should be anchored to real calendar day, not debug time offset.
        return date.today()

    def _reset_idle_timer(self) -> None:
        if not hasattr(self, "idle_timer"):
            return
        if self.is_hibernated:
            return
        self.idle_timer.start()

    def _handle_tab_hotkey(self) -> bool:
        available = [b for b in self.buttons if b.state != TaskStripe.COMPLETED and not b.is_deleting]
        empty_available = [b for b in available if b.state == TaskStripe.EMPTY]
        if not available:
            self.add_task()
            if self.buttons:
                newest = self.buttons[-1]
                QTimer.singleShot(520, newest.focus_for_input)
            return True
        if not empty_available:
            self.add_task()
            if self.buttons:
                newest = self.buttons[-1]
                QTimer.singleShot(520, newest.focus_for_input)
            return True
        focused = next((b for b in available if b.editor.hasFocus()), None)
        if focused is not None:
            self.on_focus_move_requested(focused, 1)
            return True
        available[0].focus_for_input()
        return True

    def _stripe_from_widget(self, widget: QWidget | None) -> TaskStripe | None:
        current = widget
        while current is not None:
            if isinstance(current, TaskStripe):
                return current
            current = current.parentWidget()
        return None

    def _collapse_accordion_on_non_task_click(self, event) -> None:
        if not self._accordion_open or self._focus_mode_active or self.is_hibernated:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        global_pos = event.globalPosition().toPoint()
        target_widget = QApplication.widgetAt(global_pos)
        stripe = self._stripe_from_widget(target_widget)
        if stripe is None:
            self._set_accordion_open(False, animated=True)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            if self._focus_mode_active:
                if event.key() == Qt.Key.Key_Escape:
                    self.close()
                event.accept()
                return True
            self._reset_idle_timer()
            if event.key() == Qt.Key.Key_Left:
                self.navigate_days(-1)
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Right:
                self.navigate_days(1)
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Up:
                if self.debug_mode_enabled:
                    self.time_offset += timedelta(minutes=10)
                    self.update_color_state()
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Down:
                if self.debug_mode_enabled:
                    self.time_offset -= timedelta(minutes=10)
                    self.update_color_state()
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Tab:
                if self._handle_tab_hotkey():
                    event.accept()
                    return True
            if event.key() == Qt.Key.Key_F:
                self._toggle_overlay_mode("full_tasks")
                event.accept()
                return True
        elif event.type() == QEvent.Type.MouseButtonPress:
            self._reset_idle_timer()
            if (
                isinstance(obj, QWidget)
                and (obj is self or self.isAncestorOf(obj))
                and event.button() == Qt.MouseButton.LeftButton
            ):
                now_mono = time.monotonic()
                click_pos = event.globalPosition().toPoint()
                if (
                    now_mono - self._last_click_count_time > 0.08
                    or (click_pos - self._last_click_count_pos).manhattanLength() > 4
                ):
                    self.stat_clicks += 1
                    self._lifetime_stats_dirty = True
                    self._last_click_count_time = now_mono
                    self._last_click_count_pos = click_pos
            self._collapse_accordion_on_non_task_click(event)
        elif event.type() in {QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress}:
            self._reset_idle_timer()
            if self.is_hibernated and self._hibernate_hovered:
                if not self.geometry().contains(QCursor.pos()):
                    self._hibernate_hovered = False
                    self._animate_hibernate_hover(self._hibernate_target_geometry(), 0.2, 100)
        return super().eventFilter(obj, event)

    def navigate_days(self, delta: int) -> None:
        if self.is_hibernated or self._focus_mode_active:
            return
        target = self.view_date + timedelta(days=delta)
        nav_today = self._navigation_today()
        if target > nav_today:
            target = nav_today
        if target == self.view_date:
            return
        if self._overlay_mode is not None:
            self._set_overlay_mode(None, animated=False)
        self._interrupt_and_snap_animations()
        self._save_current_day()
        self._animate_day_navigation(target, delta)

    def _animate_day_navigation(self, target: date, delta: int) -> None:
        if self._day_nav_anim_group and self._day_nav_anim_group.state() == QAbstractAnimation.State.Running:
            self._day_nav_anim_group.stop()
        self.stripe_wrapper.setGraphicsEffect(None)
        if not self.stripe_wrapper.isVisible():
            self._load_day(target)
            return
        shift = max(42, int(self.width() * 0.18))
        out_dx = shift if delta < 0 else -shift
        in_dx = -out_dx
        start_pos = self.stripe_wrapper.pos()
        out_pos = QPoint(start_pos.x() + out_dx, start_pos.y())
        effect = self._ensure_opacity_effect(self.stripe_wrapper)
        effect.setOpacity(1.0)

        out_move = QPropertyAnimation(self.stripe_wrapper, b"pos", self)
        out_move.setDuration(150)
        out_move.setStartValue(start_pos)
        out_move.setEndValue(out_pos)
        out_move.setEasingCurve(QEasingCurve.Type.OutCubic)
        out_fade = QPropertyAnimation(effect, b"opacity", self)
        out_fade.setDuration(150)
        out_fade.setStartValue(1.0)
        out_fade.setEndValue(0.0)
        out_fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        out_group = QParallelAnimationGroup(self)
        out_group.addAnimation(out_move)
        out_group.addAnimation(out_fade)

        def animate_in() -> None:
            self._load_day(target)
            final_pos = self.stripe_wrapper.pos()
            self.stripe_wrapper.move(final_pos + QPoint(in_dx, 0))
            effect_in = self._ensure_opacity_effect(self.stripe_wrapper)
            effect_in.setOpacity(0.0)
            in_move = QPropertyAnimation(self.stripe_wrapper, b"pos", self)
            in_move.setDuration(190)
            in_move.setStartValue(self.stripe_wrapper.pos())
            in_move.setEndValue(final_pos)
            in_move.setEasingCurve(QEasingCurve.Type.OutCubic)
            in_fade = QPropertyAnimation(effect_in, b"opacity", self)
            in_fade.setDuration(190)
            in_fade.setStartValue(0.0)
            in_fade.setEndValue(1.0)
            in_fade.setEasingCurve(QEasingCurve.Type.OutCubic)
            in_group = QParallelAnimationGroup(self)
            in_group.addAnimation(in_move)
            in_group.addAnimation(in_fade)
            def cleanup_in() -> None:
                self.stripe_wrapper.move(final_pos)
                if self.stripe_wrapper.graphicsEffect() is effect_in:
                    self.stripe_wrapper.setGraphicsEffect(None)
            in_group.finished.connect(cleanup_in)
            self._day_nav_anim_group = in_group
            in_group.start()

        out_group.finished.connect(animate_in)
        self._day_nav_anim_group = out_group
        out_group.start()

    def _update_nav_buttons(self) -> None:
        if not hasattr(self, "back_button"):
            return
        if self.is_hibernated:
            self.back_button.hide()
            self.forward_button.hide()
            self.day_label.hide()
            return
        nav_today = self._navigation_today()
        self.back_button.setEnabled(True)
        self.forward_button.setEnabled(self.view_date < nav_today)
        self.back_button.hide()
        self.forward_button.hide()
        show_today_label = self.view_date < nav_today
        self.day_label.setVisible(show_today_label)
        self.day_label.setText(self.view_date.strftime("%b %d"))

    def _register_animation(self, animation: QAbstractAnimation, target_widget: QWidget | None = None, end_rect: QRect | None = None) -> None:
        self._running_animations.append(animation)
        if target_widget is not None and end_rect is not None:
            self._animation_targets[target_widget] = QRect(end_rect)
        animation.finished.connect(lambda: self._remove_animation(animation))

    def _remove_animation(self, animation: QAbstractAnimation) -> None:
        if animation in self._running_animations:
            self._running_animations.remove(animation)

    def _compute_animation_bounds(self, targets: dict[TaskStripe, QRect], add_target: QRect | None, base_height: int) -> int:
        current_bottom = 0
        for stripe in self.buttons:
            try:
                if stripe.is_deleting:
                    continue
                rect = stripe.geometry()
                current_bottom = max(current_bottom, rect.y() + rect.height())
            except RuntimeError:
                continue
        target_bottom = 0
        for rect in targets.values():
            target_bottom = max(target_bottom, rect.y() + rect.height())
        add_bottom = 0
        try:
            if self.add_task_button.isVisible():
                add_bottom = max(add_bottom, self.add_task_button.geometry().y() + self.add_task_button.height())
        except RuntimeError:
            pass
        if add_target is not None:
            add_bottom = max(add_bottom, add_target.y() + add_target.height())
        return max(base_height, current_bottom + 8, target_bottom + 8, add_bottom + 8)

    def _interrupt_and_snap_animations(self) -> None:
        has_running = False
        if self.color_anim is not None and self.color_anim.state() == QAbstractAnimation.State.Running:
            has_running = True
        if self._window_resize_anim and self._window_resize_anim.state() == QAbstractAnimation.State.Running:
            has_running = True
        if self._completion_sequence_group and self._completion_sequence_group.state() == QAbstractAnimation.State.Running:
            has_running = True
        if self._day_nav_anim_group and self._day_nav_anim_group.state() == QAbstractAnimation.State.Running:
            has_running = True
        for anim in list(self._running_animations):
            if anim.state() == QAbstractAnimation.State.Running:
                has_running = True
                break
        if not has_running:
            if hasattr(self, "add_task_button"):
                self.add_task_button.setEnabled(True)
            return

        self._animation_epoch += 1
        if self.color_anim is not None and self.color_anim.state() == QAbstractAnimation.State.Running:
            self.color_anim.stop()
        if self._window_resize_anim and self._window_resize_anim.state() == QAbstractAnimation.State.Running:
            self._window_resize_anim.stop()
        if self._completion_sequence_group and self._completion_sequence_group.state() == QAbstractAnimation.State.Running:
            self._completion_sequence_group.stop()
        if self._day_nav_anim_group and self._day_nav_anim_group.state() == QAbstractAnimation.State.Running:
            self._day_nav_anim_group.stop()
        for anim in list(self._running_animations):
            try:
                anim.stop()
            except Exception:
                pass
        for widget, rect in list(self._animation_targets.items()):
            try:
                if widget is not None and widget.parent() is not None:
                    widget.setGeometry(rect)
            except RuntimeError:
                continue
        if self._last_layout_targets:
            for stripe, target in self._last_layout_targets.items():
                try:
                    if stripe.parent() is not None:
                        stripe.setGeometry(target)
                except RuntimeError:
                    continue
        if self._last_add_target is not None:
            try:
                if self.add_task_button.parent() is not None:
                    self.add_task_button.setGeometry(self._last_add_target)
                    self.add_task_button.raise_()
            except RuntimeError:
                pass
        for stripe in self.buttons:
            try:
                if stripe.is_deleting:
                    stripe.clear_delete_visual()
                    stripe.apply_theme(self.button_color)
                stripe.set_focus_dimmed(False)
                stripe.set_focus_mode(False)
                if stripe.state == TaskStripe.COMPLETED:
                    stripe.completion_fade = 1.0
                    stripe.apply_theme(self.button_color)
            except RuntimeError:
                continue
        self._running_animations.clear()
        self._animation_targets.clear()
        self._pending_deletes.clear()
        self._pending_adds.clear()
        self._pending_completions.clear()
        if self._delete_queue_timer.isActive():
            self._delete_queue_timer.stop()
        if self._action_queue_timer.isActive():
            self._action_queue_timer.stop()
        if hasattr(self, "add_task_button"):
            self.add_task_button.setEnabled(True)
        self._delete_in_progress = False
        self._completion_in_progress = False
        self.stripe_wrapper.setGraphicsEffect(None)
        self.main_layout.setEnabled(True)
        self.main_layout.activate()

    def _hibernate_target_geometry(self) -> QRect:
        screen = QApplication.primaryScreen()
        if screen is None:
            return QRect(max(0, self.x()), max(0, self.y()), 38, 30)
        # Use availableGeometry so we stay above taskbar/docks.
        area = screen.availableGeometry()
        w = 38
        h = 30
        right_margin = int(area.width() * 0.025)
        bottom_margin = int(area.height() * 0.12)
        x = area.right() - w - right_margin + 1
        y = area.bottom() - h - bottom_margin + 1
        return QRect(x, y, w, h)

    def _fade_in_widgets(self, widgets: list[QWidget], duration: int = 230) -> None:
        self._ui_fade_anims = []
        for widget in widgets:
            if widget is None or not widget.isVisible():
                continue
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(0.0)
            widget.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(duration)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def clear_effect(w=widget, e=effect) -> None:
                if w.graphicsEffect() is e:
                    w.setGraphicsEffect(None)

            anim.finished.connect(clear_effect)
            anim.start()
            self._ui_fade_anims.append(anim)

    def _focus_elapsed_seconds(self) -> float:
        elapsed = self.stat_focus_seconds
        if self._focus_mode_active and self._focus_started_at is not None:
            elapsed += max(0.0, time.monotonic() - self._focus_started_at)
        return elapsed

    def _update_overlay_theme(self) -> None:
        if not hasattr(self, "info_overlay"):
            return
        bg = QColor(self.background_color)
        fg = get_contrast_color(bg)
        self.info_overlay.setStyleSheet(
            f"background-color: rgb({bg.red()}, {bg.green()}, {bg.blue()});"
        )
        self.info_overlay_title.setStyleSheet(
            f"color: rgb({fg.red()}, {fg.green()}, {fg.blue()}); font-size: 26px; font-weight: 700;"
        )
        self.info_overlay_body.setStyleSheet(
            f"color: rgb({fg.red()}, {fg.green()}, {fg.blue()}); line-height: 1.45;"
        )

    def _hotkeys_overlay_text(self) -> str:
        return (
            "Left/Right - Navigate history days\n"
            "Tab - Jump/add task while editing\n"
            "Esc - Exit app\n"
            "Right click window - Hibernate\n"
            "Long press task - Enter focus mode\n"
            "\n"
            "Q - Return to today's default view\n"
            "B - Open/close Bird's Eye year grid\n"
            "Space - Toggle this hotkey menu\n"
            "C - Open/close clock view\n"
            "S - Open/close stats view\n"
            "F - Open/close full task view\n"
            "G - Open/close settings\n"
            "H - Toggle debug time label\n"
            "Up/Down - Time travel debug (Debug Mode)\n"
            "R - Reset spoofed time\n"
            "N - Nuke all task data (Debug Mode)"
        )

    def _year_completed_days(self, year: int) -> set[date]:
        start = date(year, 1, 1).isoformat()
        end = date(year, 12, 31).isoformat()
        rows = self.db.execute(
            """
            SELECT day, COUNT(*) as completed_count
            FROM tasks
            WHERE status = 'COMPLETED' AND day >= ? AND day <= ?
            GROUP BY day
            HAVING completed_count >= 3
            """,
            (start, end),
        ).fetchall()
        out: set[date] = set()
        for day_key, _count in rows:
            try:
                out.add(date.fromisoformat(str(day_key)))
            except Exception:
                continue
        return out

    def _stats_overlay_text(self) -> str:
        completed = len([b for b in self.buttons if b.state == TaskStripe.COMPLETED and not b.is_deleting])
        active_or_done = len([b for b in self.buttons if b.state != TaskStripe.EMPTY and not b.is_deleting])
        completion_pct = (completed / max(1, active_or_done)) * 100.0 if active_or_done else 0.0
        best_day = self._best_completed_day_count()
        focus_seconds = int(self._focus_elapsed_seconds())
        focus_hours = focus_seconds // 3600
        focus_minutes = (focus_seconds % 3600) // 60
        return (
            f"Task Completion: {completed}/{max(1, active_or_done)} ({completion_pct:.0f}%)\n"
            f"Time in focus mode: {focus_hours}h{focus_minutes}m\n"
            "\n"
            "<b>Lifetime</b>\n"
            f"Clicks: {self.stat_clicks}\n"
            f"Tasks created: {self.stat_tasks_created}\n"
            f"Tasks deleted: {self.stat_tasks_deleted}\n"
            f"Tasks completed: {self.stat_tasks_completed}\n"
            f"Most tasks in one day: {best_day}"
        )

    def _clock_overlay_text(self) -> str:
        now = self.get_app_time()
        hour12 = now.hour % 12 or 12
        return f"{hour12} {now.minute:02d} {now.second:02d}"

    def _settings_overlay_text(self) -> str:
        debug_status = "ON" if self.debug_mode_enabled else "OFF"
        palette_names = {
            "yellow": "1: Lemon (Yellow)",
            "mint": "2: Mint (Green)",
            "maroon": "3: Maroon (Red)",
            "grayscale": "4: Grayscale"
        }
        palette_list = "\n".join([f"{'→ ' if self.current_palette == k else '  '}{v}" for k, v in palette_names.items()])
        
        return (
            f"<b>Debug Mode: {debug_status}</b>\n"
            "Press [D] to toggle\n"
            "(Enables Nuke and Time Travel)\n"
            "\n"
            "<b>Palette Swap</b>\n"
            f"{palette_list}\n"
            "\n"
            "Press [Esc] or [G] to close"
        )

    def _clock_overlay_font(self) -> QFont:
        preferred_family = self.title_font_family or self.font().family()
        preferred = QFont(preferred_family, 40)
        metrics = QFontMetrics(preferred)
        if all(metrics.inFontUcs4(ord(ch)) for ch in "0123456789"):
            return preferred
        return QFont(self.font().family(), 40)

    def _set_overlay_mode(self, mode: str | None, animated: bool = True) -> None:
        if self.is_hibernated:
            return
        if mode == self._overlay_mode:
            return
        previous_mode = self._overlay_mode
        self._overlay_mode = mode
        self._update_overlay_theme()
        if mode is None:
            if self._overlay_anim and self._overlay_anim.state() == QAbstractAnimation.State.Running:
                self._overlay_anim.stop()
            if not self.info_overlay.isVisible():
                return
            if not animated:
                self.info_overlay.hide()
                self.info_overlay.setGraphicsEffect(None)
                return
            effect = self._ensure_opacity_effect(self.info_overlay)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(230)
            anim.setStartValue(float(effect.opacity()))
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def finish_hide() -> None:
                self.info_overlay.hide()
                if self.info_overlay.graphicsEffect() is effect:
                    self.info_overlay.setGraphicsEffect(None)

            anim.finished.connect(finish_hide)
            self._overlay_anim = anim
            anim.start()
            return

        if mode == "hotkeys":
            self.info_overlay_title.show()
            self.birds_eye_grid.hide()
            self.info_overlay_body.show()
            self.day_label.hide()
            self.info_overlay_title.setText("Hotkeys")
            self.info_overlay_title.setFont(QFont(self.title_font_family or self.font().family(), 30))
            self.info_overlay_body.setFont(QFont(self.font().family(), 13))
            self.info_overlay_body.setText(self._hotkeys_overlay_text())
        elif mode == "clock":
            self.info_overlay_title.hide()
            self.birds_eye_grid.hide()
            self.info_overlay_body.show()
            self.day_label.hide()
            self.info_overlay_body.setFont(self._clock_overlay_font())
            self.info_overlay_body.setText(self._clock_overlay_text())
        elif mode == "stats":
            self.info_overlay_title.show()
            self.birds_eye_grid.hide()
            self.info_overlay_body.show()
            self.day_label.hide()
            self.info_overlay_title.setText("Stats")
            self.info_overlay_title.setFont(QFont(self.title_font_family or self.font().family(), 30))
            self.info_overlay_body.setFont(QFont(self.font().family(), 13))
            self.info_overlay_body.setText(self._stats_overlay_text())
        elif mode == "birds":
            self.info_overlay_title.hide()
            self.info_overlay_body.hide()
            self._position_birds_eye_grid()
            self.birds_eye_grid.show()
            self.day_label.hide()
            year = self.get_app_time().date().year
            self.birds_eye_grid.set_data(year, self._year_completed_days(year))
        elif mode == "settings":
            self.info_overlay_title.show()
            self.birds_eye_grid.hide()
            self.info_overlay_body.show()
            self.day_label.hide()
            self.info_overlay_title.setText("Settings")
            self.info_overlay_title.setFont(QFont(self.title_font_family or self.font().family(), 30))
            self.info_overlay_body.setFont(QFont(self.font().family(), 13))
            self.info_overlay_body.setText(self._settings_overlay_text())
        elif mode == "full_tasks":
            self.full_task_overlay.refresh_tasks()
            self.full_task_overlay.show()
            self.full_task_overlay.raise_()
            self.info_overlay.hide() # Full task view is separate
            return
        else:
            return
        self.info_overlay.raise_()
        self.info_overlay.show()
        if self.full_task_overlay.isVisible():
            self.full_task_overlay.hide()
            
        if previous_mode is not None:
            if self._overlay_anim and self._overlay_anim.state() == QAbstractAnimation.State.Running:
                self._overlay_anim.stop()
            effect = self._ensure_opacity_effect(self.info_overlay)
            effect.setOpacity(1.0)
            return
        if self._overlay_anim and self._overlay_anim.state() == QAbstractAnimation.State.Running:
            self._overlay_anim.stop()
        if animated:
            effect = self._ensure_opacity_effect(self.info_overlay)
            effect.setOpacity(0.0)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(230)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._overlay_anim = anim
            anim.start()
        else:
            self.info_overlay.setGraphicsEffect(None)

    def _toggle_overlay_mode(self, mode: str) -> None:
        self._set_overlay_mode(None if self._overlay_mode == mode else mode, animated=True)

    def _refresh_overlay_content(self) -> None:
        if self._overlay_mode == "clock":
            self.info_overlay_body.setText(self._clock_overlay_text())
        elif self._overlay_mode == "stats":
            self.info_overlay_body.setText(self._stats_overlay_text())
        elif self._overlay_mode == "birds":
            year = self.get_app_time().date().year
            self.birds_eye_grid.set_data(year, self._year_completed_days(year))
        elif self._overlay_mode == "settings":
            self.info_overlay_body.setText(self._settings_overlay_text())

    def on_birds_eye_day_hovered(self, day_value: date | None) -> None:
        if self._overlay_mode != "birds":
            return
        if day_value is None:
            self.day_label.hide()
            return
        self.day_label.setText(day_value.strftime("%b %d"))
        self.day_label.show()
        self.day_label.raise_()

    def on_birds_eye_day_selected(self, day_value: date) -> None:
        if self._overlay_mode != "birds":
            return
        today = self._navigation_today()
        if day_value > today:
            return
        self._set_overlay_mode(None, animated=False)
        self.day_label.hide()
        if day_value == self.view_date:
            self._update_nav_buttons()
            return
        self._interrupt_and_snap_animations()
        self._save_current_day()
        self._load_day(day_value)
        self._update_nav_buttons()

    def _play_wake_overlay(self, color: QColor) -> None:
        if not hasattr(self, "wake_overlay"):
            return
        if self._wake_overlay_anim and self._wake_overlay_anim.state() == QAbstractAnimation.State.Running:
            self._wake_overlay_anim.stop()
        self.wake_overlay.setGeometry(self.rect())
        self.wake_overlay.setStyleSheet(
            f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});"
        )
        effect = self._ensure_opacity_effect(self.wake_overlay)
        effect.setOpacity(1.0)
        self.wake_overlay.show()
        self.wake_overlay.raise_()
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(320)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def finish() -> None:
            self.wake_overlay.hide()
            if self.wake_overlay.graphicsEffect() is effect:
                self.wake_overlay.setGraphicsEffect(None)

        anim.finished.connect(finish)
        self._wake_overlay_anim = anim
        anim.start()

    def _show_wake_overlay_immediate(self, color: QColor) -> None:
        if not hasattr(self, "wake_overlay"):
            return
        if self._wake_overlay_anim and self._wake_overlay_anim.state() == QAbstractAnimation.State.Running:
            self._wake_overlay_anim.stop()
        self.wake_overlay.setGeometry(self.rect())
        self.wake_overlay.setStyleSheet(
            f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});"
        )
        effect = self._ensure_opacity_effect(self.wake_overlay)
        effect.setOpacity(1.0)
        self.wake_overlay.show()
        self.wake_overlay.raise_()

    def go_to_default_today_view(self) -> None:
        if self._focus_mode_active:
            return
        if self._overlay_mode is not None:
            self._set_overlay_mode(None, animated=False)
        self.day_label.hide()
        target = self._navigation_today()
        if self.view_date == target:
            self._update_nav_buttons()
            return
        self._interrupt_and_snap_animations()
        self._save_current_day()
        self._load_day(target)
        self._update_nav_buttons()

    def enter_hibernate(self) -> None:
        if self.is_hibernated:
            return
        self._hibernate_overlay_mode = self._overlay_mode
        if self._focus_mode_active:
            self._hibernate_from_focus = True
            self._hibernate_focus_target = self._focused_stripe
            if self._focus_transition_group and self._focus_transition_group.state() == QAbstractAnimation.State.Running:
                self._focus_transition_group.stop()
            focused = self._focused_stripe
            if focused is not None:
                focused.set_focus_mode(False)
                if self._focus_reparented:
                    global_tl = focused.mapToGlobal(QPoint(0, 0))
                    local_tl = self.stripe_wrapper.mapFromGlobal(global_tl)
                    focused.setParent(self.stripe_wrapper)
                    focused.setGeometry(QRect(local_tl.x(), local_tl.y(), focused.width(), focused.height()))
                    focused.show()
                    self._focus_reparented = False
            for other in self.buttons:
                try:
                    other.set_focus_blackout(0.0)
                    other.set_focus_dimmed(False)
                    other.setEnabled(True)
                except RuntimeError:
                    pass
            self.focus_tint_overlay.hide()
            if self._focus_started_at is not None:
                self.stat_focus_seconds += max(0.0, time.monotonic() - self._focus_started_at)
                self._focus_started_at = None
            self._focus_mode_active = False
            self._focused_stripe = None
            self.main_layout.setEnabled(True)
        else:
            self._hibernate_from_focus = False
            self._hibernate_focus_target = None
        self._interrupt_and_snap_animations()
        self._hibernate_saved_geometry = QRect(self.geometry())
        if self._pre_hibernate_min_size is None:
            ms = self.minimumSize()
            self._pre_hibernate_min_size = (ms.width(), ms.height())
        self.setMinimumSize(1, 1)
        self.is_hibernated = True
        self._hibernate_hovered = False
        self.stripe_wrapper.hide()
        self.add_task_button.hide()
        self.debug_label.hide()
        self.sleep_label.hide()
        self.title.hide()
        self._set_overlay_mode(None, animated=False)
        self.back_button.hide()
        self.forward_button.hide()
        self.day_label.hide()
        self._position_title()

        target = self._hibernate_target_geometry()
        if self._hibernate_anim_group and self._hibernate_anim_group.state() == QAbstractAnimation.State.Running:
            self._hibernate_anim_group.stop()
        g_anim = QPropertyAnimation(self, b"geometry", self)
        g_anim.setDuration(280)
        g_anim.setStartValue(self.geometry())
        g_anim.setEndValue(target)
        g_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        o_anim = QPropertyAnimation(self, b"windowOpacity", self)
        o_anim.setDuration(280)
        o_anim.setStartValue(float(self.windowOpacity()))
        o_anim.setEndValue(0.2)
        o_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(g_anim)
        group.addAnimation(o_anim)
        self._hibernate_anim_group = group
        group.start()

    def exit_hibernate(self) -> None:
        if not self.is_hibernated:
            return
        target = QRect(self._hibernate_saved_geometry) if self._hibernate_saved_geometry is not None else QRect(self.geometry())
        self.is_hibernated = False
        if self._hibernate_from_focus and self._hibernate_focus_target in self.buttons:
            self._show_wake_overlay_immediate(QColor(0, 0, 0))
        if self._hibernate_anim_group and self._hibernate_anim_group.state() == QAbstractAnimation.State.Running:
            self._hibernate_anim_group.stop()

        g_anim = QPropertyAnimation(self, b"geometry", self)
        g_anim.setDuration(240)
        g_anim.setStartValue(self.geometry())
        g_anim.setEndValue(target)
        g_anim.setEasingCurve(QEasingCurve.Type.OutBack)

        o_anim = QPropertyAnimation(self, b"windowOpacity", self)
        o_anim.setDuration(240)
        o_anim.setStartValue(float(self.windowOpacity()))
        o_anim.setEndValue(1.0)
        o_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(g_anim)
        group.addAnimation(o_anim)
        self._hibernate_anim_group = group

        def after_exit() -> None:
            if self._pre_hibernate_min_size is not None:
                self.setMinimumSize(self._pre_hibernate_min_size[0], self._pre_hibernate_min_size[1])
            restore_overlay_mode = self._hibernate_overlay_mode
            if restore_overlay_mode is None:
                self.title.show()
            else:
                self.title.hide()
            self.stripe_wrapper.show()
            self.apply_dynamic_styles()
            self.recenter_ui(animated=False)
            self._position_title()
            self._update_nav_buttons()
            self._position_debug_overlay()
            if self.debug_visible and restore_overlay_mode is None:
                self.debug_label.show()
            if self._hibernate_from_focus and self._hibernate_focus_target in self.buttons:
                self._enter_focus_mode_immediate(self._hibernate_focus_target)
                self._play_wake_overlay(QColor(0, 0, 0))
            else:
                fade_targets = [
                    self.title,
                    self.stripe_wrapper,
                    self.back_button,
                    self.forward_button,
                    self.day_label,
                    self.debug_label,
                ]
                self._fade_in_widgets(fade_targets)
                self._play_wake_overlay(QColor(self.background_color))
                if restore_overlay_mode is not None:
                    self._set_overlay_mode(restore_overlay_mode, animated=False)
            self._reset_idle_timer()
            self._hibernate_focus_target = None
            self._hibernate_from_focus = False
            self._hibernate_overlay_mode = None

        group.finished.connect(after_exit)
        group.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        path = QPainterPath()
        radius = self.width() / 2
        path.addRoundedRect(QRectF(self.rect()), radius, radius)
        self.pill_path = path
        mask_polygon = self.pill_path.toFillPolygon().toPolygon()
        try:
            self.setMask(mask_polygon)
        except TypeError:
            self.setMask(QRegion(mask_polygon))
        self._position_title()
        self.relayout_stripes(animated=False)
        self._position_debug_overlay()
        if hasattr(self, "focus_tint_overlay"):
            self.focus_tint_overlay.setGeometry(self.rect())
        if hasattr(self, "wake_overlay"):
            self.wake_overlay.setGeometry(self.rect())
        if hasattr(self, "info_overlay"):
            self.info_overlay.setGeometry(self.rect())
            self._position_birds_eye_grid()
        if hasattr(self, "particle_overlay"):
            self.particle_overlay.setGeometry(self.rect())
            self.particle_overlay.raise_()

    def _position_title(self) -> None:
        title_w = 96
        title_h = 68
        x = int((self.width() - title_w) / 2)
        self.title.setGeometry(x, self.height() - title_h - 10, title_w, title_h)
        self.title.raise_()
        nav_y = 96
        self.back_button.setGeometry(34, nav_y, 28, 28)
        self.forward_button.setGeometry(self.width() - 62, nav_y, 28, 28)
        self.day_label.setGeometry(int((self.width() - 100) / 2), nav_y + 4, 100, 18)
        self.back_button.raise_()
        self.forward_button.raise_()
        self.day_label.raise_()

    def _position_debug_overlay(self) -> None:
        overlay_w = 160
        overlay_h = 26
        x = int((self.width() - overlay_w) / 2)
        y = self.height() - overlay_h - 12
        self.debug_label.setGeometry(x, y, overlay_w, overlay_h)

    def _position_birds_eye_grid(self) -> None:
        if not hasattr(self, "birds_eye_grid") or not hasattr(self, "info_overlay"):
            return
        avail_w = max(120, self.info_overlay.width() - 56)
        avail_h = max(140, self.info_overlay.height() - 120)
        # Preserve 19x20 shape so cells remain square-ish and centered.
        w_from_h = int(avail_h * 19 / 20)
        if w_from_h <= avail_w:
            target_w = w_from_h
            target_h = avail_h
        else:
            target_w = avail_w
            target_h = int(avail_w * 20 / 19)
        self.birds_eye_grid.setFixedSize(max(120, target_w), max(126, target_h))

    def on_stripe_height_changed(self) -> None:
        if self._completion_in_progress:
            return
        self.recenter_ui(animated=False)
        self._position_debug_overlay()

    def add_task_stripe(self, animate: bool = True, count_stat: bool = True) -> None:
        stripe = self._create_task_stripe()
        if count_stat:
            self.stat_tasks_created += 1
            self._lifetime_stats_dirty = True
        if animate:
            self.recenter_ui(animated=False)
            self._pending_adds.append((time.monotonic() + 1.5, stripe))
            self._schedule_pending_actions()
        else:
            self.recenter_ui(animated=False)

    def add_task(self) -> None:
        self.add_task_stripe(animate=True)

    def _create_task_stripe(self) -> TaskStripe:
        stripe = TaskStripe(self.stripe_wrapper)
        stripe.completed.connect(self.spawn_confetti)
        stripe.height_changed.connect(self.on_stripe_height_changed)
        stripe.state_changed.connect(self.on_stripe_state_changed)
        stripe.focus_move_requested.connect(self.on_focus_move_requested)
        stripe.completed_clicked.connect(self.on_completed_clicked)
        stripe.delete_requested.connect(self.on_delete_requested)
        stripe.long_pressed.connect(self.on_task_long_pressed)
        stripe.focus_complete_requested.connect(self.on_focus_complete_requested)
        stripe.apply_theme(self.button_color)
        stripe.show()
        self.buttons.append(stripe)
        return stripe

    def on_focus_move_requested(self, from_stripe: TaskStripe, direction: int) -> None:
        candidates = [b for b in self.buttons if b.state != TaskStripe.COMPLETED]
        if not candidates:
            if direction >= 0:
                self.add_task_stripe(animate=True)
                if self.buttons:
                    newest = self.buttons[-1]
                    QTimer.singleShot(520, newest.focus_for_input)
            return
        if from_stripe not in candidates:
            target = candidates[0]
            target.focus_for_input()
            return
        idx = candidates.index(from_stripe)
        if direction >= 0:
            if idx == len(candidates) - 1:
                self.add_task_stripe(animate=True)
                if self.buttons:
                    newest = self.buttons[-1]
                    QTimer.singleShot(520, newest.focus_for_input)
                return
            below = candidates[idx + 1] if idx + 1 < len(candidates) else None
            if below is not None and below.state == TaskStripe.EMPTY:
                below.focus_for_input()
                return
            # Tab shortcut: no empty stripe below -> create one with slide-in.
            self.add_task_stripe(animate=True)
            if self.buttons:
                newest = self.buttons[-1]
                QTimer.singleShot(520, newest.focus_for_input)
            return
        prev_idx = (idx - 1) % len(candidates)
        candidates[prev_idx].focus_for_input()

    def on_completed_clicked(self, stripe: TaskStripe) -> None:
        if self._focus_mode_active:
            self.exit_focus_mode()
            return
        if stripe.state != TaskStripe.COMPLETED:
            return
        if not self._accordion_open:
            self._set_accordion_open(True, animated=True)
            return
        stripe.reopen_from_completed()
        if stripe in self.buttons:
            self.buttons.remove(stripe)
            self.buttons.append(stripe)
        stripe.raise_()
        self.recenter_ui(animated=True)
        self._save_current_day()

    def on_delete_requested(self, stripe: TaskStripe) -> None:
        if self._focus_mode_active:
            self.exit_focus_mode()
            return
        if stripe not in self.buttons or stripe.is_deleting:
            return
        stripe.begin_delete_visual()
        stripe.set_delete_progress(1.0)
        ready_at = time.monotonic() + 1.5
        self._pending_deletes.append((ready_at, stripe))
        self._schedule_delete_queue()

    def _schedule_delete_queue(self) -> None:
        if self._delete_in_progress:
            return
        now = time.monotonic()
        self._pending_deletes = [(t, s) for t, s in self._pending_deletes if s in self.buttons and s.is_deleting]
        if not self._pending_deletes:
            if self._delete_queue_timer.isActive():
                self._delete_queue_timer.stop()
            return
        next_time = min(t for t, _s in self._pending_deletes)
        delay_ms = max(0, int((next_time - now) * 1000))
        self._delete_queue_timer.start(delay_ms)

    def _process_delete_queue(self) -> None:
        if self._delete_in_progress:
            return
        now = time.monotonic()
        self._pending_deletes = [(t, s) for t, s in self._pending_deletes if s in self.buttons and s.is_deleting]
        if not self._pending_deletes:
            return
        ready_idx = None
        for i, (t, _s) in enumerate(self._pending_deletes):
            if t <= now:
                ready_idx = i
                break
        if ready_idx is None:
            self._schedule_delete_queue()
            return
        _t, stripe = self._pending_deletes.pop(ready_idx)
        self._run_delete_animation(stripe)

    def _run_delete_animation(self, stripe: TaskStripe) -> None:
        if stripe not in self.buttons or not stripe.is_deleting:
            self._schedule_delete_queue()
            return
        self._delete_in_progress = True
        epoch = self._animation_epoch
        start_rect = QRect(stripe.geometry())
        drop_rect = QRect(start_rect)
        drop_rect.moveTop(start_rect.y() + max(120, int(self.height() * 0.24)))

        drop_anim = QPropertyAnimation(stripe, b"geometry", self)
        drop_anim.setDuration(360)
        drop_anim.setStartValue(start_rect)
        drop_anim.setEndValue(drop_rect)
        drop_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        fade_anim = QVariantAnimation(self)
        fade_anim.setDuration(360)
        fade_anim.setStartValue(1.0)
        fade_anim.setEndValue(0.0)
        fade_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        fade_anim.valueChanged.connect(lambda v: stripe.set_delete_opacity(float(v)))

        parallel = QParallelAnimationGroup(self)
        parallel.addAnimation(drop_anim)
        parallel.addAnimation(fade_anim)

        self._register_animation(drop_anim, stripe, drop_rect)
        self._register_animation(parallel)

        def finalize_delete() -> None:
            self._delete_in_progress = False
            if epoch != self._animation_epoch:
                self._schedule_delete_queue()
                return
            if stripe in self.buttons:
                self.buttons.remove(stripe)
                self.stat_tasks_deleted += 1
                self._lifetime_stats_dirty = True
            try:
                stripe.setParent(None)
                stripe.deleteLater()
            except RuntimeError:
                pass
            if not self.buttons:
                self.add_task_stripe(animate=False, count_stat=False)
            if not any(b.state == TaskStripe.COMPLETED for b in self.buttons):
                self._accordion_open = False
            self.recenter_ui(animated=True, interrupt=False)
            self._save_current_day()
            self._process_delete_queue()

        parallel.finished.connect(finalize_delete)
        parallel.start()

    def _schedule_pending_actions(self) -> None:
        if self._delete_in_progress or self._completion_in_progress:
            self._action_queue_timer.start(120)
            return
        now = time.monotonic()
        self._pending_completions = [
            (t, s)
            for t, s in self._pending_completions
            if s in self.buttons and s.state == TaskStripe.COMPLETED and not s.is_deleting
        ]
        self._pending_adds = [(t, s) for t, s in self._pending_adds if s in self.buttons and not s.is_deleting]
        if not self._pending_completions and not self._pending_adds:
            if self._action_queue_timer.isActive():
                self._action_queue_timer.stop()
            return
        next_time = min([t for t, _s in self._pending_completions] + [t for t, _s in self._pending_adds])
        delay_ms = max(0, int((next_time - now) * 1000))
        self._action_queue_timer.start(delay_ms)

    def _process_pending_actions(self) -> None:
        if self._delete_in_progress or self._completion_in_progress:
            self._schedule_pending_actions()
            return
        now = time.monotonic()
        self._pending_completions = [
            (t, s)
            for t, s in self._pending_completions
            if s in self.buttons and s.state == TaskStripe.COMPLETED and not s.is_deleting
        ]
        self._pending_adds = [(t, s) for t, s in self._pending_adds if s in self.buttons and not s.is_deleting]

        ready_completion_idx = next((i for i, (t, _s) in enumerate(self._pending_completions) if t <= now), None)
        if ready_completion_idx is not None:
            _t, stripe = self._pending_completions.pop(ready_completion_idx)
            self.complete_task(stripe)
            self._schedule_pending_actions()
            return

        ready_add_idx = next((i for i, (t, _s) in enumerate(self._pending_adds) if t <= now), None)
        if ready_add_idx is not None:
            _t, stripe = self._pending_adds.pop(ready_add_idx)
            self._animate_add_task_sequence(stripe)
            self._schedule_pending_actions()
            return

        self._schedule_pending_actions()

    def on_stripe_state_changed(self) -> None:
        if self._focus_mode_active:
            return
        if self._loading_state or self._suppress_state_signal:
            return
        stripe = self.sender()
        if isinstance(stripe, TaskStripe):
            if stripe.state == TaskStripe.COMPLETED and stripe.completion_rank is None:
                self.stat_tasks_completed += 1
                self._lifetime_stats_dirty = True
                stripe.completion_rank = self._completed_counter
                self._completed_counter += 1
                self._pending_completions.append((time.monotonic() + 1.5, stripe))
                self._schedule_pending_actions()
                return
            elif stripe.state != TaskStripe.COMPLETED and stripe.completion_rank is not None:
                stripe.completion_rank = None
                stripe.completion_fade = 0.0
        if not any(b.state == TaskStripe.COMPLETED for b in self.buttons):
            self._accordion_open = False
        self._save_current_day()
        self.recenter_ui(animated=True)

    def on_task_long_pressed(self, stripe: TaskStripe) -> None:
        if self.is_hibernated or self._focus_mode_active:
            return
        if stripe.state == TaskStripe.COMPLETED or stripe.is_deleting:
            return
        self.enter_focus_mode(stripe)

    def on_focus_complete_requested(self, stripe: TaskStripe) -> None:
        if not self._focus_mode_active:
            return
        if stripe is not self._focused_stripe:
            return
        if stripe.state != TaskStripe.ACTIVE or stripe.is_deleting:
            return

        def finish_and_complete() -> None:
            if stripe in self.buttons and stripe.state == TaskStripe.ACTIVE and not stripe.is_deleting:
                stripe.set_completed()

        self.exit_focus_mode(on_finished=finish_and_complete)

    def _set_focus_tint(self) -> None:
        self.focus_tint_overlay.setStyleSheet("background-color: rgb(0, 0, 0);")

    def _ensure_opacity_effect(self, widget: QWidget) -> QGraphicsOpacityEffect:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(1.0)
            widget.setGraphicsEffect(effect)
        return effect

    def _add_opacity_anim(
        self,
        widget: QWidget,
        target_opacity: float,
        group: QParallelAnimationGroup,
        duration: int = 220,
    ) -> None:
        effect = self._ensure_opacity_effect(widget)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(duration)
        anim.setStartValue(float(effect.opacity()))
        anim.setEndValue(float(target_opacity))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(anim)

    def _add_blackout_anim(
        self,
        stripe: TaskStripe,
        target_value: float,
        group: QParallelAnimationGroup,
        duration: int = 220,
    ) -> None:
        anim = QVariantAnimation(self)
        anim.setDuration(duration)
        anim.setStartValue(float(getattr(stripe, "_focus_blackout", 0.0)))
        anim.setEndValue(float(target_value))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v, s=stripe: s.set_focus_blackout(float(v)))
        group.addAnimation(anim)

    def enter_focus_mode(self, stripe: TaskStripe) -> None:
        if self._focus_mode_active:
            return
        self._set_overlay_mode(None, animated=False)
        self._interrupt_and_snap_animations()
        self._focus_mode_active = True
        self._focus_started_at = time.monotonic()
        self._focused_stripe = stripe
        self.main_layout.setEnabled(False)
        if self._focus_transition_group and self._focus_transition_group.state() == QAbstractAnimation.State.Running:
            self._focus_transition_group.stop()

        transition = QParallelAnimationGroup(self)

        for other in self.buttons:
            if other is stripe:
                other.set_focus_dimmed(False)
                continue
            other.setEnabled(False)
            self._add_blackout_anim(other, 1.0, transition, 240)

        fade_targets: list[QWidget] = [self.title, self.back_button, self.forward_button, self.day_label, self.add_task_button]
        if self.debug_visible and self.debug_label.isVisible():
            fade_targets.append(self.debug_label)
        for w in fade_targets:
            if w is None or not w.isVisible():
                continue
            self._add_opacity_anim(w, 0.0, transition, 240)

        self._set_focus_tint()
        self._ensure_opacity_effect(self.focus_tint_overlay).setOpacity(0.0)
        self.focus_tint_overlay.show()
        self.focus_tint_overlay.raise_()
        self._add_opacity_anim(self.focus_tint_overlay, 1.0, transition, 240)
        stripe.set_focus_mode(True)

        # Move focused stripe above the blackout overlay.
        global_tl = stripe.mapToGlobal(QPoint(0, 0))
        local_tl = self.mapFromGlobal(global_tl)
        stripe.setParent(self)
        stripe.setGeometry(QRect(local_tl.x(), local_tl.y(), stripe.width(), stripe.height()))
        stripe.show()
        stripe.raise_()
        self._focus_reparented = True

        target_y = max(0, int((self.height() - stripe.height()) / 2))
        target_x = int((self.width() - stripe.width()) / 2)
        anim = QPropertyAnimation(stripe, b"pos", self)
        anim.setDuration(260)
        anim.setStartValue(stripe.pos())
        anim.setEndValue(QPoint(target_x, target_y))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._register_animation(anim, stripe, QRect(target_x, target_y, stripe.width(), stripe.height()))
        anim.start()
        self._focus_transition_group = transition
        transition.start()

    def _enter_focus_mode_immediate(self, stripe: TaskStripe) -> None:
        if stripe not in self.buttons:
            return
        self._set_overlay_mode(None, animated=False)
        self._interrupt_and_snap_animations()
        if self._focus_transition_group and self._focus_transition_group.state() == QAbstractAnimation.State.Running:
            self._focus_transition_group.stop()
        self._focus_mode_active = True
        self._focus_started_at = time.monotonic()
        self._focused_stripe = stripe
        self.main_layout.setEnabled(False)
        self._focus_transition_group = None

        for other in self.buttons:
            try:
                if other is stripe:
                    other.set_focus_dimmed(False)
                    continue
                other.setEnabled(False)
                other.set_focus_blackout(1.0)
            except RuntimeError:
                continue

        self.title.hide()
        self.back_button.hide()
        self.forward_button.hide()
        self.day_label.hide()
        self.add_task_button.hide()
        self.debug_label.hide()
        self._set_focus_tint()
        self._ensure_opacity_effect(self.focus_tint_overlay).setOpacity(1.0)
        self.focus_tint_overlay.show()
        self.focus_tint_overlay.raise_()

        stripe.set_focus_mode(True)
        global_tl = stripe.mapToGlobal(QPoint(0, 0))
        local_tl = self.mapFromGlobal(global_tl)
        stripe.setParent(self)
        stripe.setGeometry(QRect(local_tl.x(), local_tl.y(), stripe.width(), stripe.height()))
        stripe.show()
        target_y = max(0, int((self.height() - stripe.height()) / 2))
        target_x = int((self.width() - stripe.width()) / 2)
        stripe.move(target_x, target_y)
        stripe.raise_()
        self._focus_reparented = True

    def exit_focus_mode(self, on_finished=None) -> None:
        if not self._focus_mode_active:
            return
        if self._focus_transition_group and self._focus_transition_group.state() == QAbstractAnimation.State.Running:
            self._focus_transition_group.stop()
        focused = self._focused_stripe
        if focused is not None:
            focused.set_focus_mode(False)
            if self._focus_reparented:
                global_tl = focused.mapToGlobal(QPoint(0, 0))
                local_tl = self.stripe_wrapper.mapFromGlobal(global_tl)
                focused.setParent(self.stripe_wrapper)
                focused.setGeometry(QRect(local_tl.x(), local_tl.y(), focused.width(), focused.height()))
                focused.show()
                self._focus_reparented = False
        transition = QParallelAnimationGroup(self)
        for other in self.buttons:
            try:
                other.setEnabled(True)
                self._add_blackout_anim(other, 0.0, transition, 220)
            except RuntimeError:
                pass
        fade_targets: list[QWidget] = [self.title, self.back_button, self.forward_button, self.day_label, self.add_task_button]
        if self.debug_visible:
            fade_targets.append(self.debug_label)
        for w in fade_targets:
            if w is None:
                continue
            if w in {self.back_button, self.forward_button, self.day_label}:
                # Respect nav visibility state; do not force-show.
                if not w.isVisible():
                    continue
            else:
                w.show()
            self._add_opacity_anim(w, 1.0, transition, 220)

        self._add_opacity_anim(self.focus_tint_overlay, 0.0, transition, 220)

        def done() -> None:
            self.focus_tint_overlay.hide()
            if self._focus_started_at is not None:
                self.stat_focus_seconds += max(0.0, time.monotonic() - self._focus_started_at)
                self._focus_started_at = None
            self._focus_mode_active = False
            self._focused_stripe = None
            self.main_layout.setEnabled(True)
            self.recenter_ui(animated=True)
            if callable(on_finished):
                on_finished()

        transition.finished.connect(done)
        self._focus_transition_group = transition
        transition.start()

    def complete_task(self, completed_stripe: TaskStripe) -> None:
        self._animate_completion_sequence(completed_stripe)

    def _compute_layout_targets(self) -> tuple[dict[TaskStripe, QRect], QRect | None, int, bool]:
        wrapper_width = max(0, self.stripe_wrapper.width())
        completed = [b for b in self.buttons if b.state == TaskStripe.COMPLETED and not b.is_deleting]
        completed.sort(key=lambda b: b.completion_rank if b.completion_rank is not None else 10**9)
        active = [b for b in self.buttons if b.state != TaskStripe.COMPLETED and not b.is_deleting]
        wrapper_top_in_window = self.stripe_wrapper.mapTo(self, QPoint(0, 0)).y()
        completed_anchor_y = max(0, int(self.height() * 0.25) - wrapper_top_in_window)
        active_anchor_y = max(0, int(self.height() * 0.40) - wrapper_top_in_window)
        targets: dict[TaskStripe, QRect] = {}

        completed_bottom = completed_anchor_y
        for idx, stripe in enumerate(completed):
            step = stripe.height() + self.stripe_gap + 2 if self._accordion_open else self.completed_step
            y = completed_anchor_y + idx * step
            targets[stripe] = QRect(0, y, wrapper_width, stripe.height())
            completed_bottom = max(completed_bottom, y + stripe.height())

        if active:
            active_total_height = sum(s.height() for s in active) + self.stripe_gap * max(0, len(active) - 1)
            # Let active stack breathe around the 40% anchor by shifting some height upward.
            proposed_top = max(0, active_anchor_y - int(active_total_height * 0.35))
        else:
            active_total_height = 0
            proposed_top = active_anchor_y
        if completed:
            # Floating buffer: active zone must remain exactly 150px below completed stack bottom.
            active_start_y = max(0, completed_bottom + 150)
        else:
            active_start_y = proposed_top
        placeholder_active_bottom = active_start_y + 72 if (completed and not active) else 0
        current_y = active_start_y
        for idx, stripe in enumerate(active):
            if idx > 0:
                current_y += active[idx - 1].height() + self.stripe_gap
            targets[stripe] = QRect(0, current_y, wrapper_width, stripe.height())

        show_add = False
        add_target: QRect | None = None
        if active and show_add:
            last_active = active[-1]
            last_rect = QRect(0, current_y, wrapper_width, last_active.height())
            add_y = last_rect.y() + last_rect.height() + self.add_button_gap
        elif completed and show_add:
            add_y = max(completed_bottom + 150, active_anchor_y) + self.add_button_gap
        else:
            add_y = active_anchor_y + self.add_button_gap
        add_x = max(0, (wrapper_width - self.add_task_button.width()) // 2)
        if show_add:
            add_target = QRect(add_x, add_y, self.add_task_button.width(), self.add_task_button.height())
        wrapper_height = max(
            completed_bottom + 4 if completed else 4,
            placeholder_active_bottom + 4 if placeholder_active_bottom else 4,
            current_y + active[-1].height() + 4 if active else 4,
            add_y + self.add_task_button.height() + 4 if show_add else 4,
        )
        return targets, add_target, wrapper_height, show_add

    def _set_accordion_open(self, open_state: bool, animated: bool = True) -> None:
        if self._accordion_open == open_state:
            return
        self._accordion_open = open_state
        self.recenter_ui(animated=animated)

    def recenter_ui(self, animated: bool = True, interrupt: bool = True) -> None:
        if animated and interrupt:
            self._interrupt_and_snap_animations()
        if not self.main_layout.isEnabled():
            self.main_layout.update()
            self.main_layout.activate()
        self.relayout_stripes(animated=animated)
        self._resize_window_to_fit(animated=animated)

    def relayout_stripes(self, animated: bool = False) -> None:
        if not hasattr(self, "stripe_wrapper"):
            return
        targets, add_target, wrapper_height, show_add = self._compute_layout_targets()
        self._last_layout_targets = {k: QRect(v) for k, v in targets.items()}
        self._last_add_target = QRect(add_target) if add_target is not None else None
        self.stripe_wrapper.setFixedHeight(self._compute_animation_bounds(targets, add_target, wrapper_height))
        self.add_task_button.setVisible(show_add)
        if add_target is not None and not animated:
            self.add_task_button.setGeometry(add_target)

        self._stack_animations = []
        for stripe, target in targets.items():
            if stripe.state == TaskStripe.COMPLETED:
                stripe.raise_()
            else:
                stripe.lower()
            if animated:
                start_rect = stripe.geometry()
                anim = QPropertyAnimation(stripe, b"geometry", self)
                anim.setDuration(320 if stripe.state == TaskStripe.COMPLETED else 260)
                anim.setStartValue(start_rect)
                anim.setEndValue(target)
                anim.setEasingCurve(
                    QEasingCurve.Type.OutCubic if self._accordion_open and stripe.state == TaskStripe.COMPLETED else QEasingCurve.Type.InOutQuart
                )
                self._register_animation(anim, stripe, target)
                anim.start()
                self._stack_animations.append(anim)
            else:
                stripe.setGeometry(target)

        if show_add and add_target is not None:
            if animated:
                anim = QPropertyAnimation(self.add_task_button, b"geometry", self)
                anim.setDuration(300)
                anim.setStartValue(self.add_task_button.geometry())
                anim.setEndValue(add_target)
                anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
                self._register_animation(anim, self.add_task_button, add_target)
                anim.start()
                self._stack_animations.append(anim)
            self.add_task_button.raise_()

    def _animate_add_task_sequence(self, new_stripe: TaskStripe) -> None:
        self._interrupt_and_snap_animations()
        epoch = self._animation_epoch
        targets, add_target, wrapper_height, show_add = self._compute_layout_targets()
        self.stripe_wrapper.setFixedHeight(self._compute_animation_bounds(targets, add_target, wrapper_height))
        self.add_task_button.setVisible(show_add)
        self._resize_window_to_fit(animated=False)
        if new_stripe not in targets:
            self.relayout_stripes(animated=False)
            return

        # Lock all existing stripes in place during the add choreography.
        for stripe in self.buttons:
            if stripe is new_stripe:
                continue
            if stripe in targets:
                stripe.setGeometry(targets[stripe])

        wrapper_width = max(0, self.stripe_wrapper.width())
        target = targets[new_stripe]
        start_rect = QRect(wrapper_width + 24, target.y(), target.width(), target.height())
        predicted_wrapper_height = max(
            self.stripe_wrapper.height(),
            start_rect.y() + start_rect.height() + 8,
            (add_target.y() + add_target.height() + 8) if (show_add and add_target is not None) else 0,
        )
        self.stripe_wrapper.setFixedHeight(predicted_wrapper_height)
        new_stripe.setGeometry(start_rect)
        new_stripe.raise_()
        self.add_task_button.setEnabled(False)

        self._stack_animations = []
        master = QParallelAnimationGroup(self)
        self._stack_animations.append(master)

        # Stage A (0-300ms): button drops down by 60px.
        btn_start = self.add_task_button.geometry()
        btn_drop = QRect(btn_start.x(), btn_start.y() + 60, btn_start.width(), btn_start.height())
        settle_anim = None
        if show_add and add_target is not None:
            drop_anim = QPropertyAnimation(self.add_task_button, b"geometry", self)
            drop_anim.setDuration(300)
            drop_anim.setStartValue(btn_start)
            drop_anim.setEndValue(btn_drop)
            drop_anim.setEasingCurve(QEasingCurve.Type.OutBack)
            master.addAnimation(drop_anim)
            self._register_animation(drop_anim, self.add_task_button, btn_drop)

            settle_anim = QPropertyAnimation(self.add_task_button, b"geometry", self)
            settle_anim.setDuration(220)
            settle_anim.setStartValue(btn_drop)
            settle_anim.setEndValue(add_target)
            settle_anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
            delay_settle = QSequentialAnimationGroup(self)
            delay_settle.addPause(300)
            delay_settle.addAnimation(settle_anim)
            master.addAnimation(delay_settle)
            self._stack_animations.extend([drop_anim, settle_anim, delay_settle])
            self._register_animation(settle_anim, self.add_task_button, add_target)

        # Stage B (150-600ms): stripe slides in from the right.
        bezier = QEasingCurve(QEasingCurve.Type.BezierSpline)
        bezier.addCubicBezierSegment(QPointF(0.22, 1.0), QPointF(0.36, 1.0), QPointF(1.0, 1.0))
        slide_anim = QPropertyAnimation(new_stripe, b"geometry", self)
        slide_anim.setDuration(450)
        slide_anim.setStartValue(start_rect)
        slide_anim.setEndValue(target)
        slide_anim.setEasingCurve(bezier)

        delay_group = QSequentialAnimationGroup(self)
        delay_group.addPause(150)
        delay_group.addAnimation(slide_anim)
        master.addAnimation(delay_group)
        self._stack_animations.extend([delay_group, slide_anim])
        self._register_animation(slide_anim, new_stripe, target)

        def finish_add() -> None:
            if epoch != self._animation_epoch or self._loading_state:
                return
            self.recenter_ui(animated=True, interrupt=False)
            self.add_task_button.setEnabled(True)

        master.finished.connect(finish_add)
        master.start()

    def _animate_completion_sequence(self, completed_stripe: TaskStripe) -> None:
        self._interrupt_and_snap_animations()
        epoch = self._animation_epoch
        self._completion_in_progress = True
        # Freeze layout to prevent one-frame lurch while we run absolute-position animation.
        self.main_layout.setEnabled(False)
        targets, add_target, wrapper_height, show_add = self._compute_layout_targets()
        # Keep wrapper tall enough for both current and target positions to avoid clipping/truncation.
        self.stripe_wrapper.setFixedHeight(self._compute_animation_bounds(targets, add_target, wrapper_height))
        self.add_task_button.setVisible(show_add)
        if completed_stripe not in targets:
            self._completion_in_progress = False
            self.main_layout.setEnabled(True)
            self.relayout_stripes(animated=True)
            return

        # Snapshot absolute coordinates before movement starts.
        snapshot: dict[QWidget, QRect] = {}
        for stripe in self.buttons:
            global_tl = stripe.mapToGlobal(QPoint(0, 0))
            local_tl = self.stripe_wrapper.mapFromGlobal(global_tl)
            snapshot[stripe] = QRect(local_tl.x(), local_tl.y(), stripe.width(), stripe.height())
        add_global = self.add_task_button.mapToGlobal(QPoint(0, 0))
        add_local = self.stripe_wrapper.mapFromGlobal(add_global)
        snapshot[self.add_task_button] = QRect(add_local.x(), add_local.y(), self.add_task_button.width(), self.add_task_button.height())
        wrapper_global = self.stripe_wrapper.mapToGlobal(QPoint(0, 0))
        wrapper_local = self.mapFromGlobal(wrapper_global)
        snapshot[self.stripe_wrapper] = QRect(wrapper_local.x(), wrapper_local.y(), self.stripe_wrapper.width(), self.stripe_wrapper.height())
        for widget, rect in snapshot.items():
            widget.setGeometry(rect)
        for stripe in self.buttons:
            stripe.move(snapshot[stripe].topLeft())
        self.add_task_button.move(snapshot[self.add_task_button].topLeft())

        completed_stripe.raise_()
        # Step 1 (0ms-400ms): celebration + grey-out fade; no movement.
        fade = QVariantAnimation(self)
        fade.setDuration(400)
        fade.setStartValue(float(completed_stripe.completion_fade))
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.InOutQuart)

        def on_fade(value) -> None:
            if epoch != self._animation_epoch or self._loading_state:
                return
            completed_stripe.completion_fade = float(value)
            completed_stripe.apply_theme(self.button_color)

        fade.valueChanged.connect(on_fade)

        # Step 2 (400ms-900ms): completed task slides to the pile.
        start_pos = completed_stripe.pos()
        end_pos = targets[completed_stripe].topLeft()
        slide_to_pile = QPropertyAnimation(completed_stripe, b"pos", self)
        slide_to_pile.setDuration(500)
        slide_to_pile.setStartValue(start_pos)
        slide_to_pile.setEndValue(end_pos)
        slide_to_pile.setEasingCurve(QEasingCurve.Type.InOutQuart)
        self._register_animation(slide_to_pile, completed_stripe, QRect(end_pos, completed_stripe.size()))

        # Step 3 (900ms-1400ms): final centering slide for all remaining widgets.

        def start_reshuffle() -> None:
            if epoch != self._animation_epoch or self._loading_state:
                self._finish_completion_sequence()
                return
            completed_stripe.move(targets[completed_stripe].topLeft())
            completed_stripe.raise_()
            settle_group = QParallelAnimationGroup(self)
            self._stack_animations = [settle_group]

            for stripe, target in targets.items():
                if stripe is completed_stripe:
                    continue
                anim = QPropertyAnimation(stripe, b"pos", self)
                anim.setDuration(420)
                anim.setStartValue(stripe.pos())
                anim.setEndValue(target.topLeft())
                anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
                settle_group.addAnimation(anim)
                self._register_animation(anim, stripe, target)

            if show_add and add_target is not None:
                add_anim = QPropertyAnimation(self.add_task_button, b"pos", self)
                add_anim.setDuration(420)
                add_anim.setStartValue(self.add_task_button.pos())
                add_anim.setEndValue(add_target.topLeft())
                add_anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
                settle_group.addAnimation(add_anim)
                self._register_animation(add_anim, self.add_task_button, add_target)

            if settle_group.animationCount() == 0:
                self._finish_completion_sequence()
                return

            settle_group.finished.connect(self._finish_completion_sequence)
            settle_group.start()

        slide_to_pile.finished.connect(start_reshuffle)

        sequence = QSequentialAnimationGroup(self)
        sequence.addAnimation(fade)
        sequence.addAnimation(slide_to_pile)
        self._completion_sequence_group = sequence
        sequence.start()
        self._stack_animations = [sequence]

    def _finish_completion_sequence(self) -> None:
        self._completion_in_progress = False
        self.main_layout.update()
        self.main_layout.activate()
        self.relayout_stripes(animated=False)
        self._resize_window_to_fit(animated=False)
        QTimer.singleShot(50, self._finalize_completion_enable)

    def _finalize_completion_enable(self) -> None:
        self.main_layout.setEnabled(True)
        self.main_layout.activate()
        self._save_current_day()

    def _resize_window_to_fit(self, animated: bool) -> None:
        if self.is_hibernated:
            return
        self.layout().activate()
        target_h = max(820, self.layout().sizeHint().height())
        target_w = max(300, self.width())
        if target_h == self.height() and target_w == self.width():
            return
        if animated:
            if self._window_resize_anim and self._window_resize_anim.state() == QAbstractAnimation.State.Running:
                self._window_resize_anim.stop()
            start = self.geometry()
            end = QRect(start.x(), start.y(), target_w, target_h)
            anim = QPropertyAnimation(self, b"geometry", self)
            anim.setDuration(250)
            anim.setStartValue(start)
            anim.setEndValue(end)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            self._window_resize_anim = anim
        else:
            self.resize(target_w, target_h)

    def get_app_time(self) -> datetime:
        return datetime.now() + self.time_offset

    def update_debug_overlay(self) -> None:
        app_time = self.get_app_time()
        debug_text_color = get_contrast_color(self.button_color if not self.sleep_mode else self.background_color)
        debug_bg = QColor(self.button_color if not self.sleep_mode else self.background_color)
        debug_bg = lerp_color(debug_bg, QColor("#000000"), 0.24)
        debug_bg.setAlpha(178)
        self.debug_label.setText(f"DEBUG TIME: {app_time:%H:%M}")
        self.debug_label.setStyleSheet(
            "font-size: 11px;"
            "font-weight: 700;"
            "letter-spacing: 0.8px;"
            "padding: 5px 12px;"
            "border-radius: 12px;"
            "border: 1px solid rgba(255, 255, 255, 55);"
            f"color: rgb({debug_text_color.red()}, {debug_text_color.green()}, {debug_text_color.blue()});"
            f"background-color: rgba({debug_bg.red()}, {debug_bg.green()}, {debug_bg.blue()}, {debug_bg.alpha()});"
        )
        self.debug_label.setVisible(self.debug_visible)
        self.debug_label.raise_()

    def mousePressEvent(self, event) -> None:
        self._reset_idle_timer()
        if self.is_hibernated and event.button() == Qt.MouseButton.LeftButton:
            self.exit_hibernate()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self._reset_idle_timer()
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.enter_hibernate()
        event.accept()

    def _animate_hibernate_hover(self, target_rect: QRect, target_opacity: float, duration: int = 100) -> None:
        if self._hibernate_anim_group and self._hibernate_anim_group.state() == QAbstractAnimation.State.Running:
            self._hibernate_anim_group.stop()
        g_anim = QPropertyAnimation(self, b"geometry", self)
        g_anim.setDuration(duration)
        g_anim.setStartValue(self.geometry())
        g_anim.setEndValue(target_rect)
        g_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        o_anim = QPropertyAnimation(self, b"windowOpacity", self)
        o_anim.setDuration(duration)
        o_anim.setStartValue(float(self.windowOpacity()))
        o_anim.setEndValue(target_opacity)
        o_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        group = QParallelAnimationGroup(self)
        group.addAnimation(g_anim)
        group.addAnimation(o_anim)
        self._hibernate_anim_group = group
        group.start()

    def enterEvent(self, event) -> None:
        if self.is_hibernated:
            if self._hibernate_anim_group and self._hibernate_anim_group.state() == QAbstractAnimation.State.Running:
                super().enterEvent(event)
                return
            self._hibernate_hovered = True
            rect = self._hibernate_target_geometry()
            scale = 1.05
            nw = int(rect.width() * scale)
            nh = int(rect.height() * scale)
            hover_rect = QRect(
                rect.x() - (nw - rect.width()) // 2,
                rect.y() - (nh - rect.height()) // 2,
                nw,
                nh,
            )
            self._animate_hibernate_hover(hover_rect, 0.32, 100)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self.is_hibernated and self._hibernate_hovered:
            if self._hibernate_anim_group and self._hibernate_anim_group.state() == QAbstractAnimation.State.Running:
                super().leaveEvent(event)
                return
            self._hibernate_hovered = False
            self._animate_hibernate_hover(self._hibernate_target_geometry(), 0.2, 100)
        super().leaveEvent(event)

    def keyPressEvent(self, event) -> None:
        self._reset_idle_timer()
        if self._focus_mode_active:
            if event.key() == Qt.Key.Key_Escape:
                self.close()
            event.accept()
            return
        key = event.key()
        if self._overlay_mode == "settings":
            if key == Qt.Key.Key_D:
                self.debug_mode_enabled = not self.debug_mode_enabled
                self._lifetime_stats_dirty = True
                self._save_lifetime_stats()
                self.info_overlay_body.setText(self._settings_overlay_text())
                event.accept()
                return
            elif key == Qt.Key.Key_1:
                self.current_palette = "yellow"
                self._lifetime_stats_dirty = True
                self._save_lifetime_stats()
                self.update_color_state()
                self.info_overlay_body.setText(self._settings_overlay_text())
                event.accept()
                return
            elif key == Qt.Key.Key_2:
                self.current_palette = "mint"
                self._lifetime_stats_dirty = True
                self._save_lifetime_stats()
                self.update_color_state()
                self.info_overlay_body.setText(self._settings_overlay_text())
                event.accept()
                return
            elif key == Qt.Key.Key_3:
                self.current_palette = "maroon"
                self._lifetime_stats_dirty = True
                self._save_lifetime_stats()
                self.update_color_state()
                self.info_overlay_body.setText(self._settings_overlay_text())
                event.accept()
                return
            elif key == Qt.Key.Key_4:
                self.current_palette = "grayscale"
                self._lifetime_stats_dirty = True
                self._save_lifetime_stats()
                self.update_color_state()
                self.info_overlay_body.setText(self._settings_overlay_text())
                event.accept()
                return

        if key == Qt.Key.Key_Space:
            self._toggle_overlay_mode("hotkeys")
            event.accept()
            return
        if key == Qt.Key.Key_C:
            self._toggle_overlay_mode("clock")
            event.accept()
            return
        if key == Qt.Key.Key_S:
            self._toggle_overlay_mode("stats")
            event.accept()
            return
        if key == Qt.Key.Key_B:
            self._toggle_overlay_mode("birds")
            event.accept()
            return
        if key == Qt.Key.Key_Q:
            self.go_to_default_today_view()
            event.accept()
            return
        if key == Qt.Key.Key_Tab:
            if self._handle_tab_hotkey():
                event.accept()
                return
        if key == Qt.Key.Key_Right:
            self.navigate_days(1)
            event.accept()
            return
        elif key == Qt.Key.Key_Left:
            self.navigate_days(-1)
            event.accept()
            return
        elif key == Qt.Key.Key_G:
            self._toggle_overlay_mode("settings")
            event.accept()
            return
        elif key == Qt.Key.Key_F:
            self._toggle_overlay_mode("full_tasks")
            event.accept()
            return
        elif key == Qt.Key.Key_Up:
            if self.debug_mode_enabled:
                self.time_offset += timedelta(minutes=10)
                self.update_color_state()
            event.accept()
            return
        elif key == Qt.Key.Key_Down:
            if self.debug_mode_enabled:
                self.time_offset -= timedelta(minutes=10)
                self.update_color_state()
            event.accept()
            return
        elif key == Qt.Key.Key_R:
            self.time_offset = timedelta(0)
        elif key == Qt.Key.Key_H:
            self.debug_visible = not self.debug_visible
            self.debug_label.setVisible(self.debug_visible)
            event.accept()
            return
        elif key == Qt.Key.Key_N:
            if self.debug_mode_enabled:
                self.nuke_all_task_data()
            event.accept()
            return
        elif key == Qt.Key.Key_Escape:
            self.close()
            return
        else:
            super().keyPressEvent(event)
            return

        self.update_color_state()
        event.accept()

    def toggle_add_button_visibility(self) -> None:
        return

    def nuke_all_task_data(self) -> None:
        if self._focus_mode_active:
            return
        self._interrupt_and_snap_animations()
        self.particles.clear()
        if hasattr(self, "particle_timer"):
            self.particle_timer.stop()
        with self.db:
            self.db.execute("DELETE FROM tasks")
        self.view_date = self._navigation_today()
        self.today_date = self.get_app_time().date()
        self._load_day(self.view_date)
        self._update_nav_buttons()
        if hasattr(self, "particle_overlay"):
            self.particle_overlay.update()

    def update_color_state(self) -> None:
        self._check_for_new_day()
        m = minute_of_day(self.get_app_time())
        target_bg, target_button, target_sleep, target_text, segment = self._compute_target_state(m)
        if self.current_segment is None:
            self.current_segment = segment
            self.sleep_mode = target_sleep
            self.pending_sleep_mode = target_sleep
            self.background_color = target_bg
            self.button_color = target_button
            self.text_color = target_text
            self.apply_dynamic_styles()
            self.update_debug_overlay()
            self.update()
            return

        if segment != self.current_segment:
            self._animate_color_transition(target_bg, target_button, target_text, target_sleep, segment)
            return

        self.sleep_mode = target_sleep
        self.pending_sleep_mode = target_sleep
        self.background_color = target_bg
        self.button_color = target_button
        self.text_color = target_text
        self.apply_dynamic_styles()
        self.update_debug_overlay()
        self.update()

    def _compute_target_state(self, minute: int) -> tuple[QColor, QColor, bool, QColor, int]:
        palette = self.PALETTES.get(self.current_palette, self.PALETTES["yellow"])
        
        morning_bg = QColor(palette["MORNING_BG"])
        morning_button = QColor(palette["MORNING_BUTTON"])
        afternoon_bg = QColor(palette["AFTERNOON_BG"])
        afternoon_button = QColor(palette["AFTERNOON_BUTTON"])
        flip_bg = QColor(palette["FLIP_BG"])
        flip_button = QColor(palette["FLIP_BUTTON"])
        evening_bg = QColor(palette["EVENING_BG"])
        evening_button = QColor(palette["EVENING_BUTTON"])

        if minute >= 1320 or minute < 240:
            bg = QColor(self.SLEEP_BG)
            button = evening_button
            text = QColor("#FFFFFF")
            return bg, button, True, text, 0

        keyframes: list[tuple[int, QColor, QColor]] = [
            (240, morning_bg, morning_button),     # 04:00
            (959, afternoon_bg, afternoon_button), # 15:59
            (960, flip_bg, flip_button),           # 16:00
            (1319, evening_bg, evening_button),    # 21:59
        ]
        start_min, start_bg, start_button = keyframes[0]
        end_min, end_bg, end_button = keyframes[-1]
        for idx in range(len(keyframes) - 1):
            a_min, a_bg, a_button = keyframes[idx]
            b_min, b_bg, b_button = keyframes[idx + 1]
            if a_min <= minute <= b_min:
                start_min, start_bg, start_button = a_min, a_bg, a_button
                end_min, end_bg, end_button = b_min, b_bg, b_button
                break
        span = max(1, end_min - start_min)
        t = (minute - start_min) / span
        bg = lerp_color(start_bg, end_bg, t)
        button = lerp_color(start_button, end_button, t)
        text = get_contrast_color(bg)
        segment = 1 if minute < 960 else 2
        return bg, button, False, text, segment

    def _animate_color_transition(
        self,
        target_bg: QColor,
        target_button: QColor,
        target_text: QColor,
        target_sleep: bool,
        target_segment: int,
    ) -> None:
        if self.color_anim is not None and self.color_anim.state() == QAbstractAnimation.State.Running:
            self.color_anim.stop()

        from_bg = QColor(self.background_color)
        from_button = QColor(self.button_color)
        from_text = QColor(self.text_color)
        self.pending_sleep_mode = target_sleep

        anim = QVariantAnimation(self)
        anim.setDuration(1000)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        def on_value_changed(value) -> None:
            t = float(value)
            self.background_color = lerp_color(from_bg, target_bg, t)
            self.button_color = lerp_color(from_button, target_button, t)
            self.text_color = lerp_color(from_text, target_text, t)
            self.apply_dynamic_styles(in_transition=True)
            self.update_debug_overlay()
            self.update()

        def on_finished() -> None:
            self.current_segment = target_segment
            self.sleep_mode = target_sleep
            self.pending_sleep_mode = target_sleep
            self.background_color = QColor(target_bg)
            self.button_color = QColor(target_button)
            self.text_color = QColor(target_text)
            self.apply_dynamic_styles(in_transition=False)
            self.update_debug_overlay()
            self.update()

        anim.valueChanged.connect(on_value_changed)
        anim.finished.connect(on_finished)
        self.color_anim = anim
        anim.start()

    def apply_dynamic_styles(self, in_transition: bool = False) -> None:
        self._update_overlay_theme()
        if self.is_hibernated:
            self.stripe_wrapper.hide()
            self.add_task_button.hide()
            self.sleep_label.hide()
            self.title.hide()
            self.back_button.hide()
            self.forward_button.hide()
            self.day_label.hide()
            self.debug_label.hide()
            return
        self.title.update()
        self.sleep_label.setStyleSheet(
            f"font-size: 20px; font-weight: 600; color: rgb({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()});"
        )
        self.day_label.setStyleSheet(
            "font-size: 18px; font-weight: 700; letter-spacing: 0.6px;"
            f"color: rgb({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()});"
        )

        if in_transition:
            # Keep lockout label hidden during fades; show only in settled sleep mode.
            self.stripe_wrapper.show()
            self.add_task_button.hide()
            self.sleep_label.hide()
        elif self.sleep_mode:
            self.stripe_wrapper.hide()
            self.add_task_button.hide()
            self.sleep_label.show()
        else:
            self.stripe_wrapper.show()
            self.add_task_button.hide()
            self.sleep_label.hide()

        for btn in self.buttons:
            btn.apply_theme(self.button_color)
        add_bg = lerp_color(self.button_color, QColor("#FFFFFF"), 0.08)
        add_text = get_contrast_color(add_bg)
        self.add_task_button.setStyleSheet(
            "QPushButton {"
            f"background-color: rgba({add_bg.red()}, {add_bg.green()}, {add_bg.blue()}, 210);"
            f"color: rgb({add_text.red()}, {add_text.green()}, {add_text.blue()});"
            "border: 1px solid rgba(255, 255, 255, 110);"
            "border-radius: 14px;"
            "font-size: 18px;"
            "font-weight: 700;"
            "padding: 0px;"
            "text-align: center;"
            "}"
            "QPushButton:hover {"
            f"background-color: rgba({add_bg.red()}, {add_bg.green()}, {add_bg.blue()}, 245);"
            "border: 1px solid rgba(255, 255, 255, 155);"
            "}"
        )
        nav_bg = lerp_color(self.button_color, QColor("#000000"), 0.18)
        nav_text = get_contrast_color(nav_bg)
        nav_css = (
            "QPushButton {"
            f"background-color: rgba({nav_bg.red()}, {nav_bg.green()}, {nav_bg.blue()}, 185);"
            f"color: rgb({nav_text.red()}, {nav_text.green()}, {nav_text.blue()});"
            "border: 1px solid rgba(255, 255, 255, 95);"
            "border-radius: 14px;"
            "font-weight: 700;"
            "padding: 0px;"
            "}"
            "QPushButton:hover { background-color: rgba(255, 255, 255, 48); }"
            "QPushButton:disabled { opacity: 0.45; }"
        )
        self.back_button.setStyleSheet(nav_css)
        self.forward_button.setStyleSheet(nav_css)
        if self._focus_mode_active:
            self._set_focus_tint()
            self.focus_tint_overlay.show()
            self.focus_tint_overlay.raise_()
            if self._focused_stripe is not None:
                self._focused_stripe.raise_()
        if hasattr(self, "full_task_overlay"):
            self.full_task_overlay.apply_theme(self.button_color)
        self.add_task_button.raise_()
        if hasattr(self, "particle_overlay"):
            self.particle_overlay.raise_()
        if self._overlay_mode is not None and hasattr(self, "info_overlay"):
            self.info_overlay.raise_()

    def spawn_confetti(self, global_pos: QPoint) -> None:
        if self.sleep_mode:
            return

        origin = QPointF(self.mapFromGlobal(global_pos))
        palette = [
            QColor("#FFD54F"),
            QColor("#FF8A65"),
            QColor("#4DD0E1"),
            QColor("#81C784"),
            QColor("#BA68C8"),
            QColor("#F06292"),
            QColor("#FFF176"),
        ]

        for _ in range(25):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2.0, 6.0)
            # Strong outward burst + gentle downward drift from gravity.
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - random.uniform(1.5, 4.0)

            particle = Particle(
                pos=QPointF(origin),
                vel=QPointF(vx, vy),
                color=random.choice(palette),
                radius=random.uniform(2.0, 4.8),
                life=1.0,
                fade_speed=random.uniform(0.012, 0.03),
            )
            self.particles.append(particle)

        if not self.particle_timer.isActive():
            self.particle_timer.start()
        if hasattr(self, "particle_overlay"):
            self.particle_overlay.raise_()
            self.particle_overlay.update()
        self.update()

    def update_particles(self) -> None:
        gravity = 0.12
        drag = 0.995

        alive: list[Particle] = []
        for p in self.particles:
            p.vel.setX(p.vel.x() * drag)
            p.vel.setY(p.vel.y() + gravity)
            p.pos += p.vel
            p.life -= p.fade_speed
            if p.life > 0:
                alive.append(p)

        self.particles = alive
        if not self.particles:
            self.particle_timer.stop()
        if hasattr(self, "particle_overlay"):
            self.particle_overlay.raise_()
            self.particle_overlay.update()
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.pill_path.isEmpty():
            radius = self.width() / 2
            self.pill_path = QPainterPath()
            self.pill_path.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter.setClipPath(self.pill_path)
        fill_color = QColor("#000000") if (self.is_hibernated and self._hibernate_from_focus) else self.background_color
        painter.fillPath(self.pill_path, fill_color)

        # Subtle border for separation on bright/dark desktops.
        outer_border = QColor(255, 255, 255, 42) if self.sleep_mode else QColor(0, 0, 0, 26)
        painter.setPen(QPen(outer_border, 1.4))
        painter.drawPath(self.pill_path)

        # Particle rendering is handled by ParticleOverlay (top-most layer).


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(build_lemon_icon())

    script_dir = Path(__file__).resolve().parent
    fonts_dir = script_dir / "fonts"
    lexend_family = None
    quicksand_family = None
    font_candidates: list[Path] = []
    if fonts_dir.exists() and fonts_dir.is_dir():
        font_candidates.extend(sorted(fonts_dir.rglob("*")))
    # Backward-compatible fallback in case fonts are next to the script.
    font_candidates.extend(sorted(script_dir.glob("*.ttf")))
    font_candidates.extend(sorted(script_dir.glob("*.otf")))

    for font_file in font_candidates:
        if not font_file.is_file():
            continue
        if font_file.suffix.lower() not in {".ttf", ".otf"}:
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id == -1:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if not families:
            continue
        lower_name = font_file.stem.lower()
        for family in families:
            family_lower = family.lower()
            if not lexend_family and ("lexend" in lower_name or "lexend" in family_lower):
                lexend_family = family
            if not quicksand_family and ("quicksand" in lower_name or "quicksand" in family_lower):
                quicksand_family = family
        if lexend_family and quicksand_family:
            break

    if lexend_family:
        app.setFont(QFont(lexend_family, 11))

    widget = LemonDoWidget(title_font_family=quicksand_family)
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
