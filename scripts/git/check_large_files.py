#!/usr/bin/env python3
import os
import subprocess
import sys


MAX_SIZE_MB = int(os.environ.get("GIT_MAX_FILE_MB", "20"))
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


def staged_files():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main():
    oversized = []
    for path in staged_files():
        if not os.path.exists(path):
            continue
        size = os.path.getsize(path)
        if size > MAX_SIZE_BYTES:
            oversized.append((path, size))

    if not oversized:
        return 0

    print(f"[BLOCKED] Found staged files larger than {MAX_SIZE_MB} MB:")
    for path, size in oversized:
        print(f" - {path} ({size / 1024 / 1024:.2f} MB)")
    print("Use external storage or Git LFS for large binaries.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
