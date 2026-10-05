from __future__ import annotations

import re
import subprocess
import time
import urllib.request
from pathlib import Path

PRODUCT_NAME = "DocMind"
ICON_URL = (
    "https://raw.githubusercontent.com/The-Null-Catchers/brand-assets/"
    "main/projects/docmind/icons/icon-512.png"
)

ROOT = Path(__file__).resolve().parents[1]
MOBILE_DIR = ROOT / "apps" / "mobile"
MANIFEST = MOBILE_DIR / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
ICON_PATH = MOBILE_DIR / ".brand" / "docmind-icon.png"


def patch_android_label() -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"Android manifest not found: {MANIFEST}")

    text = MANIFEST.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'android:label="[^"]*"',
        f'android:label="{PRODUCT_NAME}"',
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit("Could not locate the Android application label")

    MANIFEST.write_text(updated, encoding="utf-8")


def download_icon() -> None:
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(
                ICON_URL,
                headers={"User-Agent": "DocMind-build"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
            if len(payload) < 1024:
                raise RuntimeError("Downloaded brand icon is unexpectedly small")
            ICON_PATH.write_bytes(payload)
            return
        except Exception as exc:  # pragma: no cover - CI/network guard
            last_error = exc
            if attempt < 3:
                time.sleep(2)

    raise SystemExit(f"Failed to download DocMind brand icon: {last_error}")


def generate_launcher_icons() -> None:
    subprocess.run(
        ["dart", "run", "flutter_launcher_icons"],
        cwd=MOBILE_DIR,
        check=True,
    )


def verify_branding() -> None:
    manifest = MANIFEST.read_text(encoding="utf-8")
    if f'android:label="{PRODUCT_NAME}"' not in manifest:
        raise SystemExit("DocMind application label was not applied")

    resource_dir = MOBILE_DIR / "android" / "app" / "src" / "main" / "res"
    generated = list(resource_dir.glob("mipmap-*/ic_launcher.png"))
    generated.extend(resource_dir.glob("mipmap-*/launcher_icon.png"))
    if not generated:
        raise SystemExit("DocMind launcher icons were not generated")

    print(f"Applied {PRODUCT_NAME} branding with {len(generated)} launcher icon densities")


def main() -> None:
    patch_android_label()
    download_icon()
    generate_launcher_icons()
    verify_branding()


if __name__ == "__main__":
    main()
