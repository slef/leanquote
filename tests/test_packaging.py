"""Packaging regressions; run with python3 -m unittest discover -s tests -v.

All builds run in temporary source-only trees, never in the developer's checkout.
Requires a POSIX shell, zip/unzip, pdfLaTeX, and LEANQUOTE_TEX_ENGINE (default pdfLaTeX).
"""

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ENGINE = os.environ.get("LEANQUOTE_TEX_ENGINE", "pdflatex")
SOURCES = (
    "README.md", "LICENSE", "leanquote-export", "make-ctan.sh",
    "latex/leanquote.sty", "doc/leanquote-doc.tex", "example/example.tex",
    "example/Abstract.leanquote", "example/TranslationTiling/Abstract.lean",
    "lean/LeanQuoteExport.lean",
)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="leanquote packaging ")
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.source = self.work / "source tree"
        for name in SOURCES:
            destination = self.source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
            destination.chmod(0o600)
        # Deliberately omit any prebuilt PDF, even if one exists in the checkout.
        self.assertFalse((self.source / "doc/leanquote-doc.pdf").exists())
        self.sentinels = [self.source / name for name in (
            "build/unrelated/nested/sentinel", "build/leanquote/keep-me",
        )]
        for sentinel in self.sentinels:
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text("unrelated artifact\n", encoding="utf-8")
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.environment = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"])

    def command(self, arguments, *, cwd=None, success=True, environment=None):
        result = subprocess.run(
            arguments, cwd=cwd or self.work, env=environment or self.environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", timeout=180,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout[-8000:])
        return result

    def build(self, source=None, *, success=True):
        # Test a restrictive umask and invocation from outside the source tree.
        return self.command(
            ["sh", "-c", 'umask 077; exec sh "$1"', "sh",
             str((source or self.source) / "make-ctan.sh")], success=success,
        )

    def stub(self, name, body):
        script = self.bin / name
        script.write_text("#!/bin/sh\nset -eu\n" + body + "\n", encoding="utf-8")
        script.chmod(0o755)

    def fake_manual(self):
        self.stub("pdflatex", "printf '%s\\n' '%PDF-test' > leanquote-doc.pdf\n"
                  "printf '%s\\n' 'successful manual' > leanquote-doc.log")

    def assert_clean(self):
        self.assertEqual(list(self.source.glob(".leanquote-ctan.*")), [])
        for sentinel in self.sentinels:
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "unrelated artifact\n")

    def assert_archive(self, source=None):
        archive = (source or self.source) / "leanquote.zip"
        self.assertEqual(stat.S_IMODE(archive.stat().st_mode), 0o644)
        expected_files = {"leanquote/" + name for name in SOURCES}
        expected_files.add("leanquote/doc/leanquote-doc.pdf")
        expected_dirs = {"leanquote/", "leanquote/latex/", "leanquote/doc/",
                         "leanquote/lean/", "leanquote/example/",
                         "leanquote/example/TranslationTiling/"}
        with zipfile.ZipFile(archive) as package:
            self.assertEqual(len(package.infolist()), len(expected_files | expected_dirs))
            self.assertEqual(set(package.namelist()), expected_files | expected_dirs)
            self.assertIsNone(package.testzip())
            for entry in package.infolist():
                executable = entry.filename in {
                    "leanquote/leanquote-export", "leanquote/make-ctan.sh",
                }
                expected_mode = 0o755 if entry.is_dir() or executable else 0o644
                self.assertEqual(entry.create_system, 3, entry.filename)
                self.assertEqual(stat.S_IMODE(entry.external_attr >> 16), expected_mode,
                                 entry.filename)
            self.assertTrue(package.read("leanquote/doc/leanquote-doc.pdf").startswith(b"%PDF-"))
        return archive

    def test_contents_permissions_cleanup_and_replacement(self):
        self.fake_manual()
        # A stale member must not survive when replacing an existing archive.
        with zipfile.ZipFile(self.source / "leanquote.zip", "w") as previous:
            previous.writestr("stale-member", "old archive")
        self.build()
        self.assert_archive()
        self.assert_clean()

    def test_failed_archive_preserves_previous_archive_and_cleans_staging(self):
        self.fake_manual()
        self.stub("zip", "printf '%s\\n' partial > leanquote.zip\nexit 42")
        archive = self.source / "leanquote.zip"
        archive.write_bytes(b"previous archive")
        self.build(success=False)
        self.assertEqual(archive.read_bytes(), b"previous archive")
        self.assert_clean()

    def test_failed_copy_cleans_staging(self):
        self.fake_manual()
        (self.source / "example/Abstract.leanquote").unlink()
        self.build(success=False)
        self.assertFalse((self.source / "leanquote.zip").exists())
        self.assert_clean()

    def test_failed_manual_preserves_previous_archive(self):
        self.stub("pdflatex", "printf '%s\\n' '! deliberate failure' > leanquote-doc.log\nexit 1")
        archive = self.source / "leanquote.zip"
        archive.write_bytes(b"previous archive")
        result = self.build(success=False)
        self.assertIn("manual build failed", result.stdout)
        self.assertEqual(archive.read_bytes(), b"previous archive")
        self.assert_clean()

    def test_source_only_build_and_extracted_example(self):
        self.build()
        archive = self.assert_archive()
        self.assert_clean()
        extracted = self.work / "extracted"
        self.command(["unzip", "-q", str(archive), "-d", str(extracted)])
        package = extracted / "leanquote"
        for name in ("make-ctan.sh", "leanquote-export"):
            self.assertTrue(os.access(package / name, os.X_OK), name)
        # The README's build command must work using only the distributed files.
        (package / "doc/leanquote-doc.pdf").unlink()
        self.build(package)
        self.assert_archive(package)
        self.assertEqual(list(package.glob(".leanquote-ctan.*")), [])
        environment = dict(self.environment, TEXINPUTS="../latex:")
        self.command([ENGINE, "-halt-on-error", "-interaction=nonstopmode", "example.tex"],
                     cwd=package / "example", environment=environment)
        self.assertTrue((package / "example/example.pdf").read_bytes().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
