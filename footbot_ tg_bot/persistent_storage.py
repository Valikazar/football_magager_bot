import json
from typing import Any, Dict, Optional, Tuple, Union

from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.fsm.state import State
import database as db

class MySQLStorage(BaseStorage):
    """
    Custom MySQL-based FSM storage for aiogram.
    """

    async def set_state(self, key: StorageKey, state: Optional[Union[str, State]] = None) -> None:
        state_str = state.state if isinstance(state, State) else state
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO fsm_data (chat_id, user_id, state) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE state = VALUES(state)",
            (key.chat_id, key.user_id, state_str)
        )
        conn.commit()
        conn.close()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT state FROM fsm_data WHERE chat_id = %s AND user_id = %s",
            (key.chat_id, key.user_id)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        data_json = json.dumps(data)
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO fsm_data (chat_id, user_id, data) VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE data = VALUES(data)",
            (key.chat_id, key.user_id, data_json)
        )
        conn.commit()
        conn.close()

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT data FROM fsm_data WHERE chat_id = %s AND user_id = %s",
            (key.chat_id, key.user_id)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return json.loads(result[0])
        return {}

    async def close(self) -> None:
        pass
