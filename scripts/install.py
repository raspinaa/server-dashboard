#!/usr/bin/env python3
"""Ubuntu 24.04 installer SOURCE. Default is plan-only; never auto-erases data."""

import argparse, getpass, os, platform, re, secrets, shutil, subprocess, sys, tempfile
from pathlib import Path
from release import verify, extract


def supported(os_release, arch):
    return (
        os_release.get("ID") == "ubuntu"
        and os_release.get("VERSION_ID") == "24.04"
        and arch == "x86_64"
    )


def existing(root):
    return (Path(root) / ".env").exists() or (Path(root) / "data").exists()


def command(args):
    subprocess.run(args, check=True)


def install_docker():
    # Official signed apt repository; no curl|sh, no verification bypass.
    command(["apt-get", "update"])
    command(["apt-get", "install", "-y", "ca-certificates", "curl"])
    Path("/etc/apt/keyrings").mkdir(mode=0o755, exist_ok=True)
    command(
        [
            "curl",
            "--fail",
            "--proto",
            "=https",
            "--tlsv1.2",
            "https://download.docker.com/linux/ubuntu/gpg",
            "-o",
            "/etc/apt/keyrings/docker.asc",
        ]
    )
    os.chmod("/etc/apt/keyrings/docker.asc", 0o644)
    Path("/etc/apt/sources.list.d/infrahub-docker.sources").write_text(
        "Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: noble\nComponents: stable\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/docker.asc\n"
    )
    command(["apt-get", "update"])
    command(
        [
            "apt-get",
            "install",
            "-y",
            "docker-ce",
            "docker-ce-cli",
            "containerd.io",
            "docker-buildx-plugin",
            "docker-compose-plugin",
        ]
    )
    command(["systemctl", "enable", "--now", "docker"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="/opt/infrahub")
    p.add_argument("--version", required=True)
    p.add_argument("--artifact")
    p.add_argument("--manifest")
    p.add_argument("--signature")
    p.add_argument("--public-key", required=True)
    p.add_argument("--repository")
    p.add_argument("--token-file")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--offline", action="store_true")
    p.add_argument(
        "--tls-cert", help="Operator-provided certificate for IP/private-domain HTTPS"
    )
    p.add_argument(
        "--tls-key", help="Matching private TLS key; never a credential value argument"
    )
    a = p.parse_args()
    root = Path(a.root).resolve()
    print(
        "Plan: verify signed release; install Docker if needed; generate new config/keys; build/load images; start MySQL; migrate; create administrator; start HTTPS proxy; check health. No SSH/firewall edits."
    )
    if not a.apply:
        return
    release = dict(
        line.split("=", 1)
        for line in Path("/etc/os-release").read_text().splitlines()
        if "=" in line
    )
    release = {k: v.strip('"') for k, v in release.items()}
    if not supported(release, platform.machine()):
        raise SystemExit("Supported deployment: Ubuntu 24.04 amd64 only")
    if os.geteuid() != 0:
        raise SystemExit("Explicit installation requires root")
    if existing(root):
        print(
            "Existing installation retained: no files, database or keys changed. Use upgrade/restore tools."
        )
        return
    if root.exists() and any(root.iterdir()):
        raise SystemExit("Nonempty target refused")
    if not a.artifact:
        if a.offline or not a.repository:
            raise SystemExit(
                "Supply signed offline artifacts or an approved release repository"
            )
        from fetch_release import fetch

        folder = fetch(
            a.repository,
            a.version,
            tempfile.mkdtemp(prefix="infrahub-release-"),
            a.token_file,
        )
        a.artifact = str(folder / f"infrahub-{a.version}.tar.gz")
        a.manifest = str(folder / "manifest.json")
        a.signature = str(folder / "manifest.sig")
    verify(a.artifact, a.manifest, a.signature, a.public_key, a.version)
    if not shutil.which("docker"):
        if a.offline:
            raise SystemExit("Offline mode requires preinstalled Docker Engine/Compose")
        install_docker()
    command(["docker", "compose", "version"])
    domain = input(
        "DNS domain or IPv4 address (IP requires --tls-cert and --tls-key): "
    ).strip()
    if (
        not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", domain)
        or ":" in domain
    ):
        raise SystemExit("Invalid domain/IP")
    try:
        import ipaddress

        ipaddress.ip_address(domain)
        ip_only = True
    except ValueError:
        ip_only = False
    manual_tls = bool(a.tls_cert and a.tls_key)
    if bool(a.tls_cert) != bool(a.tls_key) or (ip_only and not manual_tls):
        raise SystemExit(
            "Supply both operator-managed TLS certificate and key for an IP installation"
        )
    if manual_tls:
        from cryptography import x509
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key,
            Encoding,
            PublicFormat,
        )

        cert = x509.load_pem_x509_certificate(Path(a.tls_cert).read_bytes())
        private = load_pem_private_key(Path(a.tls_key).read_bytes(), password=None)
        if cert.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        ) != private.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        ):
            raise SystemExit("TLS key does not match certificate")
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        names = san.get_values_for_type(x509.IPAddress if ip_only else x509.DNSName)
        if (ipaddress.ip_address(domain) if ip_only else domain) not in names:
            raise SystemExit(
                "TLS certificate must contain the exact requested domain/IP in SAN"
            )
    http = int(input("HTTP port [80]: ") or 80)
    https = int(input("HTTPS port [443]: ") or 443)
    if not 1 <= http <= 65535 or not 1 <= https <= 65535 or http == https:
        raise SystemExit("Invalid ports")
    username = input("Initial administrator username: ").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.@+-]{1,150}", username):
        raise SystemExit("Invalid username")
    extract(a.artifact, root)
    from cryptography.fernet import Fernet

    env = {
        "APP_VERSION": a.version,
        "DEBUG": "0",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "CREDENTIAL_KEY": Fernet.generate_key().decode(),
        "MYSQL_ROOT_PASSWORD": secrets.token_urlsafe(40),
        "MYSQL_PASSWORD": secrets.token_urlsafe(40),
        "MYSQL_DATABASE": "infrahub",
        "MYSQL_USER": "infrahub",
        "MYSQL_HOST": "db",
        "MYSQL_PORT": "3306",
        "ALLOWED_HOSTS": domain + ",localhost,127.0.0.1",
        "CSRF_TRUSTED_ORIGINS": "https://"
        + domain
        + (":" + str(https) if https != 443 else ""),
        "SITE_ADDRESS": domain,
        "CADDY_CONFIG": "./Caddyfile.ip-tls" if manual_tls else "./Caddyfile",
        "HTTP_PORT": str(http),
        "HTTPS_PORT": str(https),
        "UPLOAD_LIMIT_MB": "10",
        "SESSION_SECONDS": "3600",
        "RELEASE_REPOSITORY": a.repository or "",
        "RELEASE_CHANNEL": "stable",
        "UPDATE_EXECUTION_ENABLED": "0",
    }
    fd = os.open(root / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(k + "=" + v for k, v in env.items()) + "\n")
    shutil.copyfile(a.public_key, root / "release-public.key")
    for path in ["data/uploads", "data/tls", "state", "state/backups", "secrets"]:
        d = root / path
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o755 if path == "state" else 0o700)
        if path == "data/uploads":
            os.chown(d, 10001, 10001)
    if manual_tls:
        shutil.copyfile(a.tls_cert, root / "data/tls/cert.pem")
        shutil.copyfile(a.tls_key, root / "data/tls/key.pem")
        os.chmod(root / "data/tls/cert.pem", 0o600)
        os.chmod(root / "data/tls/key.pem", 0o600)
    dc = [
        "docker",
        "compose",
        "--env-file",
        str(root / ".env"),
        "-f",
        str(root / "deploy/compose.prod.yml"),
    ]
    command([sys.executable, str(root / "scripts/harden_permissions.py"), str(root)])
    if a.offline:
        images = root / "deploy/offline/images.tar"
        if not images.is_file():
            raise SystemExit(
                "Signed package must include deploy/offline/images.tar; installation config retained for recovery"
            )
        command(["docker", "load", "-i", str(images)])
    else:
        command(dc + ["build", "backend", "frontend"])
    command(
        dc
        + [
            "up",
            "-d",
            "--no-build",
            "--pull",
            "never" if a.offline else "missing",
            "db",
        ]
    )
    command(
        dc
        + [
            "run",
            "--rm",
            "--pull",
            "never" if a.offline else "missing",
            "backend",
            "python",
            "backend/manage.py",
            "migrate",
            "--noinput",
        ]
    )
    command(
        dc
        + [
            "run",
            "--rm",
            "--pull",
            "never" if a.offline else "missing",
            "backend",
            "python",
            "backend/manage.py",
            "bootstrap_admin",
            "--username",
            username,
        ]
    )
    command(
        dc + ["up", "-d", "--no-build", "--pull", "never" if a.offline else "missing"]
    )
    command(["bash", str(root / "scripts/health.sh"), str(root)])
    print(
        "Installation health checks passed. URL: https://"
        + domain
        + (":" + str(https) if https != 443 else "")
    )
    print(
        "Docker restart policies preserve startup after reboot. Confirm external DNS/TLS and secure backup before use."
    )


if __name__ == "__main__":
    main()
