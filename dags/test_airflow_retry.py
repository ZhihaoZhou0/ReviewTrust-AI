
"""
ReviewTrust AI - Airflow Automatic Retry Test.

Purpose:
Verify that Airflow automatically retries a task after a
temporary failure and continues downstream execution.

Expected behavior:
    Attempt 1: FAILED intentionally
    Attempt 2: SUCCESS
    Downstream task: SUCCESS

This DAG does not modify the ReviewTrust PostgreSQL database.
"""

from datetime import datetime, timedelta, timezone

from airflow.sdk import dag, task, get_current_context


@dag(
    dag_id="reviewtrust_retry_test",
    description="Test Airflow automatic task retry behavior",

    # Run manually to avoid unnecessary scheduled test executions.
    schedule=None,

    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
    catchup=False,

    # Allow only one active test run at a time.
    max_active_runs=1,

    tags=["reviewtrust", "testing"],
)
def reviewtrust_retry_test():
    """Define a controlled task failure and recovery test."""

    @task(
        retries=1,
        retry_delay=timedelta(seconds=15),
    )
    def simulate_temporary_failure():
        """
        Fail on the first attempt and succeed on the second.

        Airflow keeps track of the current Task Instance's
        attempt number across retries.
        """

        # Retrieve runtime information from Airflow's task context.
        context = get_current_context()
        task_instance = context["ti"]

        attempt = task_instance.try_number

        print(f"Current attempt: {attempt}")

        # Simulate a temporary error on the first attempt.
        if attempt == 1:
            print("Simulating a temporary task failure.")

            raise RuntimeError(
                "Simulated temporary failure for retry testing."
            )

        # The second attempt should reach this statement.
        print("Retry successful. Task recovered automatically.")

    @task
    def confirm_recovery():
        """
        Verify that downstream execution continues.

        Airflow executes this task only after the upstream
        task eventually succeeds.
        """
        print("Automatic retry test PASSED.")
        print("Downstream task executed successfully.")

    # Define the required task execution order.
    simulate_temporary_failure() >> confirm_recovery()


# Register the DAG for Airflow discovery.
reviewtrust_retry_test()
