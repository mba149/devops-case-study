# DevOps Case Study

This repository is being implemented in independent, reviewable sections:

- [`kops/`](kops/) contains the parameterized AWS Kubernetes cluster design.
- [`app/`](app/) contains the Dockerized Python CSV processor.
- [`infrastructure/app/`](infrastructure/app/) creates the
  private, encrypted and versioned application bucket and manages the
  processed-file transition to S3 Glacier Flexible Retrieval.
- [`helm/`](helm/) contains the reusable Kubernetes Deployment, ClusterIP
  Service, configuration and HorizontalPodAutoscaler.
- [`ansible/`](ansible/) validates environment-specific application settings
  and renders Helm values without storing credentials.
- [`docs/devops-case-study-architecture.drawio`](docs/devops-case-study-architecture.drawio)
  is the editable end-to-end and Kubernetes runtime architecture diagram.
- [`docs/devops-case-study-aws-reference-style.drawio`](docs/devops-case-study-aws-reference-style.drawio)
  is the editable AWS-icon architecture styled after the supplied reference.
- [`docs/local-kubernetes-runbook.md`](docs/local-kubernetes-runbook.md)
  documents how to deploy, verify, test, troubleshoot and clean up the
  application on Docker Desktop Kubernetes.
