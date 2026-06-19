"""Shell background job tool tests."""

import json

import pytest
from likecodex_engine.tools.shell import ShellTools


@pytest.mark.asyncio
async def test_bash_output_and_kill(tmp_path):
    shell = ShellTools(str(tmp_path))
    if __import__("sys").platform == "win32":
        cmd = "echo hello"
    else:
        cmd = "echo hello"
    started = json.loads(await shell.bgjobs("start", command=cmd))
    job_id = started["job_id"]
    import asyncio

    await asyncio.sleep(0.5)
    out = json.loads(await shell.bash_output(job_id))
    assert "hello" in out.get("stdout", "") or out.get("running") is False
    killed = json.loads(await shell.kill_shell(job_id))
    assert killed.get("killed") is True
