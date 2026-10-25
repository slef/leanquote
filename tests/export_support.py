"""Construct small, explicit export-format fixtures without running Lean."""


def make_export(code, *, name="value", source=None, axioms="", trace="build-a",
                source_path="A.lean", olean="A.olean"):
    if source is None:
        source = code
    lines = [
        "@@leanquote-export 2", "@@module A", "@@source " + source_path,
        "@@olean " + olean, "@@trace " + trace, "@@begin " + name,
        "@@axioms " + axioms,
    ]
    lines += ["@@code " + line for line in code.splitlines()]
    lines += ["@@end"]
    lines += ["@@src " + line for line in source.splitlines()]
    return "\n".join(lines) + "\n"


def export_files(code="def value : Nat := 1\n", **options):
    return {
        "A.lean": code,
        "A.leanquote": make_export(code, **options),
        "A.olean": "compiled",
        "A.trace": '{"depHash": "build-a"}',
    }
