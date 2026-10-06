import importlib.util
import io
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cursor_sync", ROOT / "scripts/cursor_sync.py")
cursor_sync = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cursor_sync
spec.loader.exec_module(cursor_sync)
Frame = cursor_sync.Frame


def solid_frame(nominal, delay=0, alpha=255):
    pixel = struct.pack("<I", (alpha << 24) | (alpha << 16))  # premultiplied red
    return Frame(nominal, nominal, nominal, nominal // 4, nominal // 2, delay, pixel * nominal * nominal)


def sizes_in(data):
    return sorted({frame.nominal for frame in cursor_sync.read_xcursor(data)})


class XcursorFormatTest(unittest.TestCase):
    def test_round_trip(self):
        frames = [solid_frame(24, 50), solid_frame(24, 60), solid_frame(32, 50)]
        parsed = cursor_sync.read_xcursor(cursor_sync.write_xcursor(frames))
        self.assertEqual(parsed, frames)

    def test_rejects_other_files(self):
        with self.assertRaises(ValueError):
            cursor_sync.read_xcursor(b"\x89PNG....")

    def test_largest_frames_keeps_the_whole_animation(self):
        frames = [solid_frame(24, 1), solid_frame(32, 1), solid_frame(32, 2)]
        self.assertEqual([f.delay for f in cursor_sync.largest_frames(frames)], [1, 2])


class ScalingTest(unittest.TestCase):
    def test_scales_dimensions_and_hotspot(self):
        scaled = cursor_sync.scale_frame(solid_frame(32, 70), 54)
        self.assertEqual((scaled.nominal, scaled.width, scaled.height), (54, 54, 54))
        self.assertEqual((scaled.xhot, scaled.yhot), (14, 27))
        self.assertEqual(scaled.delay, 70)
        self.assertEqual(len(scaled.pixels), 4 * 54 * 54)

    def test_same_size_preserves_pixels(self):
        frame = solid_frame(32, alpha=128)
        self.assertEqual(cursor_sync.scale_frame(frame, 32).pixels, frame.pixels)

    def test_png_is_straight_alpha(self):
        png = cursor_sync.frame_png(solid_frame(8, alpha=128))
        image = Image.open(io.BytesIO(png))
        self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 128))

    def test_target_sizes_follow_monitor_scales_and_skip_smaller(self):
        self.assertEqual(cursor_sync.target_sizes(36, {1.0, 1.5}), [36, 54, 72])
        self.assertEqual(cursor_sync.target_sizes(36, set()), [36, 72])
        self.assertEqual(cursor_sync.target_sizes(24, {0.5, 1.25}), [24, 30, 48])


class HyprcursorTest(unittest.TestCase):
    def test_archive_lists_every_size_and_frame(self):
        source = [solid_frame(32, 100), solid_frame(32, 120)]
        scaled = {size: [cursor_sync.scale_frame(f, size) for f in source] for size in (36, 54)}
        archive = zipfile.ZipFile(io.BytesIO(cursor_sync.hyprcursor_archive(source, scaled)))
        meta = archive.read("meta.hl").decode()
        self.assertIn("hotspot_x = 0.25000000", meta)
        self.assertIn("define_size = 36, image-36-01.png, 120", meta)
        self.assertIn("define_size = 54, image-54-00.png, 100", meta)
        self.assertEqual(Image.open(io.BytesIO(archive.read("image-54-01.png"))).size, (54, 54))

    def test_static_cursor_has_no_delay(self):
        source = [solid_frame(32)]
        archive = cursor_sync.hyprcursor_archive(source, {36: [cursor_sync.scale_frame(source[0], 36)]})
        meta = zipfile.ZipFile(io.BytesIO(archive)).read("meta.hl").decode()
        self.assertIn("define_size = 36, image-36-00.png\n", meta)


class GenerationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.theme = self.root / "icons/Test"
        (self.theme / "cursors").mkdir(parents=True)
        (self.theme / "cursors/left_ptr").write_bytes(
            cursor_sync.write_xcursor([solid_frame(24), solid_frame(32)])
        )
        (self.theme / "cursors/default").symlink_to("left_ptr")
        (self.theme / "manifest.hl").write_text("name = Test\ncursors_directory = hc\n")
        (self.theme / "hc").mkdir()
        (self.theme / "hc/left_ptr.hlc").write_bytes(b"old")
        self.source = self.root / "sources/Test"

    def tearDown(self):
        self.tmp.cleanup()

    def generate(self):
        cursor_sync.snapshot_source(self.theme, self.theme, self.source)
        return cursor_sync.generate_assets(self.theme, self.theme, self.source, [36, 54])

    def test_both_formats_get_exactly_the_target_sizes(self):
        self.assertEqual(self.generate(), 1)
        self.assertEqual(sizes_in((self.theme / "cursors/left_ptr").read_bytes()), [36, 54])
        self.assertTrue((self.theme / "cursors/default").is_symlink())
        meta = zipfile.ZipFile(self.theme / "hc/left_ptr.hlc").read("meta.hl").decode()
        self.assertIn("define_size = 54", meta)
        self.assertNotIn("define_size = 24", meta)
        self.assertEqual(Path(self.theme / "hc/default.hlc").resolve().name, "left_ptr.hlc")

    def test_snapshot_keeps_original_art_and_is_reused(self):
        self.generate()
        self.assertEqual(sizes_in((self.source / "cursors/left_ptr").read_bytes()), [24, 32])
        self.assertEqual((self.source / "hyprcursor/hc/left_ptr.hlc").read_bytes(), b"old")
        digest = cursor_sync.source_digest(self.source)
        cursor_sync.generate_assets(self.theme, None, self.source, [48])
        self.assertEqual(cursor_sync.source_digest(self.source), digest)
        self.assertEqual(sizes_in((self.theme / "cursors/left_ptr").read_bytes()), [48])

    def test_refuses_to_snapshot_generated_output(self):
        self.generate()
        cursor_sync.shutil.rmtree(self.source)
        with self.assertRaises(RuntimeError):
            cursor_sync.snapshot_source(self.theme, None, self.source)


class ConfigTest(unittest.TestCase):
    def test_set_ini_keys_replaces_and_appends(self):
        text = "Xft.dpi: 96\nXcursor.size: 24\n"
        updated = cursor_sync.set_ini_keys(text, {"Xcursor.size": "36", "Xcursor.theme": "T"}, ": ")
        self.assertEqual(updated, "Xft.dpi: 96\nXcursor.size: 36\nXcursor.theme: T\n")

    def test_preference_falls_back_on_invalid_values(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
            handle.write('{"cursorSettings": {"theme": "T", "size": "big"}}')
            handle.flush()
            self.assertEqual(cursor_sync.read_preference(Path(handle.name)), ("T", cursor_sync.FALLBACK_SIZE))
        self.assertEqual(
            cursor_sync.read_preference(Path("/nonexistent")),
            (cursor_sync.FALLBACK_THEME, cursor_sync.FALLBACK_SIZE),
        )


if __name__ == "__main__":
    unittest.main()
