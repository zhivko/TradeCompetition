    async def get_liquidation_orders_new(self, symbol: str) -> Dict:
        """Get liquidation orders data for a symbol (futures) - new implementation"""
        # Binance futures API for all force orders (liquidations)
        # According to Binance documentation, this endpoint may require authentication or have rate limiting
        
        # Try first with public endpoint (no authentication needed)
        endpoint = f"{self.futures_url}/fapi/v1/allForceOrders"
        params = {"symbol": f"{symbol}USDT"}  # Specific symbol parameter
        
        try:
            async with self.session.get(endpoint, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Successfully fetched liquidation orders for {symbol}")
                    # Return data in the expected format
                    if isinstance(data, list):
                        return {"rows": data[:50], "total": len(data)}  # Limit to 50 orders
                    else:
                        return data if isinstance(data, dict) else {"rows": [], "total": 0}
                elif response.status == 400:
                    # Try without symbol parameter
                    logger.info(f"Trying without symbol parameter for {symbol}")
                    params = {}
                    async with self.session.get(endpoint, params=params) as response2:
                        if response2.status == 200:
                            data = await response2.json()
                            logger.info(f"Successfully fetched liquidation orders for {symbol} (no symbol param)")
                            # Filter for the specific symbol
                            if isinstance(data, list):
                                filtered_rows = [row for row in data if row.get("symbol", "").startswith(f"{symbol}USDT")]
                                return {"rows": filtered_rows[:50], "total": len(filtered_rows)}  # Limit to 50 orders
                            else:
                                return data if isinstance(data, dict) else {"rows": [], "total": 0}
                        else:
                            logger.info(f"All attempts failed for {symbol}: {response2.status}")
                            return {"rows": [], "total": 0}
                elif response.status == 401:
                    # If unauthorized, try with explicit authentication headers
                    if self.api_key:
                        logger.info(f"Attempting authenticated request for liquidation orders for {symbol}")
                        headers = {"X-MBX-APIKEY": self.api_key}
                        params = {"symbol": f"{symbol}USDT"}
                        async with self.session.get(endpoint, params=params, headers=headers) as auth_response:
                            if auth_response.status == 200:
                                data = await auth_response.json()
                                logger.info(f"Successfully fetched authenticated liquidation orders for {symbol}")
                                # Return data in the expected format
                                if isinstance(data, list):
                                    return {"rows": data[:50], "total": len(data)}  # Limit to 50 orders
                                else:
                                    return data if isinstance(data, dict) else {"rows": [], "total": 0}
                            else:
                                logger.info(f"Authenticated request failed for {symbol}: {auth_response.status}")
                                return {"rows": [], "total": 0}
                    else:
                        logger.info(f"No API key available for authenticated request for {symbol}")
                        return {"rows": [], "total": 0}
                else:
                    logger.info(f"Error fetching liquidation orders for {symbol}: {response.status}")
                    return {"rows": [], "total": 0}
        except Exception as e:
            logger.info(f"Exception fetching liquidation orders for {symbol}: {e}")
            # Return empty data when exception occurs
            return {
                "rows": [],
                "total": 0
            }