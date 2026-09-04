import unittest
from pathlib import Path
from encode_apps.queue import QueueItem, auto_pair_files


class TestQueue(unittest.TestCase):
    def test_queue_item_init(self):
        item = QueueItem(
            video_path="video.mp4",
            subtitle_path="subs.ass",
            output_path="out.mp4",
            audio_path="dub.mp3",
        )
        self.assertEqual(item.status, "Pending")
        self.assertEqual(item.audio_path, "dub.mp3")
        self.assertTrue(len(item.id) > 0)

    def test_auto_pair_files(self):
        paths = [
            Path("/path/to/Episode_01.mp4"),
            Path("/path/to/Episode_01.ass"),
            Path("/path/to/Episode_01.mp3"),
            Path("/path/to/Episode_02.mkv"),
            Path("/path/to/Episode_02.srt"),
            Path("/path/to/Episode_03.mp4"),
        ]
        pairs = auto_pair_files(paths)
        self.assertEqual(len(pairs), 3)

        v1, s1, a1 = pairs[0]
        self.assertEqual(v1.name, "Episode_01.mp4")
        self.assertIsNotNone(s1)
        self.assertEqual(s1.name, "Episode_01.ass")
        self.assertIsNotNone(a1)
        self.assertEqual(a1.name, "Episode_01.mp3")

        v2, s2, a2 = pairs[1]
        self.assertEqual(v2.name, "Episode_02.mkv")
        self.assertIsNotNone(s2)
        self.assertEqual(s2.name, "Episode_02.srt")
        self.assertIsNone(a2)

        v3, s3, a3 = pairs[2]
        self.assertEqual(v3.name, "Episode_03.mp4")
        self.assertIsNone(s3)
        self.assertIsNone(a3)


if __name__ == "__main__":
    unittest.main()
