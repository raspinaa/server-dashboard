#!/usr/bin/env python3
"""Read-only GitHub release retrieval; no upload, push, or credential arguments."""

import json, re, requests
from pathlib import Path


def fetch(repository, version, destination, token_file=None):
    if not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid repository or stable version")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token_file:
        headers["Authorization"] = "Bearer " + Path(token_file).read_text().strip()
    r = requests.get(
        f"https://api.github.com/repos/{repository}/releases/tags/v{version}",
        headers=headers,
        timeout=30,
        allow_redirects=False,
    )
    if r.status_code != 200:
        raise ValueError("GitHub release access failed")
    meta = r.json()
    if (
        meta.get("draft")
        or meta.get("prerelease")
        or meta.get("tag_name") != "v" + version
    ):
        raise ValueError("Unapproved release")
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    for name in ["manifest.json", "manifest.sig", f"infrahub-{version}.tar.gz"]:
        asset = next((a for a in meta["assets"] if a["name"] == name), None)
        if not asset or not re.fullmatch(
            re.escape(f"https://api.github.com/repos/{repository}/releases/assets/")
            + r"\d+",
            asset["url"],
        ):
            raise ValueError("Missing or unsafe asset")
        response = requests.get(
            asset["url"],
            headers={**headers, "Accept": "application/octet-stream"},
            timeout=120,
            stream=True,
        )
        if response.status_code != 200:
            raise ValueError("Asset download failed")
        # requests removes Authorization on cross-host redirects; enforce approved final host.
        from urllib.parse import urlsplit

        host = urlsplit(response.url).hostname or ""
        if urlsplit(response.url).scheme != "https" or not (
            host == "api.github.com"
            or host == "release-assets.githubusercontent.com"
            or host.endswith(".githubusercontent.com")
        ):
            raise ValueError("Unapproved asset destination")
        count = 0
        temporary = dest / (name + ".partial")
        with temporary.open("wb") as f:
            for chunk in response.iter_content(1024 * 1024):
                count += len(chunk)
                if count > 1024**3:
                    raise ValueError("Asset too large")
                f.write(chunk)
        temporary.replace(dest / name)
    return dest


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--repository", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--destination", required=True)
    p.add_argument("--token-file")
    a = p.parse_args()
    try:
        fetch(a.repository, a.version, a.destination, a.token_file)
    except Exception:
        raise SystemExit(
            "Release retrieval failed; check read-only access and release assets (credentials redacted)"
        )
