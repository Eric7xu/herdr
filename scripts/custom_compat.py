#!/usr/bin/env python3
"""Test the custom CLI against official HERDR in isolated CI sessions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import tempfile
import time

BASE_VERSION = "0.9.5"
OFFICIAL = {
    ("Darwin", "arm64"): ("herdr-macos-aarch64", "fb77c2232a05a8035421382c894392f4174e4e38a18e48af3dd0290157c3a7e2"),
    ("Darwin", "aarch64"): ("herdr-macos-aarch64", "fb77c2232a05a8035421382c894392f4174e4e38a18e48af3dd0290157c3a7e2"),
    ("Darwin", "x86_64"): ("herdr-macos-x86_64", "5fb0a908ec7f6745e3e245738b06bfad56c46391c391ab3c0955fbead01f1369"),
    ("Linux", "x86_64"): ("herdr-linux-x86_64", "14d9e8bc8b4a9e0118d77c32266f76d461f09b40342eb23752960bd89f59929d"),
    ("Linux", "aarch64"): ("herdr-linux-aarch64", "17d7536f2da50859523680ef279dffcac8e4a235f4e46fe8da6c2ec44141897c"),
}


def isolated_env(directory):
    """Keep host credentials and real HERDR session identifiers out of the test."""
    home = directory / "home"
    home.mkdir(parents=True)
    state = directory / "state"
    state.mkdir()
    config = directory / "config.toml"
    config.write_text("")
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "SHELL": "/bin/sh",
        "TERM": "xterm-256color",
        "LANG": "en_US.UTF-8",
        "XDG_CONFIG_HOME": str(directory / "config"),
        "XDG_STATE_HOME": str(state),
        "HERDR_CONFIG_PATH": str(config),
        "HERDR_SOCKET_PATH": str(directory / "h.sock"),
        "HERDR_CLIENT_SOCKET_PATH": str(directory / "c.sock"),
    }


def run(binary, args, env, timeout=15, check=True):
    return subprocess.run([str(binary), *args], env=env, cwd=env["HOME"],
                          capture_output=True, text=True, timeout=timeout, check=check)


def official_binary(directory):
    name, expected = OFFICIAL[(platform.system(), platform.machine())]
    download = directory / "download"
    download.mkdir()
    target = download / name
    url = f"https://github.com/herdrdev/herdr/releases/download/v{BASE_VERSION}/{name}"
    subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "2",
                    "--max-time", "120", "--output", str(target), url], check=True, timeout=150)
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError("Official binary SHA-256 does not match the pinned release")
    target.chmod(0o755)
    return target


def exercise(client, server, directory, label):
    directory.mkdir()
    env = isolated_env(directory)
    log_path = directory / "server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen([str(server), "server"], env=env, cwd=env["HOME"],
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("The isolated server exited before it became ready")
                status = run(server, ["status", "server"], env, check=False)
                if status.returncode == 0 and "status: running" in status.stdout:
                    break
                time.sleep(0.15)
            else:
                raise RuntimeError("The isolated server did not become ready within 30 seconds")
            created = json.loads(run(client, ["workspace", "create", "--label", "compat-fixture", "--no-focus"], env).stdout)
            result = created["result"]
            workspace = result["workspace"]["workspace_id"]
            pane = result["root_pane"]["pane_id"]
            listed = json.loads(run(client, ["workspace", "list"], env).stdout)
            if "compat-fixture" not in json.dumps(listed):
                raise RuntimeError("The client did not read the test workspace")
            json.loads(run(client, ["tab", "list", "--workspace", workspace], env).stdout)
            json.loads(run(client, ["pane", "list", "--workspace", workspace], env).stdout)
            run(client, ["pane", "read", pane, "--source", "recent-unwrapped", "--lines", "10"], env)
            json.loads(run(client, ["agent", "list"], env).stdout)
            print(f"PASS: {label}: workspace, tab, pane, and agent reads", flush=True)
        except Exception:
            print(log_path.read_text()[-4000:], flush=True)
            raise
        finally:
            if process.poll() is None:
                try:
                    run(server, ["server", "stop"], env, timeout=8, check=False)
                    process.wait(timeout=8)
                except (subprocess.TimeoutExpired, OSError):
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--custom-binary", required=True, type=Path)
    parser.add_argument("--allow-local", action="store_true")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" and not args.allow_local:
        parser.error("Run this isolated-server test in GitHub Actions, or explicitly pass --allow-local")
    custom = args.custom_binary.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="hc-", dir="/tmp") as temporary:
        root = Path(temporary)
        standard = official_binary(root)
        identity = root / "identity"
        identity.mkdir()
        env = isolated_env(identity)
        for binary in (custom, standard):
            if run(binary, ["--version"], env).stdout.strip() != f"herdr {BASE_VERSION}":
                raise RuntimeError("A binary does not match the pinned upstream version")
        if "Authorized external read-only access" not in run(custom, ["--skill"], env).stdout:
            raise RuntimeError("The custom binary does not contain the Skill patch")
        if "If the check fails, say that you are not running inside Herdr and stop." not in run(standard, ["--skill"], env).stdout:
            raise RuntimeError("The official reference binary is not the expected unmodified release")
        exercise(custom, standard, root / "standard-server", "custom client with official server")
        exercise(standard, custom, root / "custom-server", "official client with custom server")
        print("PASS: both directions used isolated endpoints and no managed-pane caller context", flush=True)


if __name__ == "__main__":
    main()
