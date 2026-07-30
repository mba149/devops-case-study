# Local Kubernetes deployment runbook

This runbook deploys and tests the CSV processor on Docker Desktop Kubernetes.
It covers the complete local workflow from building the application image to
verifying CSV storage in S3.

## How to use this runbook

Run the sections in order from the repository root. Commands are designed to be
safe to rerun unless a step explicitly says otherwise.

- Confirm the active Kubernetes context before making changes.
- Use the `default` AWS profile or replace it with the intended profile.
- Never paste AWS credentials into this file, Helm values or Ansible variables.
- Commands use the existing `bilal-spidersilk` test bucket in `us-east-2`.
- The smoke-upload step creates an object in S3; remove it after testing if it
  is no longer needed.
- Stop immediately if a command fails and use the troubleshooting section
  before continuing.

## Prerequisites

Required tools:

- Docker Desktop with Kubernetes enabled;
- `kubectl` configured for the `docker-desktop` context;
- Helm;
- `ansible-core 2.21.2`;
- AWS CLI with a working profile;
- `curl` for HTTP smoke tests.

Verify them:

```bash
docker version
kubectl version --client
helm version
ansible-playbook --version
aws --version
curl --version
```

If Helm or Ansible is missing on macOS:

```bash
brew install helm
brew install pipx
pipx ensurepath
pipx install ansible-core==2.21.2
```

Restart the terminal after `pipx ensurepath` if `ansible-playbook` is not found.

## 1. Verify the target cluster

```bash
kubectl config current-context
kubectl cluster-info
kubectl get nodes -o wide
```

The context must be:

```text
docker-desktop
```

Do not continue if another context is active. Switch explicitly if needed:

```bash
kubectl config use-context docker-desktop
```

## 2. Verify AWS access

The application needs permission to list and upload objects in the test bucket.

```bash
aws sts get-caller-identity --profile default
aws s3 ls s3://bilal-spidersilk/ --profile default
```

These commands display identity metadata and bucket contents, not secret keys.

## 3. Build the application image

Build an immutable semantic version instead of using `latest`:

```bash
docker build -t csv-processor:1.0.0 app
docker image inspect csv-processor:1.0.0
```

Docker Desktop Kubernetes uses the same local Docker runtime, so this image does
not need to be pushed to a registry for this test. The Helm values use
`imagePullPolicy: IfNotPresent`.

## 4. Render environment configuration with Ansible

Application configuration is maintained in:

```text
ansible/inventories/local/group_vars/all.yml
```

Render it into a Helm values file:

```bash
cd ansible
ansible-playbook playbooks/render-helm-values.yml
cd ..
```

Expected output:

```text
helm/environments/docker-desktop-generated.yaml
```

The generated file is ignored by Git. Update Ansible `group_vars` and rerun the
playbook instead of editing generated output.

## 5. Validate the Helm chart

These commands do not change the cluster:

```bash
helm lint helm/csv-processor \
  --values helm/environments/docker-desktop-generated.yaml

helm template csv-processor helm/csv-processor \
  --namespace csv-processor \
  --values helm/environments/docker-desktop-generated.yaml
```

Do not deploy if Helm linting or rendering fails.

## 6. Create the namespace and AWS Secret

Create or update the namespace idempotently:

```bash
kubectl create namespace csv-processor \
  --dry-run=client \
  --output yaml |
kubectl apply --filename -
```

Export credentials from the configured AWS profile directly into a Kubernetes
Secret. The credential values pass through the pipeline and are not written to
the repository:

```bash
aws configure export-credentials \
  --profile default \
  --format env-no-export |
kubectl create secret generic csv-processor-aws \
  --namespace csv-processor \
  --from-env-file=/dev/stdin \
  --dry-run=client \
  --output yaml |
kubectl apply --filename -
```

Verify only the Secret metadata. Do not decode or print its contents:

```bash
kubectl get secret csv-processor-aws --namespace csv-processor
```

This Secret is for local testing. On AWS, use workload identity and a
least-privilege IAM role instead of static credentials.

## 7. Install or upgrade the Helm release

```bash
helm upgrade --install csv-processor helm/csv-processor \
  --namespace csv-processor \
  --values helm/environments/docker-desktop-generated.yaml \
  --wait \
  --timeout 5m
```

Helm upgrades the existing release when it already exists, making this command
suitable for repeated local deployments.

## 8. Verify Kubernetes resources

```bash
helm status csv-processor --namespace csv-processor

kubectl get deployment,pods,service,hpa \
  --namespace csv-processor

kubectl rollout status deployment/csv-processor \
  --namespace csv-processor
```

Expected workload state:

```text
Deployment: 1/1 available
Pod:        2/2 Running
Service:    ClusterIP on port 80
```

Inspect logs when necessary:

```bash
kubectl logs deployment/csv-processor \
  --namespace csv-processor \
  --container nginx \
  --tail 100

kubectl logs deployment/csv-processor \
  --namespace csv-processor \
  --container app \
  --tail 100
```

## 9. Access the ClusterIP Service

Start a port-forward and keep this terminal open:

```bash
kubectl port-forward service/csv-processor 8080:80 \
  --namespace csv-processor
```

Open <http://localhost:8080> or use a second terminal for the following tests.

## 10. Run HTTP smoke tests

Verify the proxied health endpoint, application page and Nginx-served CSS:

```bash
curl --fail --show-error http://127.0.0.1:8080/healthz
curl --fail --show-error http://127.0.0.1:8080/
curl --fail --show-error http://127.0.0.1:8080/static/styles.css
```

The health response should be:

```json
{"status":"ok"}
```

## 11. Test CSV processing and S3 upload

This command submits one valid CSV row without creating a local test file:

```bash
curl --fail --show-error \
  --form 'csv_file=1,Helm smoke test,9.99;filename=helm-smoke.csv;type=text/csv' \
  http://127.0.0.1:8080/upload
```

The response should report that one row was processed and show an S3 key under:

```text
processed/YYYY/MM/DD/
```

Verify the object:

```bash
aws s3 ls s3://bilal-spidersilk/processed/ \
  --recursive \
  --profile default
```

To remove the smoke-test object, copy its exact key from the upload response and
run:

```bash
aws s3 rm s3://bilal-spidersilk/<exact-object-key> \
  --profile default
```

Do not use a wildcard or recursive deletion.

## 12. Check autoscaling

```bash
kubectl get hpa csv-processor --namespace csv-processor
kubectl top pods --namespace csv-processor
kubectl get apiservice v1beta1.metrics.k8s.io
```

If the HPA displays `cpu: <unknown>/70%`, the chart is installed but the
cluster does not provide the resource metrics API. Install or enable
metrics-server before attempting an HPA scale test.

## Troubleshooting

### `CreateContainerConfigError` with `runAsNonRoot`

Confirm the rendered Deployment contains numeric users:

```text
Application and init container: UID/GID 10001
Nginx container:                UID/GID 101
```

Inspect the Pod events:

```bash
kubectl describe pod --namespace csv-processor \
  --selector app.kubernetes.io/name=csv-processor
```

### `ImagePullBackOff`

Rebuild the exact image tag configured in Ansible and confirm it exists:

```bash
docker build -t csv-processor:1.0.0 app
docker image inspect csv-processor:1.0.0
```

### S3 access denied or unavailable history

Verify the local AWS identity and Secret metadata, then inspect application
logs:

```bash
aws sts get-caller-identity --profile default
kubectl get secret csv-processor-aws --namespace csv-processor
kubectl logs deployment/csv-processor --namespace csv-processor --container app
```

Recreate the Secret when temporary AWS credentials expire.

### Port 8080 is already in use

Choose another local port while keeping Service port 80 unchanged:

```bash
kubectl port-forward service/csv-processor 18080:80 \
  --namespace csv-processor
```

Then access <http://localhost:18080>.

## Cleanup

Stop the port-forward with `Ctrl+C`, then remove the Helm release and namespace:

```bash
helm uninstall csv-processor --namespace csv-processor
kubectl delete namespace csv-processor
```

The namespace deletion also removes the local Kubernetes Secret. It does not
delete S3 objects, the S3 bucket or the local Docker image.

Optionally remove the local application image:

```bash
docker image rm csv-processor:1.0.0
```
