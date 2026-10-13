#!/usr/bin/env python3
"""Offline artifact production and authenticated verification. Never publishes."""

import argparse, base64, hashlib, json, os, re, tarfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
    Ed25519PrivateKey,
)

VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(artifact, manifest, signature, public_key, expected_version=None):
    raw = Path(manifest).read_bytes()
    Ed25519PublicKey.from_public_bytes(
        base64.b64decode(Path(public_key).read_text().strip(), validate=True)
    ).verify(base64.b64decode(Path(signature).read_bytes(), validate=True), raw)
    data = json.loads(raw)
    if not VERSION.fullmatch(data["version"]) or (
        expected_version and expected_version != data["version"]
    ):
        raise ValueError("Version mismatch")
    if (
        data.get("mysql") != "8.4"
        or not (data.get("os") == "ubuntu-24.04" or set(data.get("platforms", [])) == {"debian-12", "debian-13", "ubuntu-24.04"})
        or "amd64" not in data.get("architectures", [])
    ):
        raise ValueError("Unsupported compatibility")
    if digest(artifact) != data["sha256"]:
        raise ValueError("Artifact checksum mismatch")
    if Path(artifact).name != data["artifact"]:
        raise ValueError("Artifact name mismatch")
    return data


def extract(artifact, destination):
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(artifact, "r:gz") as tar:
        members = tar.getmembers()
        if len(members) > 20000 or sum(m.size for m in members) > 32 * 1024**3:
            raise ValueError("Archive limits exceeded")
        for m in members:
            if (
                m.issym()
                or m.islnk()
                or not (m.isfile() or m.isdir())
                or not (target / m.name).resolve().is_relative_to(target)
            ):
                raise ValueError("Unsafe archive entry")
        tar.extractall(target, members=members, filter="data")


def build(root, output, signing_key):
    root = Path(root).resolve()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    ver = (root / "VERSION").read_text().strip()
    if not VERSION.fullmatch(ver):
        raise ValueError("Invalid version")
    artifact = output / f"infrahub-{ver}.tar.gz"
    excludes = {
        ".git",
        ".venv",
        ".native",
        "node_modules",
        "media",
        "state",
        "__pycache__",
        ".pytest_cache",
        ".env",
        "artifacts",
        "test-results",
        "playwright-report",
    }
    with tarfile.open(artifact, "w:gz", compresslevel=3) as tar:
        for base, dirs, files in os.walk(root):
            dirs[:] = sorted(
                d
                for d in dirs
                if d not in excludes
                and not (Path(base) / d).is_symlink()
                and not (Path(base) / d).resolve().is_relative_to(output)
                and (
                    Path(base) != root
                    or d
                    in {
                        "backend",
                        "frontend",
                        "deploy",
                        "scripts",
                        "docs",
                        "tests",
                        "templates",
                        ".github",
                    }
                )
            )
            for f in sorted(files):
                p = Path(base) / f
                if (
                    f in excludes
                    or (f.startswith(".env") and f != ".env.example")
                    or f.endswith((".pyc", ".log", ".key", ".pem"))
                    or p.is_symlink()
                ):
                    continue
                if Path(base) == root and f not in {
                    "VERSION",
                    "CHANGELOG.md",
                    "README.md",
                    ".gitignore",
                    ".dockerignore",
                    ".env.example",
                    "pytest.ini",
                }:
                    continue
                tar.add(p, arcname=str(p.relative_to(root)), recursive=False)
    data = {
        "version": ver,
        "artifact": artifact.name,
        "sha256": digest(artifact),
        "mysql": "8.4",
        "os": "linux-offline",
        "platforms": ["debian-12", "debian-13", "ubuntu-24.04"],
        "offline": (root / "deploy/offline/images.tar").is_file() and (root / "deploy/offline/wheels").is_dir(),
        "architectures": ["amd64"],
        "notes": (root / "CHANGELOG.md").read_text()[:30000] if (root / "CHANGELOG.md").exists() else "",
        "migration_policy": "backup-required; compatible migrations only",
    }
    raw = (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (output / "manifest.json").write_bytes(raw)
    key = Ed25519PrivateKey.from_private_bytes(
        base64.b64decode(Path(signing_key).read_text().strip(), validate=True)
    )
    (output / "manifest.sig").write_bytes(base64.b64encode(key.sign(raw)))
    return artifact


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    p.add_argument("--output", required=True)
    p.add_argument("--signing-key", required=True)
    a = p.parse_args()
    print(build(a.root, a.output, a.signing_key))
