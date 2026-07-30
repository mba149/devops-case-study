# DevOps Case Study

This repository is being implemented in independent, reviewable sections:

- [`kops/`](kops/) contains the parameterized AWS Kubernetes cluster design.
- [`app/`](app/) contains the Dockerized Python CSV processor.
- [`infrastructure/s3-lifecycle/`](infrastructure/s3-lifecycle/) creates the
  private, encrypted and versioned application bucket and manages the
  processed-file transition to S3 Glacier Flexible Retrieval.

The application uses S3 as durable shared history, so it does not depend on a
container filesystem and can later run with multiple Kubernetes replicas.
