import sys
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from encode_apps.app import MainWindow
from encode_apps.queue import QueueItem

app = QApplication.instance() or QApplication(sys.argv)


class TestMainWindowQueue(unittest.TestCase):
    def setUp(self):
        self.window = MainWindow()

    def test_add_queue_item(self):
        item = QueueItem(
            video_path="/path/to/vid1.mp4",
            subtitle_path="/path/to/sub1.ass",
            output_path="/path/to/out1.mp4",
            audio_path="/path/to/dub1.mp3",
        )
        self.window._queue.append(item)
        self.window._refresh_queue_table()
        self.assertEqual(self.window._queue_table.rowCount(), 1)
        self.assertEqual(self.window._queue_table.item(0, 1).text(), "vid1.mp4")
        self.assertEqual(self.window._queue_table.item(0, 3).text(), "dub1.mp3")
        self.assertEqual(self.window._queue_table.item(0, 6).text(), "Pending")

    def test_clear_completed(self):
        item1 = QueueItem(video_path="v1.mp4", subtitle_path="s1.ass", output_path="o1.mp4", status="Completed")
        item2 = QueueItem(video_path="v2.mp4", subtitle_path="s2.ass", output_path="o2.mp4", status="Pending")
        self.window._queue = [item1, item2]
        self.window._on_clear_completed_queue()
        self.assertEqual(len(self.window._queue), 1)
        self.assertEqual(self.window._queue[0].video_path, "v2.mp4")

    def test_add_queue_item_while_encoding(self):
        self.window._is_queue_running = True
        self.assertTrue(self.window._add_queue_btn.isEnabled())

        item1 = QueueItem(video_path="v1.mp4", subtitle_path="s1.ass", output_path="o1.mp4", status="Encoding")
        item2 = QueueItem(video_path="v2.mp4", subtitle_path="s2.ass", output_path="o2.mp4", status="Pending")
        self.window._queue = [item1]
        self.window._queue.append(item2)
        self.window._refresh_queue_table()

        self.assertEqual(len(self.window._queue), 2)
        self.assertEqual(self.window._queue_table.rowCount(), 2)

    def test_remove_queue_item_while_encoding(self):
        self.window._is_queue_running = True
        item1 = QueueItem(video_path="v1.mp4", subtitle_path="s1.ass", output_path="o1.mp4", status="Encoding")
        item2 = QueueItem(video_path="v2.mp4", subtitle_path="s2.ass", output_path="o2.mp4", status="Pending")
        self.window._queue = [item1, item2]
        self.window._refresh_queue_table()

        # Select second row (Pending item)
        self.window._queue_table.selectRow(1)
        self.window._on_remove_selected_queue()

        self.assertEqual(len(self.window._queue), 1)
        self.assertEqual(self.window._queue[0].status, "Encoding")

    def test_double_click_row_loads_config(self):
        item = QueueItem(
            video_path="/path/to/my_video.mp4",
            subtitle_path="/path/to/my_sub.ass",
            audio_path="/path/to/my_dub.mp3",
            output_path="/path/to/my_output.mp4",
            preset="fast",
        )
        self.window._queue = [item]
        self.window._refresh_queue_table()
        table_item = self.window._queue_table.item(0, 1)

        self.window._on_table_double_clicked(table_item)
        self.assertEqual(self.window._video_edit.text(), "/path/to/my_video.mp4")
        self.assertEqual(self.window._sub_edit.text(), "/path/to/my_sub.ass")
        self.assertEqual(self.window._audio_edit.text(), "/path/to/my_dub.mp3")
        self.assertEqual(self.window._output_edit.text(), "/path/to/my_output.mp4")
        self.assertEqual(self.window._preset_combo.currentText(), "fast")
        self.assertEqual(self.window._preset_combo.currentText(), "fast")

    def test_marathon_mode_toggle(self):
        self.assertFalse(self.window._marathon_cb.isChecked())
        self.assertEqual(self.window._start_btn.text(), "▶  Start Queue")
        self.assertFalse(self.window._marathon_out_edit.isVisibleTo(self.window))

        self.window._marathon_cb.setChecked(True)
        self.assertEqual(self.window._start_btn.text(), "▶  Start Full Episode")
        self.assertTrue(self.window._marathon_out_edit.isVisibleTo(self.window))

    def test_start_marathon_mode(self):
        from unittest.mock import patch
        from encode_apps.worker import FullEpisodeWorker

        item1 = QueueItem(video_path="v1.mp4", subtitle_path="s1.ass", output_path="o1.mp4")
        item2 = QueueItem(video_path="v2.mp4", subtitle_path="s2.ass", output_path="o2.mp4")
        self.window._queue = [item1, item2]
        self.window._marathon_cb.setChecked(True)

        with patch("encode_apps.app.check_dependencies", return_value=[]), \
             patch.object(FullEpisodeWorker, "start") as mock_start:
            self.window._on_start_queue()
            self.assertTrue(mock_start.called)
            self.assertTrue(self.window._is_queue_running)
            self.assertIsNotNone(self.window._worker)

    def test_marathon_progress_and_finished(self):
        item = QueueItem(video_path="v1.mp4", subtitle_path="s1.ass", output_path="o1.mp4", status="Encoding")
        self.window._queue = [item]
        self.window._on_marathon_progress("frame=240 fps=24 time=00:00:10 speed=1.2x")
        self.assertEqual(item.progress_text, "frame=240 fps=24 time=00:00:10 speed=1.2x")

        with patch("PySide6.QtWidgets.QMessageBox.information"):
            self.window._on_marathon_finished(True, "Done")
            self.assertEqual(item.status, "Completed")
            self.assertEqual(item.progress_text, "✔ Full Episode")


if __name__ == "__main__":
    unittest.main()
