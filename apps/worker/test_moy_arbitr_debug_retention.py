from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

import moy_arbitr_client


class FakePage:
    def __init__(self, html_bytes: int = 8, screenshot_bytes: int = 8):
        self.html = "h" * html_bytes
        self.screenshot_bytes = screenshot_bytes

    def content(self) -> str:
        return self.html

    def screenshot(self, *, path: str, **_kwargs) -> None:
        Path(path).write_bytes(b"p" * self.screenshot_bytes)


class DebugArtifactRetentionTests(TestCase):
    def test_save_enforces_byte_quota_and_keeps_newest_complete_captures(self) -> None:
        with TemporaryDirectory() as tmp:
            debug_dir = Path(tmp) / "debug"
            page = FakePage()
            stamps = ["20260723-000001", "20260723-000002", "20260723-000003"]
            with (
                mock.patch.object(moy_arbitr_client, "MOY_ARBITR_DEBUG_DIR", str(debug_dir)),
                mock.patch.object(moy_arbitr_client, "MOY_ARBITR_DEBUG_MAX_BYTES", 42),
                mock.patch.object(moy_arbitr_client.time, "strftime", side_effect=stamps),
                mock.patch.object(moy_arbitr_client, "LAST_BROWSER_EVENTS", ["event"]),
            ):
                for job_id in range(1, 4):
                    moy_arbitr_client._save_debug_artifacts(
                        page,
                        job_id=job_id,
                        query_type="moy_arbitr_docs",
                        query_value=f"case-{job_id}",
                    )

            artifacts = sorted(debug_dir.iterdir())
            self.assertEqual(sum(path.stat().st_size for path in artifacts), 42)
            self.assertEqual(len(artifacts), 6)
            self.assertFalse(any("20260723-000001" in path.name for path in artifacts))
            for stamp in stamps[1:]:
                self.assertEqual(sum(stamp in path.name for path in artifacts), 3)

    def test_prune_only_removes_recognized_files_inside_debug_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            debug_dir = root / "debug"
            debug_dir.mkdir()
            state_path = root / "state.json"
            outside_path = root / "outside.html"
            unrecognized_path = debug_dir / "state.json"
            artifact_path = debug_dir / "job-old-query-value-20260723-000001.html"
            for path in (state_path, outside_path, unrecognized_path, artifact_path):
                path.write_text(path.name, encoding="utf-8")

            moy_arbitr_client._prune_debug_artifacts(debug_dir, 0)

            self.assertFalse(artifact_path.exists())
            self.assertEqual(state_path.read_text(encoding="utf-8"), "state.json")
            self.assertEqual(outside_path.read_text(encoding="utf-8"), "outside.html")
            self.assertEqual(unrecognized_path.read_text(encoding="utf-8"), "state.json")

    def test_prune_tolerates_stat_and_unlink_failures(self) -> None:
        with TemporaryDirectory() as tmp:
            debug_dir = Path(tmp)
            stat_failure = debug_dir / "job-1-query-stat-20260723-000001.log"
            unlink_failure = debug_dir / "job-2-query-unlink-20260723-000002.log"
            removable = debug_dir / "job-3-query-ok-20260723-000003.log"
            for path in (stat_failure, unlink_failure, removable):
                path.write_text("diagnostic", encoding="utf-8")

            original_stat = Path.stat
            original_unlink = Path.unlink

            def flaky_stat(path: Path, *args, **kwargs):
                if path == stat_failure:
                    raise PermissionError("stat denied")
                return original_stat(path, *args, **kwargs)

            def flaky_unlink(path: Path, *args, **kwargs):
                if path == unlink_failure:
                    raise PermissionError("unlink denied")
                return original_unlink(path, *args, **kwargs)

            with (
                mock.patch.object(Path, "stat", flaky_stat),
                mock.patch.object(Path, "unlink", flaky_unlink),
            ):
                moy_arbitr_client._prune_debug_artifacts(debug_dir, 0)

            self.assertTrue(stat_failure.exists())
            self.assertTrue(unlink_failure.exists())
            self.assertFalse(removable.exists())


if __name__ == "__main__":
    import unittest

    unittest.main()
