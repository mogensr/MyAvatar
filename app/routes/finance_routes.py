"""
Finance routes for MyAvatar using Tiingo API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
from ..auth.authentication import get_current_user
from ..api.tiingo import get_tiingo_api
from ..logger.log_handler import log_info, log_error

# Create router
router = APIRouter(prefix="/finance", tags=["finance"])

@router.get("/stock/{ticker}")
async def get_stock_price(ticker: str, current_user = Depends(get_current_user)):
    """
    Get the latest stock price for a ticker
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        tiingo_api = get_tiingo_api()
        price_data = tiingo_api.get_stock_price(ticker)
        
        if price_data:
            return {
                "success": True,
                "ticker": ticker,
                "data": price_data
            }
        else:
            raise HTTPException(status_code=404, detail=f"No data found for ticker {ticker}")
    except Exception as e:
        log_error(f"Error getting stock price for {ticker}", "FinanceRoutes", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stock/{ticker}/history")
async def get_stock_history(
    ticker: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user = Depends(get_current_user)
):
    """
    Get historical stock data for a ticker
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Validate dates if provided
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
        
        if end_date:
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
        
        tiingo_api = get_tiingo_api()
        history_data = tiingo_api.get_stock_data(ticker, start_date, end_date)
        
        if history_data:
            return {
                "success": True,
                "ticker": ticker,
                "data": history_data
            }
        else:
            raise HTTPException(status_code=404, detail=f"No historical data found for ticker {ticker}")
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting stock history for {ticker}", "FinanceRoutes", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_tickers(query: str, current_user = Depends(get_current_user)):
    """
    Search for tickers by name or symbol
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        tiingo_api = get_tiingo_api()
        search_results = tiingo_api.search_tickers(query)
        
        if search_results:
            return {
                "success": True,
                "query": query,
                "results": search_results
            }
        else:
            return {
                "success": True,
                "query": query,
                "results": []
            }
    except Exception as e:
        log_error(f"Error searching tickers with query '{query}'", "FinanceRoutes", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metadata/{ticker}")
async def get_ticker_metadata(ticker: str, current_user = Depends(get_current_user)):
    """
    Get metadata for a ticker
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        tiingo_api = get_tiingo_api()
        metadata = tiingo_api.get_ticker_metadata(ticker)
        
        if metadata:
            return {
                "success": True,
                "ticker": ticker,
                "data": metadata
            }
        else:
            raise HTTPException(status_code=404, detail=f"No metadata found for ticker {ticker}")
    except Exception as e:
        log_error(f"Error getting metadata for {ticker}", "FinanceRoutes", e)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-connection")
async def test_tiingo_connection(current_user = Depends(get_current_user)):
    """
    Test the Tiingo API connection
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        tiingo_api = get_tiingo_api()
        connection_success = tiingo_api.test_connection()
        
        if connection_success:
            return {
                "success": True,
                "message": "Tiingo API connection successful"
            }
        else:
            return {
                "success": False,
                "message": "Tiingo API connection failed"
            }
    except Exception as e:
        log_error("Error testing Tiingo API connection", "FinanceRoutes", e)
        raise HTTPException(status_code=500, detail=str(e))
