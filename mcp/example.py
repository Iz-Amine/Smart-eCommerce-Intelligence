import logging
from mcp.mcp_base import MCPHost
from mcp.db_server import DatabaseServer
from mcp.data_analyzer_client import DataAnalyzerClient

def setup_logging():
    """Configure logging for the MCP components."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    # Setup logging
    setup_logging()
    
    # Create the MCP host
    host = MCPHost("main_host")
    
    # Create and register the database server
    db_server = DatabaseServer(
        name="smart_ecom_db",
        host=host,
        db_path="smart_ecom_new.db"
    )
    
    # Create the data analyzer client
    analyzer = DataAnalyzerClient("data_analyzer", host)
    
    try:
        # Example: Analyze a table
        print("\nAnalyzing 'products' table:")
        analysis = analyzer.analyze_table("products")
        print(f"Table: {analysis['table_name']}")
        print(f"Total rows: {analysis['row_count']}")
        print(f"Total columns: {analysis['column_count']}")
        print("\nNumeric columns statistics:")
        for column, stats in analysis['numeric_columns_stats'].items():
            print(f"\n{column}:")
            print(f"  Min: {stats['min_val']}")
            print(f"  Max: {stats['max_val']}")
            print(f"  Avg: {stats['avg_val']:.2f}")
        
        # Example: Get schema information
        print("\nSchema for 'customers' table:")
        schema = analyzer.get_table_schema("customers")
        print(f"Table: {schema['table']}")
        print("\nColumns:")
        for column in schema['columns']:
            print(f"  {column['name']} ({column['type']})")
            if column['primary_key']:
                print("    Primary Key")
            if column['not_null']:
                print("    Not Null")
            if column['default_value'] is not None:
                print(f"    Default: {column['default_value']}")
        
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 