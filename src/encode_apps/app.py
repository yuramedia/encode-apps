"""Encode Apps — Hardsub GUI — main application window.

Run via ``encode-apps`` (console entry-point) or ``python -m encode_apps``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPalette, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from encode_apps.encoder import check_dependencies
from encode_apps.srt2ass import get_available_styles
from encode_apps.worker import EncodeWorker

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _RESOURCES = Path(sys._MEIPASS) / "encode_apps" / "resources"
else:
    _RESOURCES = Path(__file__).resolve().parent / "resources"

_DEFAULT_TEMPLATE = _RESOURCES / "Ani-One_ID_-_Template.ass"


# ───────────────────────────────────────────────────────────────────
# Dark palette
# ───────────────────────────────────────────────────────────────────

def _apply_dark_palette(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Base, QColor(40, 40, 40))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(50, 50, 50))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Button, QColor(50, 50, 50))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.BrightText, QColor(255, 60, 60))
    pal.setColor(QPalette.ColorRole.Link, QColor(100, 160, 255))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(80, 120, 215))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(110, 110, 110))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(110, 110, 110))
    app.setPalette(pal)

    app.setStyleSheet("""
        QGroupBox {
            border: 1px solid #555;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 14px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
        }
        QPushButton {
            padding: 6px 18px;
            border-radius: 4px;
            border: 1px solid #666;
            background: #3c3c3c;
        }
        QPushButton:hover { background: #505050; }
        QPushButton:pressed { background: #606060; }
        QPushButton:disabled { color: #777; border-color: #444; }
        QPushButton#startBtn {
            background: #2d6a4f;
            border-color: #40916c;
            color: #fff;
            font-weight: bold;
        }
        QPushButton#startBtn:hover { background: #40916c; }
        QPushButton#startBtn:disabled { background: #333; border-color: #444; color: #777; }
        QPushButton#cancelBtn {
            background: #6b1e1e;
            border-color: #a03030;
            color: #fff;
        }
        QPushButton#cancelBtn:hover { background: #a03030; }
        QLineEdit, QComboBox, QSpinBox {
            padding: 4px 8px;
            border: 1px solid #555;
            border-radius: 4px;
            background: #2a2a2a;
        }
        QPlainTextEdit {
            border: 1px solid #444;
            border-radius: 4px;
            background: #1a1a1a;
            font-family: "Cascadia Code", "Consolas", monospace;
            font-size: 12px;
        }
        QProgressBar {
            border: 1px solid #555;
            border-radius: 4px;
            text-align: center;
            background: #2a2a2a;
            height: 22px;
        }
        QProgressBar::chunk {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #2d6a4f, stop:1 #52b788);
            border-radius: 3px;
        }
    """)


# ───────────────────────────────────────────────────────────────────
# File picker row helper
# ───────────────────────────────────────────────────────────────────

def _file_row(label_text: str, placeholder: str = "", btn_text: str = "Browse…"):
    row = QHBoxLayout()
    lbl = QLabel(label_text)
    lbl.setFixedWidth(120)
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    btn = QPushButton(btn_text)
    btn.setFixedWidth(90)
    row.addWidget(lbl)
    row.addWidget(edit, 1)
    row.addWidget(btn)
    return row, edit, btn


# ───────────────────────────────────────────────────────────────────
# Main window
# ───────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Encode Apps — Hardsub Encoder")
        self.setMinimumSize(QSize(720, 640))
        self.setAcceptDrops(True)

        self._worker: EncodeWorker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)

        # ── Input section ────────────────────────────────────────────
        grp_input = QGroupBox("Input Files")
        lay_input = QVBoxLayout(grp_input)

        r, self._video_edit, btn = _file_row("Video", "Select video file (*.mp4 *.mkv *.avi *.mov)")
        btn.clicked.connect(self._browse_video)
        lay_input.addLayout(r)

        r, self._sub_edit, btn = _file_row("Subtitle", "Select subtitle file (*.srt *.ass)")
        btn.clicked.connect(self._browse_subtitle)
        lay_input.addLayout(r)

        r, self._endcard_edit, btn = _file_row("Endcard Image", "(Opsional) Select endcard image")
        btn.clicked.connect(self._browse_endcard)
        lay_input.addLayout(r)

        r, self._template_edit, btn = _file_row("Template ASS", str(_DEFAULT_TEMPLATE))
        self._template_edit.setText(str(_DEFAULT_TEMPLATE))
        btn.clicked.connect(self._browse_template)
        lay_input.addLayout(r)

        # Style dropdown
        style_row = QHBoxLayout()
        lbl = QLabel("Style")
        lbl.setFixedWidth(120)
        self._style_combo = QComboBox()
        self._style_combo.setMinimumWidth(200)
        self._refresh_styles_btn = QPushButton("Refresh")
        self._refresh_styles_btn.setFixedWidth(90)
        self._refresh_styles_btn.clicked.connect(self._reload_styles)
        style_row.addWidget(lbl)
        style_row.addWidget(self._style_combo, 1)
        style_row.addWidget(self._refresh_styles_btn)
        lay_input.addLayout(style_row)

        # Output
        r, self._output_edit, btn = _file_row("Output", "Auto: <video>_hardsub.mp4", "Save As…")
        btn.clicked.connect(self._browse_output)
        lay_input.addLayout(r)

        root.addWidget(grp_input)

        # ── Settings section ─────────────────────────────────────────
        grp_settings = QGroupBox("Encoding Settings")
        lay_s = QHBoxLayout(grp_settings)

        # Preset
        lay_s.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow", "placebo",
        ])
        self._preset_combo.setCurrentText("slow")
        lay_s.addWidget(self._preset_combo)

        lay_s.addSpacing(16)

        # Video bitrate
        lay_s.addWidget(QLabel("Video Bitrate:"))
        self._vbitrate_edit = QLineEdit()
        self._vbitrate_edit.setPlaceholderText("Auto-detect")
        self._vbitrate_edit.setFixedWidth(110)
        lay_s.addWidget(self._vbitrate_edit)

        # Audio bitrate
        lay_s.addWidget(QLabel("Audio Bitrate:"))
        self._abitrate_edit = QLineEdit()
        self._abitrate_edit.setPlaceholderText("Auto-detect")
        self._abitrate_edit.setFixedWidth(110)
        lay_s.addWidget(self._abitrate_edit)

        lay_s.addSpacing(16)

        # Endcard duration
        lay_s.addWidget(QLabel("Endcard (s):"))
        self._endcard_spin = QSpinBox()
        self._endcard_spin.setRange(1, 60)
        self._endcard_spin.setValue(10)
        lay_s.addWidget(self._endcard_spin)

        lay_s.addStretch()
        root.addWidget(grp_settings)

        # ── Progress section ─────────────────────────────────────────
        grp_progress = QGroupBox("Progress")
        lay_p = QVBoxLayout(grp_progress)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        lay_p.addWidget(self._progress_bar)

        self._status_label = QLabel("Siap.")
        self._status_label.setStyleSheet("color: #aaa; font-size: 13px;")
        lay_p.addWidget(self._status_label)

        self._log_area = QPlainTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setMinimumHeight(140)
        lay_p.addWidget(self._log_area)

        root.addWidget(grp_progress)

        # ── Action buttons ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._start_btn = QPushButton("▶  Start Encode")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setFixedHeight(38)
        self._start_btn.setFixedWidth(180)
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("■  Cancel")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.setFixedHeight(38)
        self._cancel_btn.setFixedWidth(120)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)

        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── Initial state ────────────────────────────────────────────
        self._reload_styles()

    # ── File browser helpers ─────────────────────────────────────────

    def _browse_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video", "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.ts *.m2ts);;All Files (*)",
        )
        if path:
            self._video_edit.setText(path)
            # Auto-fill output
            p = Path(path)
            self._output_edit.setPlaceholderText(
                str(p.with_name(p.stem + "_hardsub.mp4"))
            )

    def _browse_subtitle(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Subtitle", "",
            "Subtitle Files (*.srt *.ass);;All Files (*)",
        )
        if path:
            self._sub_edit.setText(path)
            ext = Path(path).suffix.lower()
            is_srt = ext == ".srt"
            self._template_edit.setEnabled(is_srt)
            self._style_combo.setEnabled(is_srt)
            self._refresh_styles_btn.setEnabled(is_srt)

    def _browse_endcard(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Endcard Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        )
        if path:
            self._endcard_edit.setText(path)

    def _browse_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Template ASS", "",
            "ASS Files (*.ass);;All Files (*)",
        )
        if path:
            self._template_edit.setText(path)
            self._reload_styles()

    def _browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Output As", "",
            "MP4 (*.mp4);;All Files (*)",
        )
        if path:
            self._output_edit.setText(path)

    def _reload_styles(self) -> None:
        self._style_combo.clear()
        tpl = self._template_edit.text().strip()
        if tpl and Path(tpl).is_file():
            try:
                styles = get_available_styles(tpl)
                self._style_combo.addItems(styles)
            except Exception:
                pass

    # ── Drag & drop ──────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path:
                continue
            ext = Path(path).suffix.lower()
            if ext in (".mp4", ".mkv", ".avi", ".mov", ".ts", ".m2ts"):
                self._video_edit.setText(path)
                p = Path(path)
                self._output_edit.setPlaceholderText(
                    str(p.with_name(p.stem + "_hardsub.mp4"))
                )
            elif ext in (".srt", ".ass"):
                self._sub_edit.setText(path)
                is_srt = ext == ".srt"
                self._template_edit.setEnabled(is_srt)
                self._style_combo.setEnabled(is_srt)
                self._refresh_styles_btn.setEnabled(is_srt)
            elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
                self._endcard_edit.setText(path)

    # ── Start / Cancel ───────────────────────────────────────────────

    def _on_start(self) -> None:
        # Validate
        video = self._video_edit.text().strip()
        subtitle = self._sub_edit.text().strip()

        if not video:
            QMessageBox.warning(self, "Error", "Harap pilih file video.")
            return
        if not subtitle:
            QMessageBox.warning(self, "Error", "Harap pilih file subtitle.")
            return
        if not Path(video).is_file():
            QMessageBox.warning(self, "Error", f"Video tidak ditemukan:\n{video}")
            return
        if not Path(subtitle).is_file():
            QMessageBox.warning(self, "Error", f"Subtitle tidak ditemukan:\n{subtitle}")
            return

        missing = check_dependencies()
        if missing:
            QMessageBox.critical(
                self, "Dependency Missing",
                f"Tidak ditemukan di PATH: {', '.join(missing)}\n\n"
                "Pastikan ffmpeg & ffprobe sudah terinstall.",
            )
            return

        endcard = self._endcard_edit.text().strip()
        if endcard and not Path(endcard).is_file():
            QMessageBox.warning(self, "Error", f"Endcard image tidak ditemukan:\n{endcard}")
            return

        output = self._output_edit.text().strip()
        if not output:
            p = Path(video)
            output = str(p.with_name(p.stem + "_hardsub.mp4"))

        template = self._template_edit.text().strip()
        style = self._style_combo.currentText() or None

        # ── Launch worker ────────────────────────────────────────────
        self._log_area.clear()
        self._progress_bar.setVisible(True)
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._status_label.setText("Memulai encoding…")

        self._worker = EncodeWorker(
            video_path=video,
            subtitle_path=subtitle,
            output_path=output,
            endcard_path=endcard,
            template_path=template,
            style=style,
            endcard_seconds=self._endcard_spin.value(),
            video_bitrate=self._vbitrate_edit.text().strip(),
            audio_bitrate=self._abitrate_edit.text().strip(),
            preset=self._preset_combo.currentText(),
            parent=self,
        )
        self._worker.log.connect(self._on_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._status_label.setText("Membatalkan…")

    # ── Worker signal handlers ───────────────────────────────────────

    def _on_log(self, msg: str) -> None:
        self._log_area.appendPlainText(msg)

    def _on_progress(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _on_finished(self, success: bool, msg: str) -> None:
        self._progress_bar.setVisible(False)
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._worker = None

        if success:
            self._status_label.setText("✔ Selesai!")
            self._status_label.setStyleSheet("color: #52b788; font-size: 13px; font-weight: bold;")
            self._log_area.appendPlainText(msg)
            QMessageBox.information(self, "Selesai", msg)
        else:
            self._status_label.setText("✘ Gagal")
            self._status_label.setStyleSheet("color: #e63946; font-size: 13px; font-weight: bold;")
            self._log_area.appendPlainText(f"ERROR: {msg}")
            QMessageBox.critical(self, "Error", msg)

        # Reset status colour after a moment
        self._status_label.setStyleSheet("color: #aaa; font-size: 13px;")


# ───────────────────────────────────────────────────────────────────
# Entry point
# ───────────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    _apply_dark_palette(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
