import logging
import os
import sys
from typing import Dict, Tuple

from entsoe import EntsoeRawClient
from google.cloud import bigquery
import pandas as pd
import xmltodict

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

PROJECT_ID = os.getenv("PROJECT_ID", "toki-data-platform-dev")
CLEAN_DATASET_ID = "clean"
PRICES_TABLE_ID = f"{CLEAN_DATASET_ID}.prices"
COUNTRY_CODES = ["BG", "HU"]
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY", "")
EUR_TO_BGN = os.getenv("EUR_TO_BGN", "1.95583")
RETRY_COUNT = 3
RETRY_DELAY = 10
ENTSOE_CLIENT = EntsoeRawClient(
    api_key=ENTSOE_API_KEY, retry_count=RETRY_COUNT, retry_delay=RETRY_DELAY
)
BIG_QUERY_CLIENT = None
WRITE_MODE = "append"


def scrape_prices(request) -> str:
    prices_dataframes = []
    request_data = request.get_json()
    start_date, end_date = get_start_end_date(request_data)
    for country_code in COUNTRY_CODES:
        prices_xml = get_prices_data(country_code, start_date, end_date)
        prices_dataframes.append(format_price_data(prices_xml, country_code))
    save_to_db(pd.concat(prices_dataframes))
    return "OK"


def get_start_end_date(request_data: Dict) -> Tuple[pd.Timestamp, pd.Timestamp]:
    request_start_date = request_data.get("start_date") if request_data else None
    request_end_date = request_data.get("end_date") if request_data else None
    if request_start_date and request_end_date:
        start_date = pd.Timestamp(request_start_date, tz="UTC")
        end_date = pd.Timestamp(
            pd.Timestamp(request_end_date, tz="UTC")
            + pd.DateOffset(days=1)
            - pd.DateOffset(hours=2)
        )
    else:
        start_date = pd.Timestamp(pd.Timestamp.now().normalize(), tz="UTC")
        end_date = pd.Timestamp(
            start_date + pd.DateOffset(days=1) - pd.DateOffset(hours=2)
        )
    return start_date, end_date


def get_prices_data(
    country_code: str, start_date: pd.Timestamp, end_date: pd.Timestamp
) -> str:
    """
    Get price data from external API
      Parameters:
        country_code: str
            country code as defined in https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
        start_date: pandas.Timestamp
            timestamp marking period start for price range
        end_date: pandas.Timestamp
            timestamp marking period end for price range
      Returns:
        str:
            string containing raw API response as XML formatted data
    """
    prices_xml = ENTSOE_CLIENT.query_day_ahead_prices(
        country_code, start=start_date, end=end_date
    )
    logger.info(
        f"Downloaded prices from {start_date.date()} to {end_date.date()} for {country_code}"
    )
    return prices_xml


def format_price_data(prices_xml: str, country_code: str) -> pd.DataFrame:
    """
    Format XML price data into a useful pandas.Dataframe
      Parameters:
        prices_xml: str
            XML formatted response from prices API
        country_code: str
            country code as defined in https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
      Returns:
        pandas.Dataframe:
            price table formatted as a Dataframe
    """
    dataframes = []
    parsed_data = xmltodict.parse(prices_xml)
    timeseries = parsed_data.get("Publication_MarketDocument").get("TimeSeries")
    timeseries = [timeseries] if not isinstance(timeseries, list) else timeseries
    for ts in timeseries:
        start = pd.Timestamp(ts.get("Period").get("timeInterval").get("start"))
        end = pd.Timestamp(ts.get("Period").get("timeInterval").get("end"))
        timestamps = pd.date_range(
            start=start.tz_convert("Europe/Sofia"),
            end=end.tz_convert("Europe/Sofia"),
            freq="h",
            inclusive="left",
        )
        prices = [p.get("price.amount") for p in ts.get("Period").get("Point")]
        currency = ts.get("currency_Unit.name")
        df = pd.DataFrame()
        df["timestamp"] = timestamps
        match (country_code, currency):
            case ("BG", "EUR"):
                df["price"] = [
                    str(round(float(price) * float(EUR_TO_BGN), 2)) for price in prices
                ]
                df["currency"] = "BGN"
            case _:
                df["price"] = prices
                df["currency"] = currency
        df["country_code"] = country_code
        df["source"] = "Entsoe"
        df["source_price"] = prices
        df["source_currency"] = currency
        dataframes.append(df)
        logger.info(f"Formatted price data for {country_code} from {start} to {end}")
    return pd.concat(dataframes)


def save_to_db(prices_df: pd.DataFrame) -> None:
    schema = get_big_query_client().get_table(f"{PROJECT_ID}.{PRICES_TABLE_ID}").schema
    insert_schema = [
        {"name": schema_field.name, "type": schema_field.field_type}
        for schema_field in schema
    ]
    prices_df.to_gbq(
        PRICES_TABLE_ID, PROJECT_ID, table_schema=insert_schema, if_exists=WRITE_MODE
    )
    logger.info("Inserted data in prices table")


def get_big_query_client():
    global BIG_QUERY_CLIENT
    if BIG_QUERY_CLIENT is None:
        BIG_QUERY_CLIENT = bigquery.Client()
    return BIG_QUERY_CLIENT
