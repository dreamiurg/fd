"""Invoke only the fixed FD deployment document, then require terminal success."""
import json
import os
import re
import subprocess
import time


def aws(*args):
    return json.loads(subprocess.check_output(["aws", "ssm", *args, "--region", "us-west-2", "--output", "json"], text=True))


release = os.environ["FD_RELEASE_REF"]
instance = os.environ["FD_INSTANCE_ID"]
if not re.fullmatch(r"[0-9a-f]{40}", release) or not re.fullmatch(r"i-[0-9a-f]{17}", instance):
    raise SystemExit("Invalid immutable release or instance ID")
head = subprocess.check_output(["git", "ls-remote", "--exit-code", "origin", "refs/heads/codex/aws-hosting"], text=True).split()[0]
if head != release:
    raise SystemExit("Deployment branch advanced; refusing a stale release")
command = aws("send-command", "--document-name", "ForgottenDungeonDeploy", "--instance-ids", instance,
              "--parameters", json.dumps({"ReleaseRef": [release]}), "--timeout-seconds", "900")["Command"]["CommandId"]
print(f"Deploying release {release}; SSM command {command}", flush=True)
for _ in range(192):
    time.sleep(5)
    result = subprocess.run(["aws", "ssm", "get-command-invocation", "--region", "us-west-2", "--command-id", command,
                             "--instance-id", instance, "--output", "json"], capture_output=True, text=True)
    if result.returncode:
        if "InvocationDoesNotExist" in result.stderr:
            continue
        raise SystemExit("Cannot read deployment command status")
    invocation = json.loads(result.stdout)
    status = invocation["Status"]
    if status in ("Pending", "InProgress", "Delayed"):
        continue
    # The fixed document emits release/backup/health metadata, never passwords.
    print(invocation.get("StandardOutputContent", ""))
    if status != "Success":
        print(invocation.get("StandardErrorContent", "")[-8000:])
        raise SystemExit(f"Deployment failed: {status}")
    print(f"Release {release} is running and HTTPS health passed.")
    break
else:
    raise SystemExit("Timed out observing deployment; inspect SSM before retrying")
