# /// script
# requires-python = ">=3.11"
# dependencies = ["ezdxf>=1.4,<2", "reportlab>=4,<5", "pypdf>=6,<7"]
# ///
"""Synchronize current project versions and verify the committed build guide."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
TEXT_SLOTS = {
    "README.md": (
        ("badge/v", "-experimental-orange"),
        ('alt="v', ': experimental"'),
        ("> **v", " — experimental build:**"),
        ("current project version is **v", "**"),
    ),
    "STATUS.md": (("**v", " — experimental. Hardware qualification is in progress.**"),),
    "docs/build-guide/README.md": (("Edition: **v", " — experimental**"),),
}


def validate_version(value):
    if not re.fullmatch(VERSION_PATTERN, value):
        raise ValueError("Use a version in X.Y.Z form, without a v prefix or leading zeroes")
    return value


def project_version(root):
    return validate_version(json.loads((root / "package.json").read_text())["version"])


def bumped_version(version, amount):
    major, minor, patch = map(int, validate_version(version).split("."))
    return {"major": f"{major + 1}.0.0", "minor": f"{major}.{minor + 1}.0",
            "patch": f"{major}.{minor}.{patch + 1}"}[amount]


def semantic_label(names):
    selected = set(names) & {"patch", "minor", "major"}
    if len(selected) != 1:
        raise ValueError("Every PR requires exactly one version label: patch, minor or major. "
                         f"Found: {', '.join(sorted(selected)) or 'none'}")
    return selected.pop()


def current_version_files(root, version):
    """Compute all edits before writing; only designated current-version fields change."""
    validate_version(version)
    updates = {}
    for name, slots in TEXT_SLOTS.items():
        text = (root / name).read_text()
        for prefix, suffix in slots:
            pattern = re.escape(prefix) + VERSION_PATTERN + re.escape(suffix)
            text, count = re.subn(pattern, lambda match: prefix + version + suffix, text)
            if count != 1:
                raise ValueError(f"{name}: expected one current-version field after {prefix!r}; found {count}")
        updates[name] = text

    for name in ("package.json", "package-lock.json"):
        data = json.loads((root / name).read_text())
        data["version"] = version
        if name == "package-lock.json":
            data["packages"][""]["version"] = version
        updates[name] = json.dumps(data, indent=2) + "\n"

    name = "docs/build-guide/provenance.json"
    data = json.loads((root / name).read_text())
    data["edition"] = f"v{version} experimental"
    updates[name] = json.dumps(data, indent=2) + "\n"
    return updates


def synchronize_metadata(root, version):
    for name, text in current_version_files(root, version).items():
        (root / name).write_text(text)


def metadata_errors(root):
    version = project_version(root)
    expected = current_version_files(root, version)
    errors = []
    for name in TEXT_SLOTS:
        if (root / name).read_text() != expected[name]:
            errors.append(f"{name}: current version must be {version}")
    for name in ("package-lock.json", "docs/build-guide/provenance.json"):
        if json.loads((root / name).read_text()) != json.loads(expected[name]):
            errors.append(f"{name}: version metadata must match {version}")
    return errors


def pdf_errors(root):
    from pypdf import PdfReader

    version = project_version(root)
    name = "docs/Halloween-LEDs-Build-Guide.pdf"
    reader = PdfReader(root / name)
    errors = []
    if reader.metadata.title != f"Halloween LEDs v{version} | Build guide":
        errors.append(f"{name}: title must identify v{version}")
    if reader.metadata.subject != f"Illustrated assembly, wiring and commissioning; v{version} experimental edition":
        errors.append(f"{name}: subject must identify v{version}")
    provenance = json.loads((root / "docs/build-guide/provenance.json").read_text())
    if len(reader.pages) != provenance["pdf_pages"]:
        errors.append(f"{name}: page count does not match provenance")
    for number, page in enumerate(reader.pages, 1):
        if f"v{version} experimental" not in page.extract_text():
            errors.append(f"{name}: page {number} is missing the v{version} footer")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--check", action="store_true", help="check consistency without modifying files (default)")
    operation.add_argument("--check-label", action="store_true", help="require one semantic version label in the GitHub PR event")
    operation.add_argument("--set", metavar="X.Y.Z", help="set a version, synchronize references and rebuild the PDF")
    operation.add_argument("--bump", choices=("patch", "minor", "major"), help="increment the package version and regenerate references/PDF")
    args = parser.parse_args()
    try:
        if args.check_label:
            event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
            label = semantic_label(item["name"] for item in event["pull_request"]["labels"])
            print(f"Version label: {label}. Use --bump {label} when preparing the next release.")
            return
        if args.set or args.bump:
            version = args.set or bumped_version(project_version(ROOT), args.bump)
            synchronize_metadata(ROOT, version)
            subprocess.run([sys.executable, str(ROOT / "docs/build-guide/build_pdf.py")], cwd=ROOT, check=True)
        errors = metadata_errors(ROOT) + pdf_errors(ROOT)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Version check failed: {error}\n")
    if errors:
        parser.exit(1, "\n".join(errors) + "\nRun uv run scripts/version.py --set " + project_version(ROOT) + " to regenerate current versions.\n")
    print(f"Version {project_version(ROOT)} is consistent across package metadata, documentation and PDF.")


if __name__ == "__main__":
    main()
