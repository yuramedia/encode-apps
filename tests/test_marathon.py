import unittest
from encode_apps.encoder import (
    MarathonEncodeSettings,
    MarathonEpisodeItem,
    ProbeResult,
    build_marathon_ffmpeg_command,
)


class TestMarathonEncoder(unittest.TestCase):
    def test_marathon_without_endcard(self):
        episodes = [
            MarathonEpisodeItem(video_path="ep01.mp4", ass_path="sub01.ass"),
            MarathonEpisodeItem(video_path="ep02.mp4", ass_path="sub02.ass"),
        ]
        probe = ProbeResult(
            width=1920,
            height=1080,
            fps="25/1",
            video_bitrate="8000000",
        )
        settings = MarathonEncodeSettings(
            episodes=episodes,
            output_path="full_episode.mp4",
            probe=probe,
        )
        cmd = build_marathon_ffmpeg_command(settings)
        cmd_str = " ".join(cmd)

        self.assertIn("-i ep01.mp4", cmd_str)
        self.assertIn("-i ep02.mp4", cmd_str)
        self.assertIn("[0:v]ass=sub01.ass", cmd_str)
        self.assertIn("[1:v]ass=sub02.ass", cmd_str)
        self.assertIn("concat=n=2:v=1:a=1", cmd_str)
        self.assertIn("full_episode.mp4", cmd_str)

    def test_marathon_with_endcard(self):
        episodes = [
            MarathonEpisodeItem(video_path="ep01.mp4", ass_path="sub01.ass"),
            MarathonEpisodeItem(video_path="ep02.mp4", ass_path="sub02.ass"),
            MarathonEpisodeItem(video_path="ep03.mp4", ass_path="sub03.ass"),
        ]
        probe = ProbeResult(
            width=1920,
            height=1080,
            fps="25/1",
            video_bitrate="8000000",
        )
        settings = MarathonEncodeSettings(
            episodes=episodes,
            output_path="full_marathon.mp4",
            endcard_path="endcard.png",
            endcard_seconds=10,
            probe=probe,
        )
        cmd = build_marathon_ffmpeg_command(settings)
        cmd_str = " ".join(cmd)

        self.assertIn("-i ep01.mp4", cmd_str)
        self.assertIn("-i ep02.mp4", cmd_str)
        self.assertIn("-i ep03.mp4", cmd_str)
        self.assertIn("-i endcard.png", cmd_str)
        self.assertIn("concat=n=4:v=1:a=1", cmd_str)


if __name__ == "__main__":
    unittest.main()
