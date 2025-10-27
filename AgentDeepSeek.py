import os
import json
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
from abc import ABC, abstractmethod

# Import the base Trader class
from Agent import Agent


class AgentDeepSeek(Agent):
    """Class to handle trading decisions using DeepSeek API"""

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-reasoner"  # Using the reasoner version as requested

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for DeepSeek API"""
        if not self.api_key:
            raise ValueError("DeepSeek API key not found in environment variables")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }