"""Keep the shipped, independently verified example export complete and current."""

from pathlib import Path
import unittest

from test_exporter import parse_export


ROOT = Path(__file__).resolve().parents[1]


class ExampleTests(unittest.TestCase):
    def test_source_snapshot_and_verified_axioms(self):
        headers, entries, snapshot = parse_export(
            (ROOT / "example/Abstract.leanquote").read_text(encoding="utf-8")
        )
        self.assertEqual(headers["@@leanquote-export"], "2")
        self.assertEqual(headers["@@module"], "TranslationTiling.Abstract")
        self.assertEqual(headers["@@source"], "TranslationTiling/Abstract.lean")
        self.assertEqual(headers["@@olean"],
                         ".lake/build/lib/lean/TranslationTiling/Abstract.olean")
        self.assertTrue(headers["@@trace"])
        source = (ROOT / "example/TranslationTiling/Abstract.lean").read_text(
            encoding="utf-8"
        )
        self.assertEqual(snapshot, [line.rstrip() for line in source.splitlines()])
        # Independently checked with #print axioms in the original Lean project.
        empty = {"Point", "Prototile", "Tiles"}
        standard = {
            "Adjacent", "Connected", "tiling_coRE_complete", "tiling_undecidable",
            "RealPoint", "Solid", "RealTiles", "real_tiling_coRE_complete",
            "real_tiling_undecidable",
        }
        prefix = "TranslationTiling.Abstract."
        self.assertEqual(set(entries), {prefix + name for name in empty | standard})
        for name in empty | standard:
            with self.subTest(name=name):
                expected = ({"propext", "Classical.choice", "Quot.sound"}
                            if name in standard else set())
                self.assertEqual(set(entries[prefix + name]["axioms"]), expected)
                self.assertTrue(entries[prefix + name]["code"])


if __name__ == "__main__":
    unittest.main()
