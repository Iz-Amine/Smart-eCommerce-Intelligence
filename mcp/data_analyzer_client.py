from typing import Any, Dict, List
from mcp.mcp_base import MCPClient, MCPRequest

class DataAnalyzerClient(MCPClient):
    """Client for analyzing data through the MCP."""
    
    def __init__(self, name: str, host: Any):
        super().__init__(name, host)
    
    def query_data(self, query: str) -> List[Dict[str, Any]]:
        """Execute a data query."""
        response = self.make_request(
            action="query_data",
            parameters={"query": query},
            context={"purpose": "data_analysis"}
        )
        
        if response.status == "error":
            raise Exception(f"Query failed: {response.error}")
        
        return response.data
    
    def get_table_schema(self, table: str) -> Dict[str, Any]:
        """Get schema information for a table."""
        response = self.make_request(
            action="get_schema",
            parameters={"table": table},
            context={"purpose": "schema_analysis"}
        )
        
        if response.status == "error":
            raise Exception(f"Schema retrieval failed: {response.error}")
        
        return response.data
    
    def analyze_table(self, table: str) -> Dict[str, Any]:
        """Perform basic analysis on a table."""
        # Get schema first
        schema = self.get_table_schema(table)
        
        # Get row count
        count_query = f"SELECT COUNT(*) as count FROM {table}"
        count_result = self.query_data(count_query)
        row_count = count_result[0]["count"]
        
        # Get basic statistics for numeric columns
        numeric_columns = [
            col["name"] for col in schema["columns"]
            if col["type"] in ("INTEGER", "REAL")
        ]
        
        stats = {}
        for column in numeric_columns:
            stats_query = f"""
                SELECT 
                    MIN({column}) as min_val,
                    MAX({column}) as max_val,
                    AVG({column}) as avg_val
                FROM {table}
            """
            stats_result = self.query_data(stats_query)
            stats[column] = stats_result[0]
        
        return {
            "table_name": table,
            "row_count": row_count,
            "column_count": len(schema["columns"]),
            "numeric_columns_stats": stats
        } 