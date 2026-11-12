#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Install Floral's sanitized UAPI headers before Soong/RBE compilation.

The PixelOS lineage_generator's .dummy_dep can exist while the actual
kernel headers_install output tree is missing. Use the kernel's own
headers_install target and fail closed if the required display headers
are not present. No raw/unsanitized header copies are used.
"""

import os
from pathlib import Path
import subprocess
import sys

KERNEL_PATH = Path("kernel/google/msm-4.14")
GENERATOR_REL = Path(
    "soong/.intermediates/vendor/hecker/floral/kernel-build/build/soong/"
    "generated_kernel_includes/gen"
)
REQUIRED = (
    "drm/sde_drm.h",
    "drm/msm_drm_pp.h",
    "media/msm_media_info.h",
)


def install_headers(root: Path, out_dir: str | None = None) -> Path:
    root = Path(root).resolve()
    kernel = root / KERNEL_PATH
    for relative in REQUIRED:
        source = kernel / "include/uapi" / relative
        if not source.is_file():
            raise FileNotFoundError(f"Missing Floral kernel UAPI source: {source}")

    output = Path(out_dir if out_dir is not None else os.environ.get("OUT_DIR", "out"))
    if not output.is_absolute():
        output = root / output
    generator_dir = output / GENERATOR_REL
    generator_dir.mkdir(parents=True, exist_ok=True)

    # This reproduces the direct headers_install command verified on ServerHive.
    # The kernel sanitizes UAPI headers for userspace during headers_install.
    print(f"PenguinOS: installing Floral kernel UAPI headers to {generator_dir}", flush=True)
    subprocess.run(
        ["make", "-C", str(kernel), f"O={generator_dir}", "ARCH=arm64", "headers_install"],
        cwd=root,
        check=True,
    )
    missing = [
        relative for relative in REQUIRED
        if not (generator_dir / "usr/include" / relative).is_file()
    ]
    if missing:
        raise RuntimeError(
            "Floral UAPI header installation incomplete: " + ", ".join(missing)
        )
    print("PenguinOS: verified display DRM and media UAPI headers", flush=True)
    return generator_dir


def main() -> int:
    try:
        install_headers(Path.cwd())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"PenguinOS Floral kernel UAPI: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
