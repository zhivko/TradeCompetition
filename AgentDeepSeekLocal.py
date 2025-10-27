import os
import json
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
from abc import ABC, abstractmethod

# Import the base Trader class
from Agent import Agent


class AgentDeepSeekLocal(Agent):
    """Class to handle trading decisions using local DeepSeek model via LM Studio"""

    def __init__(self, api_url: str = "http://localhost:1234/v1/chat/completions", model: str = "deepseek/deepseek-r1-0528-qwen3-8b"):
        self.api_url = api_url
        self.model = model

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for local DeepSeek API"""
        return {
            "Content-Type": "application/json"
        }