import math
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPoint,
    QPointF,
    QRectF,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QRegion
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QInputDialog,
    QPushButton,
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


class TaskButton(QPushButton):
    EMPTY = "EMPTY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

    completed = pyqtSignal(QPoint)
    request_task_input = pyqtSignal(object)
    force_reset = pyqtSignal(object)

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(68)
        self.setMaximumHeight(68)
        self.clicked.connect(self._on_clicked)
        self._anim_group: QSequentialAnimationGroup | None = None
        self.state = self.EMPTY
        self.task_text = ""
        self._last_base_color = QColor("#1A237E")
        self.setText("Click to add task")

    def _on_clicked(self) -> None:
        if self.state == self.COMPLETED:
            return
        if self.state == self.EMPTY:
            self.request_task_input.emit(self)
            return

        self.play_bounce_animation()
        self.completed.emit(QCursor.pos())
        self.set_completed()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.reset_slot()
            self.force_reset.emit(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_active(self, task_text: str) -> None:
        clean_text = task_text.strip()
        if not clean_text:
            return
        self.state = self.ACTIVE
        self.task_text = clean_text
        self.setText(clean_text)

    def set_completed(self) -> None:
        self.state = self.COMPLETED
        if self.task_text:
            self.setText(self.task_text)
        self.setCursor(Qt.CursorShape.ForbiddenCursor)
        self.apply_style(self._last_base_color)

    def reset_slot(self) -> None:
        self.state = self.EMPTY
        self.task_text = ""
        self.setText("Click to add task")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_style(self._last_base_color)

    def apply_style(self, base_color: QColor) -> None:
        self._last_base_color = QColor(base_color)
        if self.state == self.COMPLETED:
            css = (
                "QPushButton {"
                "background-color: rgba(60, 60, 60, 130);"
                "color: rgb(165, 165, 165);"
                "font-size: 20px;"
                "font-weight: 700;"
                "text-decoration: line-through;"
                "border: 1px solid rgba(180, 180, 180, 90);"
                "border-radius: 34px;"
                "padding: 12px 20px;"
                "}"
            )
        else:
            hover = lerp_color(base_color, QColor("#FFFFFF"), 0.14)
            css = (
                "QPushButton {"
                f"background-color: rgb({base_color.red()}, {base_color.green()}, {base_color.blue()});"
                "color: white;"
                "font-size: 20px;"
                "font-weight: 700;"
                "border: none;"
                "border-radius: 34px;"
                "padding: 12px 20px;"
                "}"
                "QPushButton:hover {"
                f"background-color: rgb({hover.red()}, {hover.green()}, {hover.blue()});"
                "}"
                "QPushButton:pressed {"
                "padding-top: 14px;"
                "padding-bottom: 10px;"
                "}"
            )
        self.setStyleSheet(css)

    def play_bounce_animation(self) -> None:
        original = self.geometry()
        shrink_w = int(original.width() * 0.9)
        shrink_h = int(original.height() * 0.9)
        shrink_rect = original.adjusted(
            (original.width() - shrink_w) // 2,
            (original.height() - shrink_h) // 2,
            -(original.width() - shrink_w) // 2,
            -(original.height() - shrink_h) // 2,
        )

        anim_down = QPropertyAnimation(self, b"geometry")
        anim_down.setDuration(85)
        anim_down.setStartValue(original)
        anim_down.setEndValue(shrink_rect)
        anim_down.setEasingCurve(QEasingCurve.Type.InOutQuad)

        anim_up = QPropertyAnimation(self, b"geometry")
        anim_up.setDuration(160)
        anim_up.setStartValue(shrink_rect)
        anim_up.setEndValue(original)
        anim_up.setEasingCurve(QEasingCurve.Type.OutBounce)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(anim_down)
        group.addAnimation(anim_up)
        self._anim_group = group
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


class LemonDoWidget(QWidget):
    MORNING_BG = QColor("#FFF9C4")
    MORNING_BUTTON = QColor("#1A237E")

    AFTERNOON_BG = QColor("#FFB74D")
    AFTERNOON_BUTTON = QColor("#0D47A1")

    NIGHT_BG = QColor("#311B92")
    NIGHT_BUTTON = QColor("#FFD54F")

    SLEEP_BG = QColor("#000000")

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lemon Do")
        self.setFixedSize(330, 700)
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
        self.time_offset = timedelta(0)

        self._drag_offset: QPoint | None = None
        self.particles: list[Particle] = []
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_ui()
        self._position_debug_overlay()
        self._setup_timers()
        self.update_color_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 36, 28, 36)
        layout.setSpacing(18)

        self.title = QLabel("Lemon Do")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size: 30px; font-weight: 700;")

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

        self.buttons: list[TaskButton] = []
        for i in range(3):
            btn = TaskButton(f"Task Slot {i + 1}", self)
            btn.completed.connect(self.spawn_confetti)
            btn.request_task_input.connect(self.open_task_input_dialog)
            btn.force_reset.connect(self.on_slot_force_reset)
            self.buttons.append(btn)

        layout.addWidget(self.title)
        layout.addSpacing(4)
        layout.addWidget(self.sleep_label)
        layout.addStretch(1)
        for btn in self.buttons:
            layout.addWidget(btn)
        layout.addStretch(2)

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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        path = QPainterPath()
        radius = self.width() / 2
        path.addRoundedRect(QRectF(self.rect()), radius, radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)
        self._position_debug_overlay()

    def _position_debug_overlay(self) -> None:
        overlay_w = 160
        overlay_h = 26
        x = int((self.width() - overlay_w) / 2)
        y = 10
        self.debug_label.setGeometry(x, y, overlay_w, overlay_h)

    def get_app_time(self) -> datetime:
        return datetime.now() + self.time_offset

    def update_debug_overlay(self) -> None:
        app_time = self.get_app_time()
        self.debug_label.setText(f"DEBUG TIME: {app_time:%H:%M}")
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
        elif key == Qt.Key.Key_Escape:
            self.close()
            return
        else:
            super().keyPressEvent(event)
            return

        self.update_color_state()
        event.accept()

    def update_color_state(self) -> None:
        m = minute_of_day(self.get_app_time())

        if 240 <= m < 960:
            # Phase 1: 04:00 -> 16:00
            t = (m - 240) / (960 - 240)
            self.background_color = lerp_color(self.MORNING_BG, self.AFTERNOON_BG, t)
            self.button_color = lerp_color(self.MORNING_BUTTON, self.AFTERNOON_BUTTON, t)
            self.sleep_mode = False
        elif 960 <= m < 1320:
            # Phase 2: 16:00 -> 22:00
            t = (m - 960) / (1320 - 960)
            self.background_color = lerp_color(self.AFTERNOON_BG, self.NIGHT_BG, t)
            self.button_color = lerp_color(self.AFTERNOON_BUTTON, self.NIGHT_BUTTON, t)
            self.sleep_mode = False
        else:
            # Phase 3: 22:00 -> 04:00 hard stop.
            self.background_color = self.SLEEP_BG
            self.button_color = self.NIGHT_BUTTON
            self.sleep_mode = True

        if self.sleep_mode:
            self.text_color = QColor("#FFFFFF")
        else:
            # Keep readable title text as background deepens.
            brightness = (
                self.background_color.red() * 0.299
                + self.background_color.green() * 0.587
                + self.background_color.blue() * 0.114
            )
            self.text_color = QColor("#101010" if brightness > 140 else "#F5F5F5")

        self.apply_dynamic_styles()
        self.update_debug_overlay()
        self.update()

    def apply_dynamic_styles(self) -> None:
        self.title.setStyleSheet(
            f"font-size: 30px; font-weight: 700; color: rgb({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()});"
        )
        self.sleep_label.setStyleSheet(
            f"font-size: 20px; font-weight: 600; color: rgb({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()});"
        )

        if self.sleep_mode:
            for btn in self.buttons:
                btn.hide()
            self.sleep_label.show()
        else:
            for btn in self.buttons:
                btn.show()
                btn.apply_style(self.button_color)
            self.sleep_label.hide()

    def open_task_input_dialog(self, button: TaskButton) -> None:
        if self.sleep_mode or button.state != TaskButton.EMPTY:
            return
        task_text, ok = QInputDialog.getText(self, "Add Task", "Task:")
        if ok and task_text.strip():
            button.set_active(task_text)
            button.apply_style(self.button_color)

    def on_slot_force_reset(self, button: TaskButton) -> None:
        # Dev helper: right click restores Stage 1 instantly.
        button.apply_style(self.button_color)

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

        path = QPainterPath()
        radius = self.width() / 2
        rect = QRectF(self.rect().adjusted(2, 2, -2, -2))
        path.addRoundedRect(rect, radius, radius)

        painter.fillPath(path, self.background_color)

        # Subtle border for separation on bright/dark desktops.
        border = QColor(255, 255, 255, 35) if self.sleep_mode else QColor(0, 0, 0, 25)
        painter.setPen(QPen(border, 1.5))
        painter.drawPath(path)

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
    widget = LemonDoWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
