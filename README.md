# Cloud Platform Lab

A small Python service plus Docker, Kubernetes, CI, and AWS Terraform examples
for practicing platform deployment and operational checks. A portfolio learning
project, not an enterprise platform or a claim of production Kubernetes/AWS use.

## Quick start

```sh
python -m unittest discover -s tests -v
python -m platform_lab.service
curl http://127.0.0.1:8080/readyz
curl http://127.0.0.1:8080/work
curl http://127.0.0.1:8080/metrics
```

No dependencies are needed for the Python service/tests. Health probes distinguish
liveness from readiness. Work requests emit structured JSON logs and Prometheus
request/error counters and a latency histogram. A shutdown signal stops the server.

## Kubernetes lab

```sh
kind create cluster --name platform-lab
docker build -t cloud-platform-lab:ci .
kind load docker-image cloud-platform-lab:ci --name platform-lab
kubectl apply -f k8s/platform.yaml
kubectl -n platform-lab rollout status deployment/platform-api
kubectl -n platform-lab port-forward service/platform-api 8080:8080
```

The deployment uses two replicas, resource limits, a non-root user, read-only
root filesystem, dropped capabilities, startup/readiness/liveness probes, a
disruption budget, and an HPA specification. See [RUNBOOK](docs/RUNBOOK.md) for
failure/recovery exercises, scaling prerequisites, and AWS scope.

CI runs Python tests, a real Docker build and kind deployment, a readiness-failure
and recovery exercise, HTTP smoke checks, and Terraform validation. Check the
Actions result before interpreting a workflow definition as executed evidence.
AWS resources are not applied in CI. No VMware implementation is included.

## Architecture

Python service -> Docker image -> Kubernetes Deployment/Service -> probe/metrics checks.
The AWS Terraform example is a separate EC2 learning environment, not an EKS deployment.

## Development

Created with AI coding assistance; code, test results, and limitations are available
for review. No claims of customer use, uptime improvement, or cloud cost savings.
