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
        # HEVC Main 10 must become high10, not plain "main" (silent 8-bit downgrade)
        self.assertEqual(normalize_profile("Main 10"), "high10")
        self.assertEqual(normalize_profile("main10"), "high10")

    def test_normalize_level(self):
        from encode_apps.encoder import normalize_level
        # x264-style decimals pass through
        self.assertEqual(normalize_level("4.1"), "4.1")
        self.assertEqual(normalize_level("1.3"), "1.3")
        # HEVC level_idc values are converted to decimals
        self.assertEqual(normalize_level("120"), "4.0")
        self.assertEqual(normalize_level("150"), "5.0")
        self.assertEqual(normalize_level("90"), "3.0")
        # unusable values are dropped so "-level" is omitted entirely
        self.assertEqual(normalize_level(""), "")
        self.assertEqual(normalize_level("99"), "")

    def test_resolve_video_bitrate_floors_crf_sources(self):
        from encode_apps.encoder import resolve_video_bitrate
        # CRF/quality-mode source reports a meaningless 24 kbps
        probe = ProbeResult(width=1920, height=1080, fps="24000/1001",
                            video_bitrate="23905")
        out = resolve_video_bitrate("", probe)
        self.assertGreaterEqual(int(out), 3_900_000)
        # sane probed bitrate is kept
        self.assertEqual(resolve_video_bitrate("", ProbeResult(video_bitrate="8046655")),
                         "8046655")
        # explicit user bitrate always honoured
        self.assertEqual(resolve_video_bitrate("6000k", probe), "6000k")

    def test_hevc_source_produces_valid_x264_args(self):
        # HEVC Main 10 source: level_idc 120 previously aborted libx264.
        probe = ProbeResult(width=1920, height=1080, fps="25/1",
                            video_bitrate="23905", video_profile="Main 10",
                            video_level="120")
        cmd = build_ffmpeg_command(
            EncodeSettings(video_path="in.mkv", ass_path="subs.ass",
                           output_path="out.mp4", probe=probe)
        )
        self.assertEqual(cmd[cmd.index("-profile:v") + 1], "high10")
        level_idx = cmd.index("-level")
        self.assertEqual(cmd[level_idx + 1], "4.0")
        bv_idx = cmd.index("-b:v")
        self.assertGreaterEqual(int(cmd[bv_idx + 1]), 3_900_000)

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

    def test_video_only_source_encodes_without_audio_map(self):
        # A silent source (no audio stream) must not produce "-map 0:a:0",
        # which aborts the whole encode with "matches no streams".
        probe = ProbeResult(width=1920, height=1080, fps="25/1", video_bitrate="8046655")
        cmd = build_ffmpeg_command(
            EncodeSettings(video_path="in.mkv", ass_path="subs.ass",
                           output_path="out.mp4", probe=probe)
        )
        maps = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]
        self.assertEqual(maps, ["[outv]"])
        self.assertNotIn("-c:a", cmd)

    def test_video_only_source_with_endcard_uses_silent_track(self):
        probe = ProbeResult(width=1920, height=1080, fps="25/1", video_bitrate="8046655")
        cmd = build_ffmpeg_command(
            EncodeSettings(video_path="in.mkv", ass_path="subs.ass",
                           output_path="out.mp4", endcard_path="end.png", probe=probe)
        )
        fc = self._fc(cmd)
        self.assertNotIn("[a0]", fc)
        self.assertIn("[2:a]", fc)  # anullsrc carries both segments
        self.assertIn("-c:a", cmd)  # output still muxes the silent AAC track

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
                           output_path="out.mp4", probe=ProbeResult(audio_codec="aac"))
        )
        fc = self._fc(cmd)
        self.assertEqual(fc, "[0:v]ass=subs.ass,format=yuv420p[outv]")
        maps = [cmd[i + 1] for i, x in enumerate(cmd) if x == "-map"]
        self.assertEqual(maps, ["[outv]", "0:a:0"])
        self.assertNotIn("-af", cmd)  # cannot be combined with -filter_complex

    def test_endcard_audio_layout_follows_source(self):
        probe = ProbeResult(audio_codec="aac", audio_sample_rate="44100", audio_channels="6")
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
