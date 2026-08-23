import unittest
from encode_apps.encoder import (
    EncodeSettings,
    ProbeResult,
    build_ffmpeg_command,
    normalize_profile,
)


class TestEncoder(unittest.TestCase):
    def test_normalize_profile(self):
        self.assertEqual(normalize_profile("Constrained Baseline"), "baseline")
        self.assertEqual(normalize_profile("constrained baseline"), "baseline")
        self.assertEqual(normalize_profile("Baseline"), "baseline")
        self.assertEqual(normalize_profile("Main"), "main")
        self.assertEqual(normalize_profile("High"), "high")
        self.assertEqual(normalize_profile("High 10"), "high10")
        self.assertEqual(normalize_profile("High 4:2:2"), "high422")
        self.assertEqual(normalize_profile("High 4:4:4 Predictive"), "high444")
        self.assertEqual(normalize_profile("unknown"), "main")

    def test_build_ffmpeg_command_constrained_baseline(self):
        probe = ProbeResult(
            width=1920,
            height=1080,
            fps="25/1",
            video_bitrate="8046655",
            video_profile="Constrained Baseline",
            video_level="1.3",
        )
        settings = EncodeSettings(
            video_path="input.mp4",
            ass_path="subs.ass",
            output_path="output.mp4",
            probe=probe,
        )
        cmd = build_ffmpeg_command(settings)
        profile_idx = cmd.index("-profile:v")
        self.assertEqual(cmd[profile_idx + 1], "baseline")


    def test_build_ffmpeg_command_with_endcard(self):
        probe = ProbeResult(
            width=1920,
            height=1080,
            fps="25/1",
            video_bitrate="8000000",
            audio_sample_rate="48000",
            audio_channels="2",
        )
        settings = EncodeSettings(
            video_path="input.mp4",
            ass_path="subs.ass",
            output_path="output.mp4",
            endcard_path="endcard.png",
            endcard_seconds=10,
            probe=probe,
        )
        cmd = build_ffmpeg_command(settings)
        self.assertIn("-loop", cmd)
        self.assertIn("endcard.png", cmd)
        self.assertIn("anullsrc=r=48000:cl=stereo", " ".join(cmd))
        self.assertIn("concat=n=2:v=1:a=1", " ".join(cmd))


if __name__ == "__main__":
    unittest.main()
