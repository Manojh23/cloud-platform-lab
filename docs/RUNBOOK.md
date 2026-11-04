# Platform operations runbook

## Build and run

`python -m platform_lab.service` starts a loopback-only process. For a container:

```sh
docker build -t cloud-platform-lab:ci .
docker run --rm -p 127.0.0.1:8080:8080 --read-only --tmpfs /tmp:uid=10001,gid=10001 cloud-platform-lab:ci
```

The public work endpoint has bounded, explicitly synthetic failure controls:
`/work?status=500` and `/work?delay_ms=100`. Do not expose this learning service
as a public production API. `/metrics` reports only work-endpoint requests;
probe/scrape traffic is excluded. Histogram buckets are cumulative milliseconds.

## Readiness incident

1. Check `kubectl -n platform-lab get pods` and `describe pod POD`.
2. Compare `/livez` with `/readyz`; a live process may be unready.
3. Inspect `/tmp/platform-not-ready` and request logs. In this lab, deleting this
   flag recovers readiness. Do not generalize this action to production services.
4. Verify Ready conditions and the service response after recovery.

## Rollout or capacity issue

Inspect rollout status, events, resource requests/limits, restarts, and logs.
Use `kubectl rollout history` before considering `rollout undo`. Never execute
an irreversible remediation merely because a generated suggestion says to.
The HPA needs metrics-server, which kind does not install by default; its schema
is deployed in CI, but automatic scaling is not claimed as exercised.

## AWS template

`terraform init -backend=false` then `terraform validate` checks configuration
without AWS credentials. An actual plan/apply needs a separately authorized AWS
account and incurs charges. The template creates a VPC, subnet, route, EC2 host,
SSM role, encrypted disk, and IMDSv2-only metadata; it opens no inbound ports.
Docker is bootstrapped, but this template does not deploy the application image.
Use SSM for administration and port forwarding after reviewing account policy.
Run `terraform destroy` only on your own disposable lab after reviewing its plan.

## Incident review

Record UTC timeline, affected components, evidence, contributing causes,
recovery verification, and follow-ups. Keep credentials and user data out of logs.
