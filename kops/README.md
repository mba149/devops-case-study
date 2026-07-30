# kOps Cluster

This directory implements the Kubernetes-cluster portion of the DevOps case study:

- a three-AZ, highly available control plane;
- stable On-Demand worker capacity;
- mixed On-Demand and Spot worker capacity using multiple EC2 types;
- Cluster Autoscaler discovery for every worker InstanceGroup; and
- graceful handling of Spot interruption events.

The source manifests use the native `kops toolbox template` workflow. A rendered
example is committed so the complete plain YAML can be reviewed without running
any command. Cloning, rendering, or locally validating this repository does not
create AWS infrastructure.

## Architecture

The example targets AWS `us-east-1` and uses a kOps-managed VPC:

| Availability Zone | Private subnet | Utility subnet |
| --- | --- | --- |
| `us-east-1a` | `10.20.64.0/18` | `10.20.0.0/21` |
| `us-east-1b` | `10.20.128.0/18` | `10.20.8.0/21` |
| `us-east-1c` | `10.20.192.0/18` | `10.20.16.0/21` |

Control-plane and worker instances run in private subnets. Utility subnets host
NAT gateways and the public Kubernetes API Network Load Balancer. Access to the
API is restricted by `kubernetesApiAccess`.

Worker groups are deliberately single-AZ. This gives Cluster Autoscaler
independent capacity in each AZ and avoids interactions between ASG AZ rebalancing
and autoscaler-driven node termination.

| InstanceGroup set | Count | Example minimum | Example maximum | Capacity |
| --- | ---: | ---: | ---: | --- |
| Control plane | 3 | 1 each | 1 each | On-Demand only |
| Stable workers | 3 | 1 each | 3 each | On-Demand only |
| Elastic workers | 3 | 0 each | 5 each | 20% On-Demand / 80% Spot above base |

The mixed groups use `m7i.large`, `m7a.large`, `m6i.large`, and `m6a.large`.
They have equivalent CPU and memory capacity, which is important because Cluster
Autoscaler models a mixed ASG using its first listed instance type.

## Repository layout

Commands in this document are run from the repository root.

```text
kops/
├── README.md
├── generated/
│   └── example.yaml
├── templates/
│   ├── 00-cluster.yaml.tmpl
│   ├── 10-control-plane.yaml.tmpl
│   ├── 20-workers-ondemand.yaml.tmpl
│   └── 30-workers-mixed.yaml.tmpl
├── scripts/
│   ├── render.sh
│   └── validate.sh
└── values/
    └── example.yaml
```

## Parameterization

Only values expected to vary frequently are parameterized:

- cluster name;
- S3 state-store location;
- environment label;
- administrator, VPN, or CI CIDRs allowed to reach the API;
- On-Demand and mixed worker minimum and maximum sizes; and
- the On-Demand percentage in mixed groups.

The region, Availability Zones, subnet design, Cilium configuration, NLB type,
control-plane topology, AMI, and instance family remain explicit in the templates.
Keeping those architectural decisions visible makes this case study easier to
review and avoids an unnecessary general-purpose platform abstraction.

Edit or copy [values/example.yaml](values/example.yaml) for a target environment.
Do not store AWS credentials, SSH private keys, or application secrets in values
files.

## Prerequisites

- kOps 1.36.x
- AWS CLI authenticated with a short-lived role for AWS preview/deployment
- `kubectl`
- an S3 bucket for the shared kOps state store when deploying a real cluster

The template pins Kubernetes 1.35, which is supported by kOps 1.36 and is within
one minor version of the kubectl 1.34 client used to validate this solution.

## Render the manifests

Render the included example:

```bash
./kops/scripts/render.sh
```

Render a different values file to a chosen location:

```bash
./kops/scripts/render.sh \
  kops/values/my-environment.yaml \
  kops/generated/my-environment.yaml
```

The equivalent direct command is:

```bash
kops toolbox template template.invalid \
  --values kops/values/example.yaml \
  --template kops/templates \
  --format-yaml \
  --out kops/generated/example.yaml
```

kOps 1.36 requires the positional `template.invalid` name even though the actual
cluster name comes from the values file. The placeholder is not written into the
rendered resources. The command reads the official kOps stable-channel metadata,
so rendering requires internet access but does not require AWS credentials.
The template directory is loaded as a collection, so newly added template files
are included automatically. Numeric filename prefixes keep the rendered resources
in a predictable, review-friendly order.

### Add another kOps resource

Place each additional kOps resource template directly in `kops/templates/` using
the next appropriate numeric prefix, for example:

```text
kops/templates/40-bastion.yaml.tmpl
```

No change to `kops/scripts/render.sh` is required. The script passes the complete
template directory to kOps, which renders every template into the single
multi-document output file. Documents in that file are separated with `---` and
can be registered together with one `kops create -f` or `kops replace -f` command.

Keep only renderable kOps templates in this directory. Values files,
documentation, snippets, and generated output belong in their respective
directories so they are not accidentally included in the rendered manifest.

After adding or renaming a template, regenerate and validate the example:

```bash
./kops/scripts/render.sh
./kops/scripts/validate.sh
```

## Validate locally

Validate the example values:

```bash
./kops/scripts/validate.sh
```

Or validate another values file:

```bash
./kops/scripts/validate.sh kops/values/my-environment.yaml
```

The script renders the templates, loads all resources into a temporary local kOps
state store, and lists the resulting InstanceGroups. kOps may perform a read-only
AWS region lookup during schema validation, but the script has no `--yes` operation
and cannot provision AWS infrastructure. Local state is for validation only; real
clusters require shared state such as S3.

## Required deployment customization

Before using a real AWS account:

1. Set a real `clusterName` in the environment values file.
2. Set `stateStore` to a globally unique S3 bucket.
3. Replace the documentation CIDR `203.0.113.10/32` with trusted access CIDRs.
4. Confirm the VPC, Pod, and Service ranges do not overlap connected networks.
5. Confirm the EC2 types and pinned Ubuntu image are available in the region.
6. Render and validate the configuration again.

The example uses `topology.dns.type: None`, so it does not require a Route 53
hosted zone. The Kubernetes API is exposed through the kOps-managed NLB.

## Prepare a real state store

The following commands are examples. The bucket name must be globally unique:

```bash
aws s3api create-bucket \
  --bucket REPLACE_WITH_UNIQUE_STATE_BUCKET \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket REPLACE_WITH_UNIQUE_STATE_BUCKET \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket REPLACE_WITH_UNIQUE_STATE_BUCKET \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

After rendering values that reference the bucket:

```bash
export KOPS_STATE_STORE="s3://REPLACE_WITH_UNIQUE_STATE_BUCKET"
export KOPS_CLUSTER_NAME="REPLACE_WITH_CLUSTER_NAME"
```

## Register and preview the cluster

For a new cluster, register the rendered desired configuration:

```bash
kops create -f kops/generated/my-environment.yaml
```

For an existing desired configuration:

```bash
kops replace --force -f kops/generated/my-environment.yaml
```

These commands modify the kOps state store but do not create EC2 or network
resources. Preview the AWS infrastructure changes by omitting `--yes`:

```bash
kops update cluster "${KOPS_CLUSTER_NAME}"
```

After reviewing the preview, the following command creates or modifies billable
AWS resources:

```bash
kops update cluster "${KOPS_CLUSTER_NAME}" --yes
```

Do not run it until the AWS account, CIDRs, IAM permissions, state bucket, and
estimated cost have been reviewed.

## Preview and apply node replacements

Some changes, such as a new AMI or machine type, require replacing instances.
Preview the rolling update:

```bash
kops rolling-update cluster "${KOPS_CLUSTER_NAME}"
```

Apply it only after reviewing the preview:

```bash
kops rolling-update cluster "${KOPS_CLUSTER_NAME}" --yes
```

## Verify a deployed cluster

```bash
kops validate cluster --wait 10m
kubectl get nodes -L kops.k8s.io/instancegroup,capacity-profile
kubectl -n kube-system get deployment cluster-autoscaler
kubectl -n kube-system logs deployment/cluster-autoscaler --tail=100
```

Verify that all worker ASGs were discovered:

```bash
kubectl -n kube-system logs deployment/cluster-autoscaler \
  | grep -E 'workers-(ondemand|mixed)'
```

The control-plane InstanceGroups intentionally have fixed size and are not managed
by Cluster Autoscaler. `autoscale: true` is explicitly set on all six worker
InstanceGroups.

## Spot interruption strategy

Each mixed group has AWS Capacity Rebalance enabled. The cluster enables the
kOps-managed AWS Node Termination Handler in queue-processor mode, which consumes
AWS interruption and rebalance events delivered through EventBridge and SQS.

Applications on Spot capacity must still use multiple replicas,
PodDisruptionBudgets, topology spread constraints, and realistic resource requests.
Node resilience cannot compensate for an application with only one replica.
