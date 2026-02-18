import math
import random
import sys
from dataclasses import dataclass
from datetime import datetime

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
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget


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
    completed = pyqtSignal(QPoint)

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(68)
        self.setMaximumHeight(68)
        self.clicked.connect(self._on_clicked)
        self._anim_group: QSequentialAnimationGroup | None = None

    def _on_clicked(self) -> None:
        self.play_bounce_animation()
        self.completed.emit(QCursor.pos())

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

        self._drag_offset: QPoint | None = None
        self.particles: list[Particle] = []

        self._build_ui()
        self._setup_timers()
        self.update_color_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 36, 28, 36)
        layout.setSpacing(18)

        self.title = QLabel("Lemon Do")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size: 30px; font-weight: 700;")

        self.sleep_label = QLabel("Go to bed, come back tomorrow.")
        self.sleep_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sleep_label.setWordWrap(True)
        self.sleep_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        self.sleep_label.hide()

        self.buttons: list[TaskButton] = []
        for i in range(3):
            btn = TaskButton(f"Task Slot {i + 1}", self)
            btn.completed.connect(self.spawn_confetti)
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

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
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

    def update_color_state(self) -> None:
        m = minute_of_day(datetime.now())

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
        self.update()

    def apply_dynamic_styles(self) -> None:
        self.title.setStyleSheet(
            f"font-size: 30px; font-weight: 700; color: rgb({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()});"
        )
        self.sleep_label.setStyleSheet(
            f"font-size: 20px; font-weight: 600; color: rgb({self.text_color.red()}, {self.text_color.green()}, {self.text_color.blue()});"
        )

        button_css = (
            "QPushButton {"
            f"background-color: rgb({self.button_color.red()}, {self.button_color.green()}, {self.button_color.blue()});"
            "color: white;"
            "font-size: 20px;"
            "font-weight: 700;"
            "border: none;"
            "border-radius: 34px;"
            "padding: 12px 20px;"
            "}"
            "QPushButton:hover {"
            "filter: brightness(1.1);"
            "}"
            "QPushButton:pressed {"
            "padding-top: 14px;"
            "padding-bottom: 10px;"
            "}"
        )

        if self.sleep_mode:
            for btn in self.buttons:
                btn.hide()
            self.sleep_label.show()
        else:
            for btn in self.buttons:
                btn.show()
                btn.setStyleSheet(button_css)
            self.sleep_label.hide()

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
