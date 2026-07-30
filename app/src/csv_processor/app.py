from __future__ import annotations

import csv
import io
import os
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, Response, current_app, jsonify, render_template, request
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

EXPECTED_COLUMN_COUNT = 3


class CSVValidationError(ValueError):
    """Raised when an uploaded file is not a supported CSV document."""


def create_app(config: dict[str, Any] | None = None, s3_client: Any | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        AWS_REGION=os.getenv("AWS_REGION", "us-east-2"),
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024))),
        MAX_CSV_ROWS=int(os.getenv("MAX_CSV_ROWS", "5000")),
        MAX_HISTORY_ITEMS=int(os.getenv("MAX_HISTORY_ITEMS", "100")),
        S3_BUCKET=os.getenv("S3_BUCKET", ""),
        S3_PREFIX=os.getenv("S3_PREFIX", "processed/"),
    )
    if config:
        app.config.update(config)

    if not app.config["S3_BUCKET"]:
        raise RuntimeError("S3_BUCKET must be configured")

    app.config["S3_PREFIX"] = normalize_prefix(app.config["S3_PREFIX"])
    app.extensions["s3_client"] = s3_client or boto3.client(
        "s3", region_name=app.config["AWS_REGION"]
    )

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/healthz")
    def healthz() -> tuple[Response, int]:
        return jsonify(status="ok"), 200

    @app.get("/")
    def index() -> tuple[str, int] | str:
        history, history_error = load_history()
        return render_template(
            "index.html", history=history, history_error=history_error
        )

    @app.post("/upload")
    def upload() -> tuple[str, int]:
        uploaded = request.files.get("csv_file")
        if uploaded is None or not uploaded.filename:
            return render_page(error="Choose a CSV file to upload."), 400

        try:
            original_bytes, rows, safe_name = parse_upload(uploaded)
            key = build_object_key(app.config["S3_PREFIX"], safe_name)
            app.extensions["s3_client"].put_object(
                Bucket=app.config["S3_BUCKET"],
                Key=key,
                Body=original_bytes,
                ContentType="text/csv; charset=utf-8",
                ServerSideEncryption="AES256",
                Metadata={
                    "original-filename": safe_name,
                    "row-count": str(len(rows)),
                },
            )
        except CSVValidationError as exc:
            return render_page(error=str(exc)), 400
        except (BotoCoreError, ClientError):
            current_app.logger.exception("Unable to upload processed CSV to S3")
            return render_page(
                error="The CSV was valid, but it could not be stored in S3. Try again."
            ), 502

        return (
            render_page(
                rows=rows,
                success=(
                    f"Processed {len(rows)} rows and stored the original file as {key}."
                ),
                uploaded_key=key,
            ),
            201,
        )

    @app.errorhandler(413)
    def request_too_large(_error: Exception) -> tuple[str, int]:
        size_mib = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return render_page(error=f"The upload exceeds the {size_mib} MiB limit."), 413

    return app


def normalize_prefix(prefix: str) -> str:
    cleaned = prefix.strip().strip("/")
    return f"{cleaned}/" if cleaned else ""


def parse_upload(uploaded: FileStorage) -> tuple[bytes, list[tuple[str, str, str]], str]:
    safe_name = secure_filename(uploaded.filename or "")
    if not safe_name or not safe_name.lower().endswith(".csv"):
        raise CSVValidationError("Only files with a .csv extension are accepted.")

    original_bytes = uploaded.read()
    if not original_bytes:
        raise CSVValidationError("The uploaded CSV is empty.")

    try:
        text = original_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CSVValidationError("The CSV must use UTF-8 encoding.") from exc

    rows: list[tuple[str, str, str]] = []
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        for line_number, row in enumerate(reader, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue
            if len(row) != EXPECTED_COLUMN_COUNT:
                raise CSVValidationError(
                    f"Line {line_number} must contain exactly three columns."
                )

            product_id, product_name, price = (cell.strip() for cell in row)
            if not product_id.isdigit():
                raise CSVValidationError(
                    f"Line {line_number} has an invalid product ID."
                )
            if not product_name:
                raise CSVValidationError(
                    f"Line {line_number} has an empty product name."
                )
            try:
                parsed_price = Decimal(price)
            except InvalidOperation as exc:
                raise CSVValidationError(
                    f"Line {line_number} has an invalid price."
                ) from exc
            if not parsed_price.is_finite() or parsed_price < 0:
                raise CSVValidationError(
                    f"Line {line_number} has an invalid price."
                )

            rows.append((product_id, product_name, price))
            if len(rows) > current_app.config["MAX_CSV_ROWS"]:
                raise CSVValidationError(
                    f"The CSV exceeds the {current_app.config['MAX_CSV_ROWS']} row limit."
                )
    except csv.Error as exc:
        raise CSVValidationError(f"The CSV is malformed: {exc}.") from exc

    if not rows:
        raise CSVValidationError("The CSV contains no data rows.")

    return original_bytes, rows, safe_name


def build_object_key(prefix: str, safe_name: str) -> str:
    now = datetime.now(UTC)
    return (
        f"{prefix}{now:%Y/%m/%d}/{now:%Y%m%dT%H%M%S}-{uuid4().hex[:12]}-{safe_name}"
    )


def load_history() -> tuple[list[dict[str, Any]], str | None]:
    try:
        paginator = current_app.extensions["s3_client"].get_paginator("list_objects_v2")
        objects: list[dict[str, Any]] = []
        for page in paginator.paginate(
            Bucket=current_app.config["S3_BUCKET"],
            Prefix=current_app.config["S3_PREFIX"],
            PaginationConfig={"PageSize": 100},
        ):
            objects.extend(page.get("Contents", []))

        objects.sort(key=lambda item: item["LastModified"], reverse=True)
        history = [
            {
                "key": item["Key"],
                "name": item["Key"].rsplit("/", 1)[-1],
                "size": item["Size"],
                "storage_class": item.get("StorageClass", "STANDARD"),
                "last_modified": item["LastModified"],
            }
            for item in objects[: current_app.config["MAX_HISTORY_ITEMS"]]
        ]
        return history, None
    except (BotoCoreError, ClientError):
        current_app.logger.exception("Unable to list processed files from S3")
        return [], "Previously processed files are temporarily unavailable."


def render_page(**context: Any) -> str:
    history, history_error = load_history()
    return render_template(
        "index.html", history=history, history_error=history_error, **context
    )
