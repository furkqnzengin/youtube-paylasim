import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import upload  # noqa: E402

CONFIG = json.loads((ROOT / "metadata" / "categories.json").read_text())


class TitleTests(unittest.TestCase):
    def title(self, name):
        return upload.build_metadata(name, CONFIG, {})["title"]

    def test_titles(self):
        self.assertEqual(self.title("rays_heart.mp4"),
                         "Light Rays Inside a Mirror – Heart | Satisfying Simulation")
        self.assertEqual(self.title("harmonograph_9fold.mp4"),
                         "Harmonograph – 9-Fold | Satisfying Simulation")
        self.assertEqual(self.title("gap_50deg.mp4"),
                         "Ball Escaping the Gap – 50° | Satisfying Simulation")
        self.assertEqual(self.title("double_pendulum.mp4"),
                         "Double Pendulum Chaos | Satisfying Simulation")
        self.assertEqual(self.title("pendulum_wave_circle48.mp4"),
                         "Pendulum Wave – Circle 48 | Satisfying Simulation")
        self.assertEqual(self.title("unknown_thing.mp4"),
                         "Unknown Thing | Satisfying Simulation")

    def test_override(self):
        meta = upload.build_metadata("a.mp4", CONFIG, {"a.mp4": {"title": "X"}})
        self.assertEqual(meta["title"], "X")


class PickTests(unittest.TestCase):
    def test_no_same_category_twice(self):
        pending = ["rays_a.mp4", "rays_b.mp4", "rays_c.mp4", "gap_1.mp4"]
        published, order = [], []
        while pending:
            n = upload.pick_next(pending, published, CONFIG)
            order.append(n)
            pending.remove(n)
            published.append({"file": n, "category": n.split("_")[0]})
        self.assertEqual(order, ["rays_a.mp4", "gap_1.mp4", "rays_b.mp4", "rays_c.mp4"])

    def test_empty(self):
        self.assertIsNone(upload.pick_next([], [], CONFIG))


class UploadTests(unittest.TestCase):
    def test_upload_flow(self):
        session = mock.Mock()
        session.post.side_effect = [
            mock.Mock(status_code=200, json=lambda: {"access_token": "T"}),
            mock.Mock(status_code=200, headers={"Location": "https://up/1"}),
        ]
        session.put.return_value = mock.Mock(status_code=200, json=lambda: {"id": "abc"})
        env = {"YT_CLIENT_ID": "i", "YT_CLIENT_SECRET": "s", "YT_REFRESH_TOKEN": "r"}
        meta = upload.build_metadata("rays_heart.mp4", CONFIG, {})
        with mock.patch.dict("os.environ", env):
            res = upload.upload(session, Path(__file__), meta, "public")
        self.assertEqual(res["id"], "abc")
        init = session.post.call_args_list[1]
        self.assertEqual(init.kwargs["headers"]["Authorization"], "Bearer T")
        self.assertEqual(init.kwargs["json"]["status"]["privacyStatus"], "public")
        self.assertEqual(session.put.call_args.args[0], "https://up/1")


if __name__ == "__main__":
    unittest.main()
