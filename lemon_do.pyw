import math
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import (
    QAbstractAnimation,
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
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QRegion,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
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


@dataclass
class Particle:
    pos: QPointF
    vel: QPointF
    color: QColor
    radius: float
    life: float
    fade_speed: float


class StripeTextEdit(QTextEdit):
    clicked = pyqtSignal()
    double_clicked = pyqtSignal()
    tab_move_requested = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setPlaceholderText("")

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

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

        self.editor = StripeTextEdit(self)
        self.editor.setReadOnly(False)
        self.editor.clicked.connect(self._on_click_inside)
        self.editor.double_clicked.connect(self._on_double_click_inside)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.tab_move_requested.connect(self._on_tab_move_requested)
        self.editor.setMouseTracking(True)

        self.check_button = QPushButton("✓", self)
        self.check_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_button.setFixedSize(30, 30)
        self.check_button.setVisible(False)
        self.check_button.clicked.connect(self._on_check_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(8)
        layout.addWidget(self.editor)
        layout.addWidget(self.check_button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.apply_theme(self._base_color)
        self._sync_state_with_text()
        self._adjust_height_to_content()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.reset_slot()
            event.accept()
            return
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._adjust_height_to_content()

    def _on_click_inside(self) -> None:
        if self.state == self.COMPLETED:
            return
        self._begin_inline_edit()

    def _on_double_click_inside(self) -> None:
        if self.state == self.COMPLETED:
            return
        self._begin_inline_edit()

    def _on_check_clicked(self) -> None:
        self.set_completed()

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

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._update_check_visibility()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._update_check_visibility()
        super().leaveEvent(event)

    def _update_check_visibility(self) -> None:
        show = self._is_hovered and self.state == self.ACTIVE and self.state != self.COMPLETED
        self.check_button.setVisible(show)

    def apply_theme(self, base_color: QColor) -> None:
        self._base_color = QColor(base_color)
        if self.state == self.COMPLETED:
            p = max(0.0, min(1.0, self.completion_fade))
            base_bg = QColor(self._base_color)
            completed_bg = QColor(55, 55, 55)
            mixed = lerp_color(base_bg, completed_bg, p)
            text_color = lerp_color(get_contrast_color(base_bg), QColor("#B0B0B0"), p)
            alpha = int(210 - (45 * p))
            frame_css = (
                f"background-color: rgba({mixed.red()}, {mixed.green()}, {mixed.blue()}, {alpha});"
                "border-radius: 0px; border: 1px solid rgba(220, 220, 220, 28);"
            )
            font = QFont(self.editor.font())
            font.setStrikeOut(False)
            font.setItalic(False)
            self.editor.setFont(font)
            self.editor.setCursor(Qt.CursorShape.ForbiddenCursor)
            self._placeholder_color = QColor(210, 210, 210, 90)
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

    def __init__(self, title_font_family: str | None = None) -> None:
        super().__init__()
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
        self.pill_path = QPainterPath()

        self._drag_offset: QPoint | None = None
        self.particles: list[Particle] = []
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_ui()
        self._position_title()
        self._position_debug_overlay()
        self._setup_shortcuts()
        self._setup_timers()
        self.update_color_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.main_layout = layout
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget(self)
        header.setFixedHeight(104)
        self.title = QLabel("Lemon Do", self)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont(self.title_font_family or self.font().family(), 30)
        title_font.setBold(True)
        self.title.setFont(title_font)
        self.title.setStyleSheet("color: rgb(20, 20, 20);")
        self.title.raise_()

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

        for _ in range(3):
            self.add_task_stripe(animate=False)
        self.relayout_stripes(animated=False)

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

    def _setup_shortcuts(self) -> None:
        self.toggle_add_shortcut = QShortcut(QKeySequence("A"), self)
        self.toggle_add_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.toggle_add_shortcut.activated.connect(self.toggle_add_button_visibility)

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

    def _position_title(self) -> None:
        title_w = max(120, self.width() - 56)
        title_h = 48
        x = int((self.width() - title_w) / 2)
        self.title.setGeometry(x, 50, title_w, title_h)
        self.title.raise_()

    def _position_debug_overlay(self) -> None:
        overlay_w = 160
        overlay_h = 26
        x = int((self.width() - overlay_w) / 2)
        y = self.height() - overlay_h - 12
        self.debug_label.setGeometry(x, y, overlay_w, overlay_h)

    def on_stripe_height_changed(self) -> None:
        self.relayout_stripes(animated=False)
        self._resize_window_to_fit(animated=False)
        self._position_debug_overlay()

    def add_task_stripe(self, animate: bool = True) -> None:
        stripe = TaskStripe(self.stripe_wrapper)
        stripe.completed.connect(self.spawn_confetti)
        stripe.height_changed.connect(self.on_stripe_height_changed)
        stripe.state_changed.connect(self.on_stripe_state_changed)
        stripe.focus_move_requested.connect(self.on_focus_move_requested)
        stripe.apply_theme(self.button_color)
        stripe.show()
        self.buttons.append(stripe)
        if animate:
            self._animate_add_task_sequence(stripe)
        else:
            self.relayout_stripes(animated=False)
            self._resize_window_to_fit(animated=False)

    def on_focus_move_requested(self, from_stripe: TaskStripe, direction: int) -> None:
        candidates = [b for b in self.buttons if b.state != TaskStripe.COMPLETED]
        if not candidates:
            return
        if from_stripe not in candidates:
            target = candidates[0]
            target.focus_for_input()
            return
        idx = candidates.index(from_stripe)
        next_idx = (idx + (1 if direction >= 0 else -1)) % len(candidates)
        candidates[next_idx].focus_for_input()

    def on_stripe_state_changed(self) -> None:
        stripe = self.sender()
        if isinstance(stripe, TaskStripe):
            if stripe.state == TaskStripe.COMPLETED and stripe.completion_rank is None:
                stripe.completion_rank = self._completed_counter
                self._completed_counter += 1
                self._animate_completion_sequence(stripe)
                return
            elif stripe.state != TaskStripe.COMPLETED and stripe.completion_rank is not None:
                stripe.completion_rank = None
        self.relayout_stripes(animated=True)

    def _compute_layout_targets(self) -> tuple[dict[TaskStripe, QRect], QRect | None, int, bool]:
        wrapper_width = max(0, self.stripe_wrapper.width())
        completed = [b for b in self.buttons if b.state == TaskStripe.COMPLETED]
        completed.sort(key=lambda b: b.completion_rank if b.completion_rank is not None else 10**9)
        active = [b for b in self.buttons if b.state != TaskStripe.COMPLETED]

        title_bottom = self.title.y() + self.title.height()
        # Reserve a clean "stack bay" above the active list.
        active_anchor_y = max(0, title_bottom + 18)
        completed_anchor_y = max(0, active_anchor_y - 38)
        targets: dict[TaskStripe, QRect] = {}

        completed_bottom = completed_anchor_y
        for idx, stripe in enumerate(completed):
            y = completed_anchor_y + idx * self.completed_step
            targets[stripe] = QRect(0, y, wrapper_width, stripe.height())
            completed_bottom = max(completed_bottom, y + stripe.height())

        active_start_y = completed_bottom + self.stripe_gap if completed else active_anchor_y
        current_y = active_start_y
        for idx, stripe in enumerate(active):
            if idx > 0:
                current_y += active[idx - 1].height() + self.stripe_gap
            targets[stripe] = QRect(0, current_y, wrapper_width, stripe.height())

        show_add = self.add_button_visible and not self.sleep_mode
        add_target: QRect | None = None
        if active and show_add:
            last_active = active[-1]
            last_rect = QRect(0, current_y, wrapper_width, last_active.height())
            add_y = last_rect.y() + last_rect.height() + self.add_button_gap
        elif completed and show_add:
            add_y = completed_bottom + self.add_button_gap
        else:
            add_y = self.add_button_gap
        add_x = max(0, (wrapper_width - self.add_task_button.width()) // 2)
        if show_add:
            add_target = QRect(add_x, add_y, self.add_task_button.width(), self.add_task_button.height())
        if show_add:
            wrapper_height = add_y + self.add_task_button.height() + 4
        elif active:
            wrapper_height = current_y + active[-1].height() + 4
        elif completed:
            wrapper_height = completed_bottom + 4
        else:
            wrapper_height = 4
        return targets, add_target, wrapper_height, show_add

    def relayout_stripes(self, animated: bool = False) -> None:
        if not hasattr(self, "stripe_wrapper"):
            return
        targets, add_target, wrapper_height, show_add = self._compute_layout_targets()
        self.stripe_wrapper.setFixedHeight(wrapper_height)
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
                anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
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
                anim.start()
                self._stack_animations.append(anim)
            self.add_task_button.raise_()

    def _animate_add_task_sequence(self, new_stripe: TaskStripe) -> None:
        targets, add_target, wrapper_height, show_add = self._compute_layout_targets()
        self.stripe_wrapper.setFixedHeight(wrapper_height)
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

        def finish_add() -> None:
            self.relayout_stripes(animated=False)
            self._resize_window_to_fit(animated=False)
            if show_add and add_target is not None:
                self.add_task_button.setGeometry(add_target)
            self.add_task_button.raise_()
            self.add_task_button.setEnabled(True)

        master.finished.connect(finish_add)
        master.start()

    def _animate_completion_sequence(self, completed_stripe: TaskStripe) -> None:
        # Freeze layout to prevent one-frame lurch while we run absolute-position animation.
        self.main_layout.setEnabled(False)
        targets, add_target, wrapper_height, show_add = self._compute_layout_targets()
        # Keep wrapper tall enough for both current and target positions to avoid clipping/truncation.
        current_bottom = 0
        for stripe in self.buttons:
            current_bottom = max(current_bottom, stripe.geometry().y() + stripe.geometry().height())
        current_bottom = max(current_bottom, self.add_task_button.geometry().y() + self.add_task_button.height())
        target_bottom = 0
        for rect in targets.values():
            target_bottom = max(target_bottom, rect.y() + rect.height())
        if show_add and add_target is not None:
            target_bottom = max(target_bottom, add_target.y() + add_target.height())
        self.stripe_wrapper.setFixedHeight(max(wrapper_height, current_bottom + 4, target_bottom + 4))
        self.add_task_button.setVisible(show_add)
        if completed_stripe not in targets:
            self.main_layout.setEnabled(True)
            self.relayout_stripes(animated=True)
            return

        # Snapshot every geometry before movement starts.
        snapshot: dict[QWidget, QRect] = {}
        for stripe in self.buttons:
            snapshot[stripe] = QRect(stripe.geometry())
        snapshot[self.add_task_button] = QRect(self.add_task_button.geometry())
        snapshot[self.stripe_wrapper] = QRect(self.stripe_wrapper.geometry())
        for widget, rect in snapshot.items():
            widget.setGeometry(rect)

        completed_stripe.raise_()
        # Step 1 (0ms-400ms): celebration + grey-out fade; no movement.
        fade = QVariantAnimation(self)
        fade.setDuration(400)
        fade.setStartValue(float(completed_stripe.completion_fade))
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.InOutQuart)

        def on_fade(value) -> None:
            completed_stripe.completion_fade = float(value)
            completed_stripe.apply_theme(self.button_color)

        fade.valueChanged.connect(on_fade)

        # Step 2 (400ms-900ms): completed task slides to the pile.
        start_rect = completed_stripe.geometry()
        end_rect = QRect(targets[completed_stripe])
        if end_rect.y() >= start_rect.y():
            end_rect.moveTop(max(0, start_rect.y() - 8))
        slide_to_pile = QPropertyAnimation(completed_stripe, b"geometry", self)
        slide_to_pile.setDuration(500)
        slide_to_pile.setStartValue(start_rect)
        slide_to_pile.setEndValue(end_rect)
        slide_to_pile.setEasingCurve(QEasingCurve.Type.InOutQuart)

        # Step 3 (900ms-1400ms): reshuffle remaining tasks + plus button.

        def start_reshuffle() -> None:
            self._stack_animations = []
            for stripe, target in targets.items():
                if stripe is completed_stripe:
                    stripe.setGeometry(target)
                    stripe.raise_()
                    continue
                stripe.lower()
                anim = QPropertyAnimation(stripe, b"geometry", self)
                anim.setDuration(500)
                anim.setStartValue(stripe.geometry())
                anim.setEndValue(target)
                anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
                anim.start()
                self._stack_animations.append(anim)

            if show_add and add_target is not None:
                add_anim = QPropertyAnimation(self.add_task_button, b"geometry", self)
                add_anim.setDuration(500)
                add_anim.setStartValue(self.add_task_button.geometry())
                add_anim.setEndValue(add_target)
                add_anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
                add_anim.start()
                self._stack_animations.append(add_anim)
                self.add_task_button.raise_()

            self._resize_window_to_fit(animated=True)
            if self._stack_animations:
                self._stack_animations[0].finished.connect(self._finish_completion_sequence)
            else:
                self._finish_completion_sequence()

        slide_to_pile.finished.connect(start_reshuffle)

        sequence = QSequentialAnimationGroup(self)
        sequence.addAnimation(fade)
        sequence.addAnimation(slide_to_pile)
        self._completion_sequence_group = sequence
        sequence.start()
        self._stack_animations = [sequence]

    def _finish_completion_sequence(self) -> None:
        self.main_layout.setEnabled(True)
        self.main_layout.activate()
        self.relayout_stripes(animated=False)
        self._resize_window_to_fit(animated=False)

    def _resize_window_to_fit(self, animated: bool) -> None:
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
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Right:
            self.time_offset += timedelta(hours=1)
        elif key == Qt.Key.Key_Left:
            self.time_offset -= timedelta(hours=1)
        elif key == Qt.Key.Key_Up:
            self.time_offset += timedelta(minutes=10)
        elif key == Qt.Key.Key_Down:
            self.time_offset -= timedelta(minutes=10)
        elif key == Qt.Key.Key_R:
            self.time_offset = timedelta(0)
        elif key == Qt.Key.Key_H:
            self.debug_visible = not self.debug_visible
            self.debug_label.setVisible(self.debug_visible)
            event.accept()
            return
        elif key == Qt.Key.Key_A:
            self.toggle_add_button_visibility()
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
        self.add_button_visible = not self.add_button_visible
        self.relayout_stripes(animated=True)
        self._resize_window_to_fit(animated=True)

    def update_color_state(self) -> None:
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
        if minute >= 1320 or minute < 240:
            bg = QColor(self.SLEEP_BG)
            button = QColor(self.EVENING_BUTTON)
            text = QColor("#FFFFFF")
            return bg, button, True, text, 0

        keyframes: list[tuple[int, QColor, QColor]] = [
            (240, self.MORNING_BG, self.MORNING_BUTTON),     # 04:00
            (959, self.AFTERNOON_BG, self.AFTERNOON_BUTTON), # 15:59
            (960, self.FLIP_BG, self.FLIP_BUTTON),           # 16:00
            (1319, self.EVENING_BG, self.EVENING_BUTTON),    # 21:59
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
        self.title.setStyleSheet(
            f"color: rgb({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()});"
        )
        self.sleep_label.setStyleSheet(
            f"font-size: 20px; font-weight: 600; color: rgb({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()});"
        )

        if in_transition:
            # Keep lockout label hidden during fades; show only in settled sleep mode.
            self.stripe_wrapper.show()
            self.add_task_button.setVisible(self.add_button_visible)
            self.sleep_label.hide()
        elif self.sleep_mode:
            self.stripe_wrapper.hide()
            self.add_task_button.hide()
            self.sleep_label.show()
        else:
            self.stripe_wrapper.show()
            self.add_task_button.setVisible(self.add_button_visible)
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
        self.add_task_button.raise_()

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
        rect = QRectF(self.rect().adjusted(2, 2, -2, -2))
        painter.fillPath(self.pill_path, self.background_color)

        # Subtle border for separation on bright/dark desktops.
        outer_border = QColor(255, 255, 255, 42) if self.sleep_mode else QColor(0, 0, 0, 26)
        painter.setPen(QPen(outer_border, 1.4))
        painter.drawPath(self.pill_path)

        # Confetti particles rendered above UI.
        for p in self.particles:
            alpha = int(max(0, min(255, p.life * 255)))
            c = QColor(p.color)
            c.setAlpha(alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c)
            painter.drawEllipse(p.pos, p.radius, p.radius)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

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
