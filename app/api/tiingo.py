"""
Tiingo API integration for financial data
"""
import os
import requests
from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
from ..logger.log_handler import log_info, log_error

# Load environment variables if not already loaded
load_dotenv()

# Get Tiingo API token from environment variables
TIINGO_API_TOKEN = os.getenv("TIINGO_API_KEY", "")

class TiingoAPI:
    """
    Tiingo API client for financial data retrieval
    """
    BASE_URL = "https://api.tiingo.com"
    
    def __init__(self, token=None):
        """
        Initialize Tiingo API client with optional token override
        """
        self.token = token or TIINGO_API_TOKEN
        if not self.token:
            log_error("Tiingo API token not provided", "TiingoAPI")
            raise ValueError("Tiingo API token not provided")
        
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Token {self.token}'
        }
    
    def test_connection(self):
        """
        Test the Tiingo API connection
        """
        try:
            endpoint = f"{self.BASE_URL}/tiingo/daily/AAPL/prices"
            params = {
                'startDate': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                'endDate': datetime.now().strftime('%Y-%m-%d'),
                'format': 'json'
            }
            
            response = requests.get(endpoint, headers=self.headers, params=params)
            
            if response.status_code == 200:
                log_info("Tiingo API connection successful", "TiingoAPI")
                return True
            else:
                log_error(f"Tiingo API connection failed with status code {response.status_code}", "TiingoAPI")
                return False
        except Exception as e:
            log_error("Tiingo API connection test failed", "TiingoAPI", e)
            return False
    
    def get_stock_price(self, ticker):
        """
        Get the latest price for a stock ticker
        """
        try:
            endpoint = f"{self.BASE_URL}/tiingo/daily/{ticker}/prices"
            params = {
                'startDate': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                'endDate': datetime.now().strftime('%Y-%m-%d'),
                'format': 'json'
            }
            
            response = requests.get(endpoint, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    latest_price = data[-1]
                    log_info(f"Retrieved latest price for {ticker}: {latest_price['close']}", "TiingoAPI")
                    return latest_price
                else:
                    log_error(f"No price data available for {ticker}", "TiingoAPI")
                    return None
            else:
                log_error(f"Failed to get price for {ticker}. Status code: {response.status_code}", "TiingoAPI")
                return None
        except Exception as e:
            log_error(f"Error retrieving stock price for {ticker}", "TiingoAPI", e)
            return None
    
    def get_stock_data(self, ticker, start_date=None, end_date=None):
        """
        Get historical stock data for a ticker
        """
        try:
            endpoint = f"{self.BASE_URL}/tiingo/daily/{ticker}/prices"
            
            # Default to last 30 days if dates not provided
            end_date = end_date or datetime.now().strftime('%Y-%m-%d')
            start_date = start_date or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            params = {
                'startDate': start_date,
                'endDate': end_date,
                'format': 'json'
            }
            
            response = requests.get(endpoint, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                log_info(f"Retrieved {len(data)} days of data for {ticker}", "TiingoAPI")
                return data
            else:
                log_error(f"Failed to get data for {ticker}. Status code: {response.status_code}", "TiingoAPI")
                return None
        except Exception as e:
            log_error(f"Error retrieving stock data for {ticker}", "TiingoAPI", e)
            return None
    
    def get_ticker_metadata(self, ticker):
        """
        Get metadata for a ticker
        """
        try:
            endpoint = f"{self.BASE_URL}/tiingo/daily/{ticker}"
            
            response = requests.get(endpoint, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                log_info(f"Retrieved metadata for {ticker}", "TiingoAPI")
                return data
            else:
                log_error(f"Failed to get metadata for {ticker}. Status code: {response.status_code}", "TiingoAPI")
                return None
        except Exception as e:
            log_error(f"Error retrieving ticker metadata for {ticker}", "TiingoAPI", e)
            return None
    
    def search_tickers(self, query):
        """
        Search for tickers by name or symbol
        """
        try:
            endpoint = f"{self.BASE_URL}/tiingo/utilities/search"
            params = {
                'query': query,
                'format': 'json'
            }
            
            response = requests.get(endpoint, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                log_info(f"Found {len(data)} results for query: {query}", "TiingoAPI")
                return data
            else:
                log_error(f"Failed to search tickers. Status code: {response.status_code}", "TiingoAPI")
                return None
        except Exception as e:
            log_error(f"Error searching tickers", "TiingoAPI", e)
            return None

# Initialize global Tiingo API client
tiingo_api = None

def get_tiingo_api():
    """
    Get or create a global Tiingo API client
    """
    global tiingo_api
    if tiingo_api is None:
        tiingo_api = TiingoAPI()
    return tiingo_api
