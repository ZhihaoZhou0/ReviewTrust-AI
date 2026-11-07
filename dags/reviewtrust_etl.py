"""
ReviewTrust AI - Airflow ETL Orchestration.

This DAG coordinates the existing data engineering pipeline:

    Extract Check -> Clean -> Validate -> Incremental Load -> Monitor

Airflow is responsible for task dependencies, retries, scheduling,
and logging. Data transformation and loading logic remain in the
pipeline package so they can also run independently of Airflow.
"""

import json
import subprocess
import sys

from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.sdk import dag, task


# Project root inside the Airflow Docker container.
# This path is mapped from the local repository by Docker Compose.
ROOT = Path("/opt/reviewtrust")

# Shared locations used by the pipeline tasks.
RAW = ROOT / "data/raw"
PROCESSED = ROOT / "data/processed"
REPORT = PROCESSED / "cleaning-report.json"


def run_module(module):
    """
    Execute an existing Python module as a subprocess.

    Running modules with '-m' preserves package imports such as
    'from pipeline.validate import validate_batch'.

    check=True raises an exception if the command exits unsuccessfully.
    Airflow interprets that exception as a task failure.
    """
    subprocess.run(
        [sys.executable, "-m", module],
        cwd=ROOT,
        check=True,
    )


@dag(
    dag_id="reviewtrust_etl",
    description="ReviewTrust AI Amazon review ETL",

    # Manual execution for the MVP.
    # A cron expression can be added later for scheduled execution.
    schedule=None,

    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),

    # Do not create historical DAG runs when Airflow starts.
    catchup=False,

    # Prevent overlapping runs from processing the same dataset.
    max_active_runs=1,

    default_args={
        # Retry a failed task up to two additional times.
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
    },

    tags=["reviewtrust", "data-engineering"],
)
def reviewtrust_etl():
    """Define the five tasks in the ETL workflow."""

    @task
    def extract_check():
        """
        Verify that the source CSV files are available.

        The MVP uses previously downloaded Amazon review data.
        This task avoids unnecessary network downloads during
        repeated local ETL demonstrations.
        """
        from pipeline.source import verify_source_files

        for path in verify_source_files(RAW).values():
            print(f"Verified pinned source: {path}")

    @task
    def clean():
        """
        Run A1's existing cleaning pipeline.

        Cleaning standardizes source fields and validates required
        values while retaining repeated review rows.

        The cleaning implementation is reused rather than
        duplicated inside the Airflow DAG.
        """
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "pipeline/clean_dataset.py"),
                "--products", str(RAW / "products.csv"),
                "--reviews", str(RAW / "reviews.csv"),
                "--output-dir", str(PROCESSED),
                "--report", str(REPORT),
            ],
            cwd=ROOT,
            check=True,
        )

        # Inspect the cleaning report before continuing.
        report = json.loads(REPORT.read_text())

        # Stop downstream tasks if the cleaner rejected any
        # malformed or otherwise invalid source records.
        for kind in ["products", "reviews"]:
            rejected = {
                key: value
                for key, value in report[kind].items()
                if key.startswith("rejected_") and value > 0
            }

            if rejected:
                raise ValueError(
                    f"{kind} cleaning rejected rows: {rejected}"
                )

        print("Cleaning completed successfully.")

    @task
    def validate():
        """
        Run batch-level quality checks before database loading.

        Validation covers required fields, schema integrity,
        ratings, dates, foreign keys, and source-position integrity.

        An invalid batch raises an exception, preventing
        the incremental loading task from executing.
        """
        run_module("pipeline.validate")

    @task
    def incremental_load():
        """
        Load cleaned reviews into PostgreSQL incrementally.

        The loader uses stable batch IDs and database checkpoints.

        Successfully completed batches are skipped during reruns.
        Inserts and successful checkpoints share one transaction
        to support safe recovery after a failure.
        """
        run_module("pipeline.incremental")

    @task
    def monitor():
        """
        Check database counts and ETL batch statuses.

        This task provides a final data-quality checkpoint and
        writes summary metrics to the Airflow task log.
        """
        run_module("pipeline.monitor")

    # Define the execution order explicitly.
    # Airflow runs each downstream task only after the
    # upstream task finishes successfully.
    extract_check() >> clean() >> validate() >> incremental_load() >> monitor()


# Instantiate the DAG so Airflow can discover it.
reviewtrust_etl()
