"""Exercise release failure boundaries without starting Docker or touching a real ledger."""

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.fixture
def release_sandbox(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(
        Path(__file__).parents[1] / "scripts/release_local.sh", scripts / "release_local.sh"
    )
    binary = tmp_path / "bin"
    binary.mkdir()
    virtualenv = tmp_path / ".venv/bin"
    virtualenv.mkdir(parents=True)

    def executable(path, source):
        path.write_text(source)
        path.chmod(0o700)

    executable(
        binary / "docker",
        f"#!{sys.executable}\n"
        + r"""
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
with Path(os.environ['TRACE']).open('a') as stream:
    stream.write(json.dumps(args) + '\n')
if args[:2] == ['context', 'inspect']:
    print(os.environ.get('ENDPOINT', 'unix:///local-docker.sock'))
elif args[:2] == ['compose', 'ps']:
    print('previous-app-container')
elif 'pg_dump' in args:
    sys.stdout.buffer.write(b'PGDMP-test-archive')
elif 'pg_restore' in args:
    assert sys.stdin.buffer.read() == b'PGDMP-test-archive'
stage = os.environ.get('FAIL_STAGE')
if ((stage == 'build' and args == ['compose', 'build', 'app'])
    or (stage == 'backup' and 'pg_dump' in args)
    or (stage == 'deploy' and '--no-build' in args)):
    sys.exit(17)
""",
    )
    for stage in ("local", "latency", "web"):
        executable(
            scripts / f"verify_{stage}.sh",
            "#!/bin/bash\nset -eu\n"
            f'echo "verify_{stage} $*" >> "$TRACE"\n'
            'if [[ "${FAIL_STAGE:-}" == interrupt ]]; then\n'
            "  touch .runtime/interrupt-ready\n"
            "  exec sleep 20\n"
            "fi\n"
            f'if [[ "${{FAIL_STAGE:-}}" == "{stage}" ]]; then exit 17; fi\n',
        )
    executable(
        virtualenv / "python",
        "#!/bin/bash\nset -eu\n"
        'if [[ "$1" == -m ]]; then\n'
        '  echo "smoke $*" >> "$TRACE"\n'
        '  if [[ "${FAIL_STAGE:-}" == smoke ]]; then exit 17; fi\n'
        "  exit 0\nfi\n"
        f'exec {shlex.quote(sys.executable)} "$@"\n',
    )
    for name in ("pytest", "ruff"):
        executable(virtualenv / name, "#!/bin/bash\nexit 0\n")

    def run(failure="", endpoint="unix:///local-docker.sock", full=False):
        environment = {
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "TRACE": str(tmp_path / "trace"),
            "FAIL_STAGE": failure,
            "ENDPOINT": endpoint,
        }
        result = subprocess.run(
            ["/bin/bash", str(scripts / "release_local.sh"), *(["--full-profile"] if full else [])],
            cwd=tmp_path,
            env=environment,
            text=True,
            capture_output=True,
            timeout=15,
        )
        trace = (tmp_path / "trace").read_text() if (tmp_path / "trace").exists() else ""
        return result, trace

    return tmp_path, run


@pytest.mark.parametrize("stage", ["local", "latency", "web", "build"])
def test_release_checks_fail_before_personal_app_is_stopped(release_sandbox, stage):
    root, run = release_sandbox
    result, trace = run(stage)
    assert result.returncode == 17
    assert '["compose", "stop", "app"]' not in trace
    assert "pg_dump" not in trace
    assert not list((root / ".runtime/backups").iterdir())
    assert not (root / ".runtime/local-release.lock").exists()


def test_backup_failure_restarts_previous_container_without_deploying(release_sandbox):
    root, run = release_sandbox
    result, trace = run("backup")
    assert result.returncode == 17
    assert '["compose", "start", "app"]' in trace
    assert "--no-build" not in trace
    assert not list((root / ".runtime/backups").iterdir())


@pytest.mark.parametrize("stage", ["deploy", "smoke"])
def test_failed_deployment_keeps_backup_and_never_restores_automatically(release_sandbox, stage):
    root, run = release_sandbox
    result, trace = run(stage)
    assert result.returncode == 17
    assert '["compose", "start", "app"]' not in trace
    assert trace.count('["compose", "stop", "app"]') == 2
    assert len(list((root / ".runtime/backups").glob("*.dump"))) == 1
    assert '"--list"' in trace  # Archive inspection, not an automatic database restore.
    assert '"--clean"' not in trace


def test_release_success_checks_then_backs_up_before_starting_new_app(release_sandbox):
    root, run = release_sandbox
    result, trace = run(full=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert trace.index("verify_local") < trace.index("verify_latency") < trace.index("verify_web")
    assert "--quick" not in trace
    assert trace.index('"build"') < trace.index('"stop"') < trace.index("pg_dump")
    assert trace.index("pg_dump") < trace.index("pg_restore") < trace.index("--no-build")
    assert "--current-schema" in trace
    backup = next((root / ".runtime/backups").glob("*.dump"))
    report = json.loads(backup.with_suffix(".json").read_text())
    assert report["bytes"] == backup.stat().st_size
    assert len(report["sha256"]) == 64
    assert "full restore has not been tested" in report["validation"]
    assert backup.stat().st_mode & 0o077 == 0
    assert not (root / ".runtime/local-release.lock").exists()


def test_local_release_rejects_remote_docker_before_any_compose_action(release_sandbox):
    _, run = release_sandbox
    result, trace = run(endpoint="ssh://another-server")
    assert result.returncode == 2
    assert "compose" not in trace


def test_second_release_cannot_remove_the_first_releases_lock(release_sandbox):
    root, run = release_sandbox
    lock = root / ".runtime/local-release.lock"
    lock.mkdir(parents=True)
    result, trace = run()
    assert result.returncode == 1
    assert trace == ""
    assert lock.is_dir()


def test_ctrl_c_cleans_release_lock_and_never_reaches_personal_database(release_sandbox):
    root, _ = release_sandbox
    environment = {
        "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"],
        "TRACE": str(root / "trace"),
        "FAIL_STAGE": "interrupt",
    }
    process = subprocess.Popen(
        ["/bin/bash", str(root / "scripts/release_local.sh")],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        # Isolate this simulated terminal job: signals cannot reach the test runner
        # or the user's actual release/application processes.
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not (root / ".runtime/interrupt-ready").exists():
            if process.poll() is not None or time.monotonic() > deadline:
                pytest.fail("Simulated release did not reach the interruptible stage")
            time.sleep(0.02)
        os.killpg(process.pid, signal.SIGINT)
        output, _ = process.communicate(timeout=5)
        assert process.returncode != 0, output
        assert not (root / ".runtime/local-release.lock").exists(), output
        trace = (root / "trace").read_text()
        assert "verify_latency" not in trace
        assert "pg_dump" not in trace
        assert '["compose", "stop", "app"]' not in trace
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate(timeout=5)
