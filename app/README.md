# CSV Processor Application

The Flask application validates three-column product CSV files, prints processed
rows in the browser, uploads each successfully processed original to Amazon S3,
and uses S3 itself as the source for the previous-file history.

The expected column order is `product_id`, `product_name`, and `price`. The input
does not contain a header row.

## Build the image

```bash
docker build -t csv-processor:1.0.0 app
```

## Run against the test bucket

Mount the host AWS configuration directory read-only. Credentials are never
copied into the image:

```bash
docker run --rm \
  --name csv-processor \
  -p 8080:8080 \
  -e AWS_PROFILE=default \
  -e AWS_REGION=us-east-2 \
  -e S3_BUCKET=bilal-spidersilk \
  -e S3_PREFIX=case-study-test/processed/ \
  --mount type=bind,source=/absolute/path/to/.aws,target=/home/app/.aws,readonly \
  csv-processor:1.0.0
```

Open <http://localhost:8080> and upload `soh-1-.csv`. The defaults use the bucket
`bilal-spidersilk` in `us-east-2` and prefix `case-study-test/processed/`.
