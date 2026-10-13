"""Build a relocatable release archive from tracked project files."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_NAME = "mechanical-agent-v4"


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "-C", str(PROJECT_ROOT), "ls-files", "-z"],
    )
    paths = [Path(item.decode("utf-8")) for item in output.split(b"\0") if item]
    return [path for path in paths if path.as_posix() != "scripts/build_release.py"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "release" / RELEASE_NAME,
        help="Output directory (fixed to release/mechanical-agent-v4).",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    release_root = (PROJECT_ROOT / "release").resolve()
    if output.parent != release_root or output.name != RELEASE_NAME:
        parser.error(f"--output must be exactly {release_root / RELEASE_NAME}")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for relative in tracked_files():
        source = PROJECT_ROOT / relative
        if source.is_file():
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    bundle_test = PROJECT_ROOT / "tests" / "test_plugin_bundle.py"
    if bundle_test.is_file():
        target = output / "tests" / bundle_test.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundle_test, target)

    demo_report_script = PROJECT_ROOT / "scripts" / "generate_demo_report.py"
    if demo_report_script.is_file():
        target = output / "scripts" / demo_report_script.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(demo_report_script, target)

    bundled_tools = output / "agh-plugin" / "tools"
    bundled_tools.mkdir(parents=True, exist_ok=True)
    for source in (PROJECT_ROOT / "tools").glob("*.py"):
        shutil.copy2(source, bundled_tools / source.name)

    files = sorted(path for path in output.rglob("*") if path.is_file())
    manifest = [
        "# mechanical-agent-v4 发布包清单",
        "",
        f"生成时间（UTC）：{datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "本包从 Git 已跟踪项目文件构建；AGH 插件所需的 Python 脚本已放入 agh-plugin/tools/。",
        "未包含 Python/AGH 运行时、虚拟环境、AGH 本地数据、API 密钥或 validation/sources/ 第三方原始资料。",
        "",
        "| 文件 | SHA-256 |",
        "|---|---|",
    ]
    for path in files:
        manifest.append(
            f"| {path.relative_to(output).as_posix()} | {sha256(path)} |"
        )
    (output / "发布包文件清单.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")

    archive = output.with_suffix(".zip")
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                bundle.write(path, Path(RELEASE_NAME) / path.relative_to(output))

    print(f"目录：{output}")
    print(f"压缩包：{archive}")
    print(f"文件数：{sum(path.is_file() for path in output.rglob('*'))}")
    print(f"压缩包 SHA-256：{sha256(archive)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
