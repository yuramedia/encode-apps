import unittest
from encode_apps.encoder import (
    EncodeSettings,
    MarathonEncodeSettings,
    MarathonEpisodeItem,
    ProbeResult,
    build_ffmpeg_command,
    build_marathon_ffmpeg_command,
)


class TestAudioDubbing(unittest.TestCase):
    def setUp(self):
        self.probe = ProbeResult(
            width=1920,
            height=1080,
            fps="24000/1001",
            video_bitrate="5000k",
            video_profile="main",
            video_level="4.1",
            audio_codec="aac",
            audio_bitrate="192k",
            audio_sample_rate="48000",
            audio_channels="2",
            duration_seconds=120.0,
        )

    def test_single_encode_with_dubbing_audio(self):
        settings = EncodeSettings(
            video_path="/media/ep01.mp4",
            ass_path="/temp/subs.ass",
            output_path="/media/ep01_out.mp4",
            audio_path="/media/ep01_indonesian_dub.mp3",
            probe=self.probe,
        )
        cmd = build_ffmpeg_command(settings)

        # Inputs should have video at 0 and audio at 1
        self.assertIn("-i", cmd)
        video_idx = cmd.index(settings.video_path)
        audio_idx = cmd.index(settings.audio_path)
        self.assertGreater(audio_idx, video_idx)

        # Map replacement audio 1:a:0 directly without audio filters
        self.assertIn("-map", cmd)
        map_indices = [i for i, x in enumerate(cmd) if x == "-map"]
        mapped_streams = [cmd[i + 1] for i in map_indices]
        self.assertEqual(mapped_streams, ["[outv]", "1:a:0"])

        # In single encode, no audio filters exist in filter_complex
        fc = cmd[cmd.index("-filter_complex") + 1]
        self.assertEqual(fc, "[0:v]ass=subs.ass,format=yuv420p[outv]")

        # AAC audio codec
        c_a_idx = cmd.index("-c:a")
        self.assertEqual(cmd[c_a_idx + 1], "aac")

    def test_single_encode_with_dubbing_audio_and_endcard(self):
        settings = EncodeSettings(
            video_path="/media/ep01.mp4",
            ass_path="/temp/subs.ass",
            output_path="/media/ep01_out.mp4",
            audio_path="/media/ep01_dub.wav",
            endcard_path="/media/endcard.png",
            endcard_seconds=5,
            probe=self.probe,
        )
        cmd = build_ffmpeg_command(settings)

        # Check inputs: [video, audio, loop endcard, anullsrc]
        self.assertIn(settings.video_path, cmd)
        self.assertIn(settings.audio_path, cmd)
        self.assertIn(settings.endcard_path, cmd)

        filter_idx = cmd.index("-filter_complex")
        fc = cmd[filter_idx + 1]

        # Dub (input 1) is formatted into [a0]; 3:a is the anullsrc endcard track
        self.assertIn("[1:a:0]aformat=sample_rates=48000:channel_layouts=stereo[a0]", fc)
        self.assertIn("[v0][a0][v1][3:a]concat=n=2:v=1:a=1[outv][outa]", fc)

    def test_marathon_with_mixed_dubbing(self):
        ep1 = MarathonEpisodeItem(
            video_path="/media/ep01.mp4",
            ass_path="/temp/subs_0.ass",
            audio_path="/media/ep01_dub.m4a",
        )
        ep2 = MarathonEpisodeItem(
            video_path="/media/ep02.mp4",
            ass_path="/temp/subs_1.ass",
            audio_path="",  # Native audio
        )
        settings = MarathonEncodeSettings(
            episodes=[ep1, ep2],
            output_path="/media/marathon_dub.mp4",
            probe=self.probe,
        )
        cmd = build_marathon_ffmpeg_command(settings)

        # Input order:
        # 0: ep1.video
        # 1: ep1.audio (dub)
        # 2: ep2.video
        self.assertEqual(cmd[cmd.index("-i") + 1], ep1.video_path)
        filter_idx = cmd.index("-filter_complex")
        fc = cmd[filter_idx + 1]

        # ep1 uses dub audio (input 1), ep2 its native audio (input 2)
        self.assertIn("[1:a:0]aformat=sample_rates=48000:channel_layouts=stereo[a0]", fc)
        self.assertIn("[2:a:0]aformat=sample_rates=48000:channel_layouts=stereo[a1]", fc)
        self.assertIn("[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]", fc)

    def test_marathon_with_dubbing_and_endcard(self):
        ep1 = MarathonEpisodeItem(
            video_path="/media/ep01.mp4",
            ass_path="/temp/subs_0.ass",
            audio_path="/media/ep01_dub.flac",
        )
        ep2 = MarathonEpisodeItem(
            video_path="/media/ep02.mp4",
            ass_path="/temp/subs_1.ass",
            audio_path="/media/ep02_dub.opus",
        )
        settings = MarathonEncodeSettings(
            episodes=[ep1, ep2],
            output_path="/media/marathon_all_dub.mp4",
            endcard_path="/media/endcard.png",
            endcard_seconds=10,
            probe=self.probe,
        )
        cmd = build_marathon_ffmpeg_command(settings)

        # 0: ep1.video
        # 1: ep1.audio
        # 2: ep2.video
        # 3: ep2.audio
        # 4: endcard.png
        # 5: anullsrc
        filter_idx = cmd.index("-filter_complex")
        fc = cmd[filter_idx + 1]

        self.assertIn("[v0][a0][v1][a1][v4][5:a]concat=n=3:v=1:a=1[outv][outa]", fc)


if __name__ == "__main__":
    unittest.main()
