"""Policy permission tests."""

from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.permissions.policy import Decision, Policy, Rule


def test_deny_overrides_allow():
    policy = Policy(
        mode=Decision.ALLOW,
        allow=[Rule.parse("Bash")],
        deny=[Rule.parse("Bash(rm -rf*)")],
    )
    assert policy.decide("run_command", False, {"command": "rm -rf /tmp/x"}) == Decision.DENY
    assert policy.decide("run_command", False, {"command": "ls"}) == Decision.ALLOW


def test_bash_prefix_rule():
    policy = Policy(allow=[Rule.parse("Bash(go test:*)")])
    assert policy.decide("run_command", False, {"command": "go test ./..."}) == Decision.ALLOW
    assert policy.decide("run_command", False, {"command": "go test ./... && rm x"}) == Decision.ASK


def test_evaluator_with_policy(tmp_path):
    policy = Policy(deny=[Rule.parse("Edit(secrets/**)")])
    ev = PermissionEvaluator(ApprovalMode.AUTO, policy, str(tmp_path))
    d = ev.evaluate("write_file", {"path": "secrets/key.txt", "content": "x"})
    assert not d.allowed
