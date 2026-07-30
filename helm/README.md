# Kubernetes deployment with Helm

The `csv-processor` chart deploys Nginx and the Python application as two
containers in the same Pod. An init container uses the application image to
copy packaged CSS and JavaScript into an `emptyDir` volume. Nginx mounts that
volume read-only, serves `/static/` directly, and proxies all other requests to
Gunicorn over the Pod-local network.

The chart creates:

- one Deployment containing the asset init container, Nginx and Gunicorn;
- one ClusterIP Service that sends traffic to Nginx;
- ConfigMaps for application environment variables and Nginx configuration;
- one CPU-based HorizontalPodAutoscaler;
- per-Pod `emptyDir` volumes for shared public assets and writable temporary
  directories.

AWS credentials are not stored in Helm values or rendered into a Helm release.
For Minikube, create an existing Kubernetes Secret. On AWS, replace this Secret
with workload identity and pod IAM permissions.

## Versioning

- Helm chart version: `0.1.0`
- Application version and image tag: `1.0.0`
- Nginx image: `nginxinc/nginx-unprivileged:1.28.1-alpine`

Increment the application image tag for every application release. Do not
reuse `1.0.0` for different image contents.

## Run on Minikube

Start Minikube and enable the metrics API required by the HPA:

```bash
minikube start
minikube addons enable metrics-server
```

Build the semantic application version and load it into Minikube:

```bash
docker build -t csv-processor:1.0.0 app
minikube image load csv-processor:1.0.0
```

Create the namespace and local AWS credentials Secret. The following assumes
your AWS credentials are already exported in the shell:

```bash
kubectl create namespace csv-processor

kubectl create secret generic csv-processor-aws \
  --namespace csv-processor \
  --from-literal=AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" \
  --from-literal=AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" \
  --from-literal=AWS_SESSION_TOKEN="${AWS_SESSION_TOKEN:-}"
```

The Minikube values currently use the existing `bilal-spidersilk` test bucket.
Install the chart:

```bash
helm upgrade --install csv-processor helm/csv-processor \
  --namespace csv-processor \
  --values helm/environments/minikube.yaml
```

Wait for the Deployment and access the ClusterIP Service from the workstation:

```bash
kubectl rollout status deployment/csv-processor --namespace csv-processor
kubectl port-forward service/csv-processor 8080:80 --namespace csv-processor
```

Open <http://localhost:8080>.

`minikube service` is normally used with NodePort or LoadBalancer services. This
chart intentionally uses ClusterIP, so `kubectl port-forward` is the direct
local-access method.

## Validate and inspect

Render without changing the cluster:

```bash
helm lint helm/csv-processor \
  --values helm/environments/minikube.yaml

helm template csv-processor helm/csv-processor \
  --namespace csv-processor \
  --values helm/environments/minikube.yaml \
  --set-string aws.bucket=example-bucket
```

Inspect the running application and autoscaler:

```bash
kubectl get pods,service,hpa --namespace csv-processor
kubectl top pods --namespace csv-processor
```

## Create another environment

Create another values file under `helm/environments/` and override only the
values that differ, such as the image tag, bucket, resource sizing and HPA
limits. The reusable Kubernetes templates remain unchanged.
