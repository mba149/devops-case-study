# Application S3 bucket

This Terraform/OpenTofu configuration creates the private S3 bucket used by the
CSV processor. Terraform generates a globally unique bucket name from the
project and environment, for example `csv-processor-dev-abc123...`.

The bucket has:

- all public access blocked and ACLs disabled;
- Amazon S3 managed encryption (`AES256`);
- versioning enabled;
- `force_destroy = false` to protect stored CSV files;
- a lifecycle rule that transitions current and noncurrent objects under
  `processed/` to S3 Glacier Flexible Retrieval after 30 days.

The explicit
`transition_default_minimum_object_size = "varies_by_storage_class"` setting
allows CSV files smaller than S3's default 128 KiB lifecycle transition threshold
to transition to Glacier Flexible Retrieval.

## Configure an environment

Copy the example values and change them for the target environment:

```bash
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` is environment-specific and should not be committed.

## Create the bucket

```bash
cd infrastructure/s3-lifecycle
tofu init
tofu fmt -check
tofu validate
tofu plan -out=s3.tfplan
tofu apply s3.tfplan
```

The same commands work with the `terraform` CLI by replacing `tofu` with
`terraform`.

## Pass the bucket to the application

After applying, obtain the generated values:

```bash
tofu output application_environment
tofu output -raw bucket_name
```

Set the resulting values on the container or, later, in the Kubernetes
Deployment:

```text
AWS_REGION=us-east-2
S3_BUCKET=<value of bucket_name output>
S3_PREFIX=processed/
```

Terraform intentionally does not create application IAM permissions yet. The
Kubernetes workload identity will use the `bucket_arn` output when that part is
implemented.
