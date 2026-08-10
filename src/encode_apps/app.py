"""Encode Apps — Hardsub GUI — main application window with Queue Encoding.

Run via ``encode-apps`` (console entry-point) or ``python -m encode_apps``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from encode_apps.encoder import check_dependencies
from encode_apps.queue import QueueItem, auto_pair_files
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
            padding: 6px 14px;
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
        QPushButton#addQueueBtn {
            background: #1d4ed8;
            border-color: #3b82f6;
            color: #fff;
            font-weight: bold;
        }
        QPushButton#addQueueBtn:hover { background: #2563eb; }
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
        QTableWidget {
            background-color: #242424;
            gridline-color: #3f3f3f;
            border: 1px solid #444;
            border-radius: 4px;
        }
        QHeaderView::section {
            background-color: #333;
            color: #ddd;
            padding: 4px 8px;
            border: 1px solid #444;
            font-weight: bold;
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
        self.setWindowTitle("Encode Apps — Hardsub Encoder & Queue")
        self.setMinimumSize(QSize(860, 720))
        self.setAcceptDrops(True)

        self._worker: EncodeWorker | None = None
        self._queue: list[QueueItem] = []
        self._is_queue_running = False
        self._current_queue_index = -1

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)

        # ── Input section ────────────────────────────────────────────
        grp_input = QGroupBox("Job Configurator")
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
        self._vbitrate_edit.setFixedWidth(100)
        lay_s.addWidget(self._vbitrate_edit)

        # Audio bitrate
        lay_s.addWidget(QLabel("Audio Bitrate:"))
        self._abitrate_edit = QLineEdit()
        self._abitrate_edit.setPlaceholderText("Auto-detect")
        self._abitrate_edit.setFixedWidth(100)
        lay_s.addWidget(self._abitrate_edit)

        lay_s.addSpacing(16)

        # Endcard duration
        lay_s.addWidget(QLabel("Endcard (s):"))
        self._endcard_spin = QSpinBox()
        self._endcard_spin.setRange(1, 60)
        self._endcard_spin.setValue(10)
        lay_s.addWidget(self._endcard_spin)

        lay_s.addStretch()

        self._add_queue_btn = QPushButton("+ Add to Queue")
        self._add_queue_btn.setObjectName("addQueueBtn")
        self._add_queue_btn.setMinimumHeight(32)
        self._add_queue_btn.clicked.connect(self._on_add_to_queue)
        lay_s.addWidget(self._add_queue_btn)

        root.addWidget(grp_settings)

        # ── Queue Table section ──────────────────────────────────────
        grp_queue = QGroupBox("Encoding Queue")
        lay_q = QVBoxLayout(grp_queue)

        self._queue_table = QTableWidget()
        self._queue_table.setColumnCount(7)
        self._queue_table.setHorizontalHeaderLabels(
            ["#", "Video", "Subtitle", "Output", "Preset", "Status", "Progress"]
        )
        self._queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._queue_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._queue_table.verticalHeader().setVisible(False)
        self._queue_table.setMinimumHeight(140)

        header = self._queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        lay_q.addWidget(self._queue_table)

        # Queue toolbar
        q_btn_row = QHBoxLayout()
        self._remove_selected_btn = QPushButton("Remove Selected")
        self._remove_selected_btn.clicked.connect(self._on_remove_selected_queue)
        q_btn_row.addWidget(self._remove_selected_btn)

        self._clear_completed_btn = QPushButton("Clear Completed")
        self._clear_completed_btn.clicked.connect(self._on_clear_completed_queue)
        q_btn_row.addWidget(self._clear_completed_btn)

        q_btn_row.addStretch()

        self._start_btn = QPushButton("▶  Start Queue")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setFixedHeight(34)
        self._start_btn.setFixedWidth(160)
        self._start_btn.clicked.connect(self._on_start_queue)
        q_btn_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("■  Stop Queue")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.setFixedHeight(34)
        self._cancel_btn.setFixedWidth(130)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._on_stop_queue)
        q_btn_row.addWidget(self._cancel_btn)

        lay_q.addLayout(q_btn_row)
        root.addWidget(grp_queue)

        # ── Progress & Log section ───────────────────────────────────
        grp_progress = QGroupBox("Progress & Log")
        lay_p = QVBoxLayout(grp_progress)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(False)
        lay_p.addWidget(self._progress_bar)

        self._status_label = QLabel("Siap.")
        self._status_label.setStyleSheet("color: #aaa; font-size: 13px;")
        lay_p.addWidget(self._status_label)

        self._log_area = QPlainTextEdit()
        self._log_area.setReadOnly(True)
        self._log_area.setMinimumHeight(120)
        lay_p.addWidget(self._log_area)

        root.addWidget(grp_progress)

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
        urls = event.mimeData().urls()
        paths = [Path(url.toLocalFile()) for url in urls if url.toLocalFile()]
        if not paths:
            return

        if len(paths) == 1:
            p = paths[0]
            ext = p.suffix.lower()
            if ext in (".mp4", ".mkv", ".avi", ".mov", ".ts", ".m2ts"):
                self._video_edit.setText(str(p))
                self._output_edit.setPlaceholderText(
                    str(p.with_name(p.stem + "_hardsub.mp4"))
                )
                return
            elif ext in (".srt", ".ass"):
                self._sub_edit.setText(str(p))
                is_srt = ext == ".srt"
                self._template_edit.setEnabled(is_srt)
                self._style_combo.setEnabled(is_srt)
                self._refresh_styles_btn.setEnabled(is_srt)
                return
            elif ext in (".png", ".jpg", ".jpeg", ".bmp"):
                self._endcard_edit.setText(str(p))
                return

        # Multi-file drop or batch auto-pairing
        pairs = auto_pair_files(paths)
        if not pairs:
            return

        template = self._template_edit.text().strip() or str(_DEFAULT_TEMPLATE)
        style = self._style_combo.currentText() or None
        preset = self._preset_combo.currentText()

        added_count = 0
        for video_p, sub_p in pairs:
            if not video_p.is_file():
                continue
            sub_str = str(sub_p) if sub_p and sub_p.is_file() else self._sub_edit.text().strip()
            if not sub_str:
                continue
            out_str = str(video_p.with_name(video_p.stem + "_hardsub.mp4"))

            item = QueueItem(
                video_path=str(video_p),
                subtitle_path=sub_str,
                output_path=out_str,
                endcard_path=self._endcard_edit.text().strip(),
                template_path=template,
                style=style,
                endcard_seconds=self._endcard_spin.value(),
                video_bitrate=self._vbitrate_edit.text().strip(),
                audio_bitrate=self._abitrate_edit.text().strip(),
                preset=preset,
            )
            self._queue.append(item)
            added_count += 1

        self._refresh_queue_table()
        if added_count > 0:
            self._log_area.appendPlainText(f"Menambahkan {added_count} job ke antrean via Drag & Drop.")

    # ── Queue management ─────────────────────────────────────────────

    def _build_queue_item_from_fields(self) -> QueueItem | None:
        video = self._video_edit.text().strip()
        subtitle = self._sub_edit.text().strip()

        if not video:
            QMessageBox.warning(self, "Error", "Harap pilih file video.")
            return None
        if not subtitle:
            QMessageBox.warning(self, "Error", "Harap pilih file subtitle.")
            return None
        if not Path(video).is_file():
            QMessageBox.warning(self, "Error", f"Video tidak ditemukan:\n{video}")
            return None
        if not Path(subtitle).is_file():
            QMessageBox.warning(self, "Error", f"Subtitle tidak ditemukan:\n{subtitle}")
            return None

        endcard = self._endcard_edit.text().strip()
        if endcard and not Path(endcard).is_file():
            QMessageBox.warning(self, "Error", f"Endcard image tidak ditemukan:\n{endcard}")
            return None

        output = self._output_edit.text().strip()
        if not output:
            p = Path(video)
            output = str(p.with_name(p.stem + "_hardsub.mp4"))

        template = self._template_edit.text().strip()
        style = self._style_combo.currentText() or None

        return QueueItem(
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
        )

    def _on_add_to_queue(self) -> None:
        item = self._build_queue_item_from_fields()
        if item:
            self._queue.append(item)
            self._refresh_queue_table()
            self._log_area.appendPlainText(f"Job ditambahkan ke antrean: {Path(item.video_path).name}")

    def _refresh_queue_table(self) -> None:
        self._queue_table.setRowCount(len(self._queue))
        for row, item in enumerate(self._queue):
            # 0: #
            it_num = QTableWidgetItem(str(row + 1))
            it_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._queue_table.setItem(row, 0, it_num)

            # 1: Video
            self._queue_table.setItem(row, 1, QTableWidgetItem(Path(item.video_path).name))

            # 2: Subtitle
            sub_name = Path(item.subtitle_path).name if item.subtitle_path else "-"
            self._queue_table.setItem(row, 2, QTableWidgetItem(sub_name))

            # 3: Output
            self._queue_table.setItem(row, 3, QTableWidgetItem(Path(item.output_path).name))

            # 4: Preset
            it_preset = QTableWidgetItem(item.preset)
            it_preset.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._queue_table.setItem(row, 4, it_preset)

            # 5: Status
            it_status = QTableWidgetItem(item.status)
            it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if item.status == "Completed":
                it_status.setForeground(QColor("#52b788"))
            elif item.status == "Encoding":
                it_status.setForeground(QColor("#f59e0b"))
            elif item.status == "Failed":
                it_status.setForeground(QColor("#ef4444"))
            elif item.status == "Cancelled":
                it_status.setForeground(QColor("#9ca3af"))
            self._queue_table.setItem(row, 5, it_status)

            # 6: Progress
            it_prog = QTableWidgetItem(item.progress_text or "-")
            self._queue_table.setItem(row, 6, it_prog)

    def _on_remove_selected_queue(self) -> None:
        selected_rows = sorted(
            list(set(index.row() for index in self._queue_table.selectedIndexes())),
            reverse=True,
        )
        has_encoding = False
        for row in selected_rows:
            if 0 <= row < len(self._queue):
                if self._queue[row].status == "Encoding":
                    has_encoding = True
                    continue
                del self._queue[row]

        if has_encoding:
            QMessageBox.warning(
                self, "Peringatan",
                "Job yang sedang di-encode tidak dapat dihapus. Hentikan antrean terlebih dahulu.",
            )
        self._refresh_queue_table()

    def _on_clear_completed_queue(self) -> None:
        self._queue = [
            item for item in self._queue
            if item.status not in ("Completed", "Failed", "Cancelled")
        ]
        self._refresh_queue_table()

    # ── Queue Execution ──────────────────────────────────────────────

    def _on_start_queue(self) -> None:
        if self._is_queue_running:
            return

        missing = check_dependencies()
        if missing:
            QMessageBox.critical(
                self, "Dependency Missing",
                f"Tidak ditemukan di PATH: {', '.join(missing)}\n\n"
                "Pastikan ffmpeg & ffprobe sudah terinstall.",
            )
            return

        # If queue is empty, try building a job from current fields
        if not self._queue:
            item = self._build_queue_item_from_fields()
            if item:
                self._queue.append(item)
                self._refresh_queue_table()

        pending_items = [item for item in self._queue if item.status == "Pending"]
        if not pending_items:
            QMessageBox.information(self, "Info", "Tidak ada job pending di antrean.")
            return

        self._is_queue_running = True
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

        self._run_next_queue_item()

    def _on_stop_queue(self) -> None:
        if not self._is_queue_running:
            return

        self._status_label.setText("Membatalkan antrean…")
        if self._worker:
            self._worker.cancel()
        self._is_queue_running = False

    def _run_next_queue_item(self) -> None:
        if not self._is_queue_running:
            return

        next_index = -1
        for idx, item in enumerate(self._queue):
            if item.status == "Pending":
                next_index = idx
                break

        if next_index == -1:
            # Queue complete
            self._is_queue_running = False
            self._start_btn.setEnabled(True)
            self._cancel_btn.setEnabled(False)
            self._progress_bar.setVisible(False)
            self._status_label.setText("✔ Semua Job Antrean Selesai!")
            self._status_label.setStyleSheet("color: #52b788; font-size: 13px; font-weight: bold;")
            QMessageBox.information(self, "Antrean Selesai", "Semua job dalam antrean telah selesai di-encode.")
            return

        self._current_queue_index = next_index
        item = self._queue[next_index]
        item.status = "Encoding"
        item.progress_text = "Memulai…"
        self._refresh_queue_table()

        self._log_area.appendPlainText(
            f"\n=== [Job {next_index + 1}/{len(self._queue)}] {Path(item.video_path).name} ==="
        )
        self._progress_bar.setVisible(True)
        self._status_label.setText(f"Encoding [{next_index + 1}/{len(self._queue)}]: {Path(item.video_path).name}")

        self._worker = EncodeWorker(
            video_path=item.video_path,
            subtitle_path=item.subtitle_path,
            output_path=item.output_path,
            endcard_path=item.endcard_path,
            template_path=item.template_path,
            style=item.style,
            endcard_seconds=item.endcard_seconds,
            video_bitrate=item.video_bitrate,
            audio_bitrate=item.audio_bitrate,
            preset=item.preset,
            parent=self,
        )

        # Connect signals with bound current item
        self._worker.log.connect(self._on_log)
        self._worker.progress.connect(lambda p, it=item: self._on_worker_progress(it, p))
        self._worker.finished.connect(lambda s, m, it=item: self._on_worker_finished(it, s, m))
        self._worker.start()

    def _on_log(self, msg: str) -> None:
        self._log_area.appendPlainText(msg)

    def _on_worker_progress(self, item: QueueItem, msg: str) -> None:
        item.progress_text = msg
        self._status_label.setText(msg)
        self._update_item_table_row(item)

    def _on_worker_finished(self, item: QueueItem, success: bool, msg: str) -> None:
        self._worker = None

        if success:
            item.status = "Completed"
            item.progress_text = "✔ Selesai"
            self._log_area.appendPlainText(f"Job selesai: {item.output_path}")
        else:
            if not self._is_queue_running:
                item.status = "Cancelled"
                item.progress_text = "Dibatalkan"
            else:
                item.status = "Failed"
                item.error_msg = msg
                item.progress_text = "✘ Gagal"
            self._log_area.appendPlainText(f"Job gagal/dibatalkan: {msg}")

        self._update_item_table_row(item)

        if self._is_queue_running:
            QTimer.singleShot(150, self._run_next_queue_item)
        else:
            self._progress_bar.setVisible(False)
            self._start_btn.setEnabled(True)
            self._cancel_btn.setEnabled(False)
            self._status_label.setText("Antrean dihentikan / dibatalkan.")
            self._status_label.setStyleSheet("color: #aaa; font-size: 13px;")

    def _update_item_table_row(self, item: QueueItem) -> None:
        try:
            row = self._queue.index(item)
        except ValueError:
            return

        it_status = QTableWidgetItem(item.status)
        it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.status == "Completed":
            it_status.setForeground(QColor("#52b788"))
        elif item.status == "Encoding":
            it_status.setForeground(QColor("#f59e0b"))
        elif item.status == "Failed":
            it_status.setForeground(QColor("#ef4444"))
        elif item.status == "Cancelled":
            it_status.setForeground(QColor("#9ca3af"))
        self._queue_table.setItem(row, 5, it_status)

        it_prog = QTableWidgetItem(item.progress_text or "-")
        self._queue_table.setItem(row, 6, it_prog)


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
