import unittest
from unittest.mock import Mock, patch

import flask
import pandas as pd

from main import format_price_data, get_start_end_date, scrape_prices


class TestScrapePrices(unittest.TestCase):
    def setUp(self):
        self.expected_start_date = pd.Timestamp(
            pd.Timestamp.now().normalize(), tz="UTC"
        )
        self.expected_end_date = pd.Timestamp(
            self.expected_start_date + pd.DateOffset(days=1) - pd.DateOffset(hours=2)
        )
        self.expected_request_start_date_str = "2022-12-01"
        self.expected_request_end_date_str = "2022-12-10"
        self.expected_request_data = {
            "start_date": self.expected_request_start_date_str,
            "end_date": self.expected_request_end_date_str,
        }
        self.expected_request_start_date = pd.Timestamp(
            self.expected_request_start_date_str, tz="UTC"
        )
        self.expected_request_end_date = pd.Timestamp(
            self.expected_request_end_date_str, tz="UTC"
        ).replace(hour=22)
        self.expected_bg_api_prices_xml = """<?xml version="1.0" encoding="UTF-8"?>
                                            <Publication_MarketDocument>
                                              <TimeSeries>
                                                <currency_Unit.name>EUR</currency_Unit.name>
                                                  <Period>
                                                    <timeInterval>
                                                      <start>2022-11-30T00:00Z</start>
                                                      <end>2022-11-30T02:00Z</end>
                                                    </timeInterval>
                                                    <resolution>PT60M</resolution>
                                                      <Point>
                                                        <position>1</position>
                                                        <price.amount>279.92</price.amount>
                                                      </Point>
                                                      <Point>
                                                        <position>2</position>
                                                        <price.amount>230.21</price.amount>
                                                      </Point>
                                                  </Period>
                                              </TimeSeries>
                                            </Publication_MarketDocument>"""
        self.expected_hu_api_prices_xml = """<?xml version="1.0" encoding="UTF-8"?>
                                             <Publication_MarketDocument>
                                                  <TimeSeries>
                                                    <currency_Unit.name>EUR</currency_Unit.name>
                                                      <Period>
                                                        <timeInterval>
                                                          <start>2022-11-30T00:00Z</start>
                                                          <end>2022-11-30T02:00Z</end>
                                                        </timeInterval>
                                                        <resolution>PT60M</resolution>
                                                          <Point>
                                                            <position>1</position>
                                                            <price.amount>280.13</price.amount>
                                                          </Point>
                                                          <Point>
                                                            <position>2</position>
                                                            <price.amount>224.06</price.amount>
                                                          </Point>
                                                      </Period>
                                                  </TimeSeries>
                                             </Publication_MarketDocument>"""
        self.expected_bg_formatted_prices = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2022-11-30 02:00:00", tz="Europe/Sofia"),
                    "price": "547.48",
                    "currency": "BGN",
                    "country_code": "BG",
                    "source": "Entsoe",
                    "source_price": "279.92",
                    "source_currency": "EUR",
                },
                {
                    "timestamp": pd.Timestamp("2022-11-30 03:00:00", tz="Europe/Sofia"),
                    "price": "450.25",
                    "currency": "BGN",
                    "country_code": "BG",
                    "source": "Entsoe",
                    "source_price": "230.21",
                    "source_currency": "EUR",
                },
            ]
        )
        self.expected_hu_formatted_prices = pd.DataFrame(
            [
                {
                    "timestamp": pd.Timestamp("2022-11-30 02:00:00", tz="Europe/Sofia"),
                    "price": "280.13",
                    "currency": "EUR",
                    "country_code": "HU",
                    "source": "Entsoe",
                    "source_price": "280.13",
                    "source_currency": "EUR",
                },
                {
                    "timestamp": pd.Timestamp("2022-11-30 03:00:00", tz="Europe/Sofia"),
                    "price": "224.06",
                    "currency": "EUR",
                    "country_code": "HU",
                    "source": "Entsoe",
                    "source_price": "224.06",
                    "source_currency": "EUR",
                },
            ]
        )
        self.expected_prices_dataframe = pd.concat(
            [self.expected_bg_formatted_prices, self.expected_hu_formatted_prices]
        )

    @patch("main.save_to_db")
    @patch("main.format_price_data")
    @patch("main.get_prices_data")
    @patch("main.get_start_end_date")
    def test_scrape_prices(
        self,
        mock_get_start_end_date,
        mock_get_prices_data,
        mock_format_prices_data,
        mock_save_to_db,
    ):
        # Given
        mock_get_start_end_date.return_value = (
            self.expected_start_date,
            self.expected_end_date,
        )
        mock_get_prices_data.side_effect = [
            self.expected_bg_api_prices_xml,
            self.expected_hu_api_prices_xml,
        ]
        mock_format_prices_data.side_effect = [
            self.expected_bg_formatted_prices,
            self.expected_hu_formatted_prices,
        ]
        # When
        scrape_prices(Mock(spec=flask.Request))
        actual_get_prices_data_first_call_country_code = (
            mock_get_prices_data.call_args_list[0].args[0]
        )
        actual_get_prices_data_second_call_country_code = (
            mock_get_prices_data.call_args_list[1].args[0]
        )

        actual_format_first_call_args = mock_format_prices_data.call_args_list[0].args
        actual_format_first_call_price_data = actual_format_first_call_args[0]
        actual_format_first_call_country_code = actual_format_first_call_args[1]
        actual_format_second_call_args = mock_format_prices_data.call_args_list[1].args
        actual_format_second_call_price_data = actual_format_second_call_args[0]
        actual_format_second_call_country_code = actual_format_second_call_args[1]

        actual_save_to_db_dataframe = mock_save_to_db.call_args_list[0].args[0]

        # Then
        self.assertEqual("BG", actual_get_prices_data_first_call_country_code)
        self.assertEqual("HU", actual_get_prices_data_second_call_country_code)
        self.assertEqual(2, mock_get_prices_data.call_count)

        self.assertEqual(
            self.expected_bg_api_prices_xml, actual_format_first_call_price_data
        )
        self.assertEqual("BG", actual_format_first_call_country_code)
        self.assertEqual(
            self.expected_hu_api_prices_xml, actual_format_second_call_price_data
        )
        self.assertEqual("HU", actual_format_second_call_country_code)
        self.assertEqual(2, mock_format_prices_data.call_count)

        pd.testing.assert_frame_equal(
            self.expected_prices_dataframe, actual_save_to_db_dataframe
        )
        self.assertEqual(1, mock_save_to_db.call_count)

    def test_get_start_end_date_without_request_parameters_returns_current_date(self):
        # When
        actual_start_date, actual_end_date = get_start_end_date({})

        # Then
        self.assertEqual(self.expected_start_date, actual_start_date)
        self.assertEqual(self.expected_end_date, actual_end_date)

    def test_get_start_end_date_with_request_parameters_returns_request_dates(self):
        # When
        actual_start_date, actual_end_date = get_start_end_date(
            self.expected_request_data
        )

        # Then
        self.assertEqual(self.expected_request_start_date, actual_start_date)
        self.assertEqual(self.expected_request_end_date, actual_end_date)

    def test_format_price_data(self):
        # When
        actual_formatted_prices = format_price_data(
            self.expected_bg_api_prices_xml, "BG"
        )

        # Then
        pd.testing.assert_frame_equal(
            self.expected_bg_formatted_prices, actual_formatted_prices
        )
