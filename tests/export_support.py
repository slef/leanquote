"""Construct small, explicit export-format fixtures without running Lean."""


def make_export(code, *, name="value", source=None, axioms="", trace="build-a",
                source_path="A.lean", olean="A.olean", version=2,
                kind="declaration", statement=None):
    if source is None:
        source = code
    lines = [
        "@@leanquote-export " + str(version), "@@module A", "@@source " + source_path,
        "@@olean " + olean, "@@trace " + trace, "@@begin " + name,
        "@@axioms " + axioms,
    ]
    if version == 3:
        lines += ["@@kind " + kind]
    lines += ["@@code " + line for line in code.splitlines()]
    if statement is not None:
        assert version == 3
        lines += ["@@statement " + line for line in statement.splitlines()]
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
