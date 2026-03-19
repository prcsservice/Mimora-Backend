"""
WebSocket Connection Manager — Real-time notifications for artists and customers
"""
import logging
import json
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    In-memory WebSocket connection manager.
    Manages active connections for artists and customers.
    """

    def __init__(self):
        # artist_id -> WebSocket
        self.artist_connections: Dict[str, WebSocket] = {}
        # customer_id -> WebSocket
        self.customer_connections: Dict[str, WebSocket] = {}

    async def connect_artist(self, artist_id: str, websocket: WebSocket):
        """Accept and register an artist WebSocket connection."""
        await websocket.accept()
        self.artist_connections[artist_id] = websocket
        logger.info(f"Artist {artist_id} connected via WebSocket")

    async def connect_customer(self, customer_id: str, websocket: WebSocket):
        """Accept and register a customer WebSocket connection."""
        await websocket.accept()
        self.customer_connections[customer_id] = websocket
        logger.info(f"Customer {customer_id} connected via WebSocket")

    def disconnect_artist(self, artist_id: str):
        """Remove artist connection."""
        self.artist_connections.pop(artist_id, None)
        logger.info(f"Artist {artist_id} disconnected")

    def disconnect_customer(self, customer_id: str):
        """Remove customer connection."""
        self.customer_connections.pop(customer_id, None)
        logger.info(f"Customer {customer_id} disconnected")

    async def notify_artist(self, artist_id: str, data: dict) -> bool:
        """
        Send a JSON message to an artist's WebSocket.
        Returns True if sent successfully, False if artist is not connected.
        """
        ws = self.artist_connections.get(artist_id)
        if ws:
            try:
                await ws.send_json(data)
                logger.info(f"Notification sent to artist {artist_id}: {data.get('type', 'unknown')}")
                return True
            except Exception as e:
                logger.error(f"Failed to notify artist {artist_id}: {e}")
                self.disconnect_artist(artist_id)
                return False
        else:
            logger.warning(f"Artist {artist_id} not connected via WebSocket")
            return False

    async def notify_customer(self, customer_id: str, data: dict) -> bool:
        """
        Send a JSON message to a customer's WebSocket.
        Returns True if sent successfully, False if customer is not connected.
        """
        ws = self.customer_connections.get(customer_id)
        if ws:
            try:
                await ws.send_json(data)
                logger.info(f"Notification sent to customer {customer_id}: {data.get('type', 'unknown')}")
                return True
            except Exception as e:
                logger.error(f"Failed to notify customer {customer_id}: {e}")
                self.disconnect_customer(customer_id)
                return False
        else:
            logger.warning(f"Customer {customer_id} not connected via WebSocket")
            return False

    @property
    def active_artist_count(self) -> int:
        return len(self.artist_connections)

    @property
    def active_customer_count(self) -> int:
        return len(self.customer_connections)


# Global singleton
ws_manager = ConnectionManager()
