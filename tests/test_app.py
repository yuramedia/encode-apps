import sys
import unittest
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
        )
        self.window._queue.append(item)
        self.window._refresh_queue_table()
        self.assertEqual(self.window._queue_table.rowCount(), 1)
        self.assertEqual(self.window._queue_table.item(0, 1).text(), "vid1.mp4")
        self.assertEqual(self.window._queue_table.item(0, 5).text(), "Pending")

    def test_clear_completed(self):
        item1 = QueueItem(video_path="v1.mp4", subtitle_path="s1.ass", output_path="o1.mp4", status="Completed")
        item2 = QueueItem(video_path="v2.mp4", subtitle_path="s2.ass", output_path="o2.mp4", status="Pending")
        self.window._queue = [item1, item2]
        self.window._on_clear_completed_queue()
        self.assertEqual(len(self.window._queue), 1)
        self.assertEqual(self.window._queue[0].video_path, "v2.mp4")


if __name__ == "__main__":
    unittest.main()
