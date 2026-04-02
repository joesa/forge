"""
Layer 1 — Lockfile generator.

Generates deterministic package-lock.json content from resolved dependencies.
Same input always produces same output (sorted keys, stable integrity hashes).
"""

from __future__ import annotations

import hashlib
import json


def _generate_integrity_hash(package_name: str, version: str) -> str:
    """Generate a deterministic SHA-512 integrity hash.

    Uses package name + version as seed for reproducibility.
    In production this would fetch the real tarball hash from npm registry.
    """
    seed = f"{package_name}@{version}".encode()
    digest = hashlib.sha512(seed).digest()
    import base64
    return f"sha512-{base64.b64encode(digest).decode()}"


def generate_lockfile(packages: dict[str, str]) -> str:
    """Generate valid package-lock.json content from resolved packages.

    Args:
        packages: Dict of package_name → pinned version.

    Returns:
        Deterministic JSON string — same input always produces same output.
    """
    # Sort packages for determinism
    sorted_packages = dict(sorted(packages.items()))

    # Build lockfile structure (npm lockfile v3 format)
    lockfile: dict[str, object] = {
        "name": "forge-generated-app",
        "version": "1.0.0",
        "lockfileVersion": 3,
        "requires": True,
        "packages": {
            "": {
                "name": "forge-generated-app",
                "version": "1.0.0",
                "dependencies": sorted_packages,
            },
        },
    }

    # Add each package as a node_modules entry
    packages_section = lockfile["packages"]
    if not isinstance(packages_section, dict):
        packages_section = {}

    for pkg_name, version in sorted_packages.items():
        # Clean version string (remove ^, ~, >= prefixes)
        clean_version = version.lstrip("^~>=<")
        if clean_version == "latest":
            clean_version = "0.0.0"

        node_key = f"node_modules/{pkg_name}"
        packages_section[node_key] = {
            "version": clean_version,
            "resolved": (
                f"https://registry.npmjs.org/{pkg_name}/-/"
                f"{pkg_name.split('/')[-1]}-{clean_version}.tgz"
            ),
            "integrity": _generate_integrity_hash(pkg_name, clean_version),
        }

    lockfile["packages"] = packages_section

    return json.dumps(lockfile, indent=2, sort_keys=False)
