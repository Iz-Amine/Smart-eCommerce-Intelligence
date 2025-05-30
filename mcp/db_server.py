from typing import Any, Dict, List
import sqlite3
from mcp.mcp_base import MCPServer, MCPRequest

class DatabaseServer(MCPServer):
    """MCP Server for handling database operations."""
    
    def __init__(self, name: str, host: Any, db_path: str):
        # Define permissions for different clients
        permissions = {
            "data_analyzer": ["query_data", "get_schema"],
            "report_generator": ["query_data"],
            "admin": ["query_data", "get_schema", "modify_data"]
        }
        super().__init__(name, host, permissions)
        self.db_path = db_path
    
    def _process_request(self, request: MCPRequest) -> Any:
        """Process database-related requests."""
        if request.action == "query_data":
            return self._execute_query(request.parameters.get("query", ""))
        elif request.action == "get_schema":
            return self._get_schema(request.parameters.get("table", ""))
        elif request.action == "modify_data":
            return self._modify_data(
                request.parameters.get("query", ""),
                request.parameters.get("params", {})
            )
        else:
            raise ValueError(f"Unknown action: {request.action}")
    
    def _execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a read-only query."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def _get_schema(self, table: str) -> Dict[str, Any]:
        """Get schema information for a table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            return {
                "table": table,
                "columns": [
                    {
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "default_value": col[4],
                        "primary_key": bool(col[5])
                    }
                    for col in columns
                ]
            }
    
    def _modify_data(self, query: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a data modification query."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return {
                "rows_affected": cursor.rowcount,
                "last_row_id": cursor.lastrowid
            } 