"""Scan publishable files (and optional reachable Git history), without printing secrets."""

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private-key": rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    "aws-access-key": rb"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])",
    "github-token": rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
    "api-secret": rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}",
    "jwt-literal": rb"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}",
}


def scan(data: bytes, path: str, source: str) -> list[dict]:
    if b"\0" in data:
        return []
    return [
        {
            "path": path,
            "source": source,
            "line": data.count(b"\n", 0, match.start()) + 1,
            "rule": name,
        }
        for name, pattern in PATTERNS.items()
        for match in re.finditer(pattern, data)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    paths = set(
        filter(
            None,
            subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                cwd=ROOT,
            )
            .decode()
            .split("\0"),
        )
    )
    findings = []
    for path in sorted(paths):
        file = ROOT / path
        if not file.is_file():
            continue
        name = file.name
        public_env = name == ".env.example" or path in {
            "apps/admin/.env.development",
            "apps/admin/.env.production",
        }
        if (name.startswith(".env") and not public_env) or any(
            part in {"backups", "logs"} for part in Path(path).parts
        ):
            findings.append(
                {
                    "path": path,
                    "source": "worktree",
                    "line": 1,
                    "rule": "private-runtime-file",
                }
            )
        if file.stat().st_size < 2_000_000:
            findings.extend(scan(file.read_bytes(), path, "worktree"))
    blob_count = 0
    if args.history:
        objects = {}
        for line in subprocess.check_output(
            ["git", "rev-list", "--objects", "--all"], cwd=ROOT, text=True
        ).splitlines():
            oid, _, path = line.partition(" ")
            if path:
                objects[oid] = path
        proc = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        assert proc.stdin and proc.stdout
        for oid, path in objects.items():
            proc.stdin.write((oid + "\n").encode())
            proc.stdin.flush()
            header = proc.stdout.readline().decode().split()
            if len(header) != 3:
                continue
            size = int(header[2])
            data = proc.stdout.read(size)
            proc.stdout.read(1)
            if header[1] == "blob":
                blob_count += 1
                if size < 2_000_000:
                    findings.extend(scan(data, path, oid[:12]))
        proc.stdin.close()
        proc.wait()
    print(
        json.dumps(
            {
                "files": len(paths),
                "history_blobs": blob_count,
                "findings": findings,
                "scope": "High-confidence patterns only; does not replace a full secret/dependency audit.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
