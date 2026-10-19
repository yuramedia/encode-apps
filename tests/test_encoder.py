import unittest
from encode_apps.encoder import (
    EncodeSettings,
    ProbeResult,
    audio_params,
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

    def _fc(self, cmd):
        return cmd[cmd.index("-filter_complex") + 1]

    def test_audio_is_never_stream_copied(self):
        # AAC source used to be passed through with ``-c:a copy``; broken source
        # timestamps then made the audio drop out part-way through.
        probe = ProbeResult(audio_codec="aac", audio_bitrate="192k")
        cmd = build_ffmpeg_command(
            EncodeSettings(video_path="in.mp4", ass_path="subs.ass",
                           output_path="out.mp4", probe=probe)
        )
        self.assertNotIn("copy", cmd)
        self.assertEqual(cmd[cmd.index("-c:a") + 1], "aac")

    def test_audio_normalised_and_first_stream_only(self):
        cmd = build_ffmpeg_command(
            EncodeSettings(video_path="in.mp4", ass_path="subs.ass",
                           output_path="out.mp4", probe=ProbeResult())
        )
        fc = self._fc(cmd)
        self.assertEqual(fc, "[0:v]ass=subs.ass,format=yuv420p[outv]")
        maps = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]
        self.assertEqual(maps, ["[outv]", "0:a:0"])
        self.assertNotIn("-af", cmd)  # cannot be combined with -filter_complex

    def test_endcard_audio_layout_follows_source(self):
        probe = ProbeResult(audio_sample_rate="44100", audio_channels="6")
        cmd = build_ffmpeg_command(
            EncodeSettings(video_path="in.mp4", ass_path="subs.ass",
                           output_path="out.mp4", endcard_path="end.png", probe=probe)
        )
        joined = " ".join(cmd)
        self.assertIn("anullsrc=r=44100:cl=5.1", joined)
        self.assertIn("channel_layouts=5.1", self._fc(cmd))
        self.assertEqual(cmd[cmd.index("-ac") + 1], "6")

    def test_unusual_channel_count_falls_back_to_stereo(self):
        probe = ProbeResult(audio_channels="3")
        sr, layout, ch = audio_params(probe)
        self.assertEqual((sr, layout, ch), ("48000", "stereo", "2"))


if __name__ == "__main__":
    unittest.main()
