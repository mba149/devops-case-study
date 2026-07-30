# Application configuration with Ansible

Ansible is the source for environment-specific application configuration. It
validates inventory variables and renders a Helm override file; it does not
create AWS infrastructure, create the Kubernetes cluster, or duplicate the
Kubernetes templates owned by Helm.

```text
inventory group_vars
        -> Ansible validation and Jinja template
        -> helm/environments/<environment>-generated.yaml
        -> Helm
        -> Kubernetes ConfigMap, Deployment and HPA
```

The local inventory currently configures:

- application image `csv-processor:1.0.0`;
- AWS region, S3 bucket and object prefix;
- the name of the existing Kubernetes credentials Secret;
- HPA minimum, maximum and CPU target;
- CPU requests plus memory requests and limits for both containers.

Actual AWS credentials are intentionally not stored in Ansible variables or
rendered Helm values.

## Prerequisite

The playbook is tested with `ansible-core 2.21.2`. Install it with `pipx` so it
is isolated from the system Python environment:

```bash
pipx install ansible-core==2.21.2
ansible-playbook --version
```

## Render the local values

Run from the repository root:

```bash
cd ansible
ansible-playbook playbooks/render-helm-values.yml
cd ..
```

The output is:

```text
helm/environments/docker-desktop-generated.yaml
```

Generated files are ignored by Git. Change the inventory variables and rerun
the playbook instead of editing generated output.

## Validate and deploy

```bash
helm lint helm/csv-processor \
  --values helm/environments/docker-desktop-generated.yaml

helm upgrade --install csv-processor helm/csv-processor \
  --namespace csv-processor \
  --values helm/environments/docker-desktop-generated.yaml \
  --wait \
  --timeout 5m
```

## Add another environment

Copy `inventories/local` to an environment-specific directory such as
`inventories/staging`, change its `group_vars/all.yml`, and render it with:

```bash
cd ansible
ansible-playbook \
  --inventory inventories/staging/hosts.yml \
  playbooks/render-helm-values.yml
```
