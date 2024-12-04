import base64
from datetime import datetime, timezone, timedelta
import json
import logging
from os import getenv
from typing import List, Dict, Any

from google.cloud import bigquery

logger = logging.getLogger("billing_aggregator.main")
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

PROJECT_ID = getenv("PROJECT_ID", "toki-data-platform-dev")
DATASET_ID = 'clean'
BILLING_TABLE_NAME = "billing"
COLUMN_DATATYPE = "STRING"
DEFAULT_TIMEZONE = timezone.utc
START_DATE_PARAM = "start_date"
END_DATE_PARAM = "end_date"
POINT_ID_PARAM = "point_ids"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

BIG_QUERY_CLIENT = None


def billing_aggregator(event: Dict[str, Any], context) -> None:
    """
    Entry point that extracts metering point ids, start and end time from an event and moves billing data for those
    points into a billing table.
    :param event: Dict[str,Any]
        Contains the event that is received via PubSub trigger.
    :param context:
        Contains the context of the invocation.
    :return: None
        Since the function is just a processor it returns no value.
    """

    json_data = base64.b64decode(event.get("data"))
    data = json.loads(json_data)
    logger.info(f"Received event {data}")

    points_to_bill = data.get(POINT_ID_PARAM, [])

    if len(points_to_bill) <= 0:
        logger.info("No points to bill")
        return

    start_date, end_date = extract_date_range(data)

    job_config = get_job_config(points_to_bill, start_date, end_date)
    query = get_billing_query()
    query_client = get_big_query_client()

    _ = execute_billing_job(query_client, query, job_config)

    logger.info(f"Loaded {len(points_to_bill)} rows into {DATASET_ID}.{BILLING_TABLE_NAME}.")


def extract_date_range(data: Dict[str, str]) -> tuple[str, str]:
    """
    Returns start and end time extracted from the event received or replaces with default values for previous month.
    :param data: Dict[str,str]
        Contains the event received in json format.
    :return: tuple [str,str]
        Returns a tuple of the start and end date for the billing.
    """
    today = datetime.utcnow()
    end_date = datetime(today.year, today.month, 1, tzinfo=DEFAULT_TIMEZONE)
    last_month = end_date - timedelta(hours=1)
    start_date = datetime(last_month.year, last_month.month, 1, tzinfo=DEFAULT_TIMEZONE)

    start_date = data.get(START_DATE_PARAM, start_date.strftime(DATETIME_FORMAT))
    end_date = data.get(END_DATE_PARAM, end_date.strftime(DATETIME_FORMAT))

    return start_date, end_date


def get_job_config(point_ids: List[str], start_date: str, end_date: str) -> bigquery.QueryJobConfig:
    """
    Creates the job configuration required for the billing job. It requires setting parameters for points to fetch data
    for, start and end date as well as a result target table. Destination is currently controlled by a constant in
    settings.py
    :param point_ids: List[str]
        List of metering point ids that should be billed.
    :param start_date: str
        The start date for the billing period.
    :param end_date: str
        The end date for the billing period.
    :return: QueryJobConfig
        Returns configuration for a BigQuery job.
    """

    query_params = [bigquery.ScalarQueryParameter(START_DATE_PARAM, COLUMN_DATATYPE, start_date),
                    bigquery.ScalarQueryParameter(END_DATE_PARAM, COLUMN_DATATYPE, end_date),
                    bigquery.ArrayQueryParameter(POINT_ID_PARAM, COLUMN_DATATYPE, point_ids)]

    job_config = bigquery.QueryJobConfig(query_parameters=query_params)

    job_config.destination = f"{PROJECT_ID}.{DATASET_ID}.{BILLING_TABLE_NAME}"
    job_config.write_disposition = "WRITE_APPEND"

    return job_config


def get_billing_query() -> str:
    """
    Function to fetch the billing query with its necessary parameters
    :return: str
        Returns the parametrized query to run for billing
    """

    return f"""
    WITH
        billing_data AS (
        SELECT
            point_id,
            SUM(measurement) AS consumption_kwh,
            SUM(measurement_mwh) AS consumption_mwh,
            SUM(total_per_hour) AS energy_price,
            SUM(markup) AS markup,
        FROM
            `clean.hourly_billing`
        WHERE
            point_id in UNNEST(@{POINT_ID_PARAM}) AND
            timestamp > DATETIME(@{START_DATE_PARAM})
            AND timestamp <= DATETIME(@{END_DATE_PARAM})
        GROUP BY
            point_id
    ),
        billing_data_with_duty AS (
        SELECT
            *,
            # Duty fee hardcoded for Bulgarian clients for now, move to a separate table
            2*consumption_mwh AS duty
        FROM
            billing_data )
    SELECT
        point_id,
        PARSE_DATETIME("%F %X",@{START_DATE_PARAM}) as start_time,
        PARSE_DATETIME("%F %X",@{END_DATE_PARAM}) as end_time,
        consumption_kwh,
        consumption_mwh,
        energy_price,
        markup,
        duty,
        energy_price + markup + duty AS total_price,
        FALSE AS is_invoiced,
        FALSE AS is_invalidated,
    FROM
        billing_data_with_duty
    """  # noqa: S608 Ignoring since parameters are controlled via query params


def execute_billing_job(client: bigquery.Client, query: str, config: bigquery.QueryJobConfig):
    """
    A utility function to execute a query job with a bigquery client.
    :param client: bigquery.Client
        A client to use for the query job.
    :param query: str
        A query string to execute inside the job.
    :param config: QueryJobConfig
        A job configuration to use for the query job.
    :return:
        Iterator for the result set of the job.
    """
    query_job = client.query(query, job_config=config)
    logger.info(f"Executing query {query_job.query}")

    return query_job.result()


def get_big_query_client() -> bigquery.Client:
    """
    Utility function to fetch bigquery client instance if it is not already initialized in the global scope
    :return: bigquery.Client
        Returns a bigquery client global for the invocation of the function
    """
    global BIG_QUERY_CLIENT
    if BIG_QUERY_CLIENT is None:
        BIG_QUERY_CLIENT = bigquery.Client()
    return BIG_QUERY_CLIENT
