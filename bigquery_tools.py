"""
BigQuery Tools for Text-to-SQL Agent.

Provides tools for fetching schema information and executing SQL queries.
"""

import os
import json
from decimal import Decimal
from typing import Optional, List, Dict, Any
from google.cloud import bigquery
from google.adk.tools import FunctionTool
from dotenv import load_dotenv

load_dotenv()

# Initialize BigQuery client
_client: Optional[bigquery.Client] = None


def convert_to_json_safe(value: Any) -> Any:
    """Convert BigQuery values to JSON-serializable types.

    BUG #31 FIX: Ensure all Decimal and numeric types are properly converted.
    """
    if value is None:
        return None

    # Handle Decimal FIRST (before other numeric checks)
    # This fixes BUG #31: Object of type Decimal is not JSON serializable
    if isinstance(value, Decimal):
        try:
            if value == value.to_integral_value():
                return int(value)
            return float(value)
        except Exception:
            return str(value)

    # Handle datetime, date, time objects
    if hasattr(value, 'isoformat'):
        return value.isoformat()

    # Handle bytes
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')

    # Handle REPEATED fields (lists, tuples)
    if isinstance(value, (list, tuple)):
        return [convert_to_json_safe(item) for item in value]

    # Handle STRUCT/RECORD fields (dicts)
    if isinstance(value, dict):
        return {str(k): convert_to_json_safe(v) for k, v in value.items()}

    # Handle named tuples (BigQuery Row objects)
    if hasattr(value, '_asdict'):
        return {str(k): convert_to_json_safe(v) for k, v in value._asdict().items()}

    # Handle basic JSON-serializable types
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        # Handle special float values
        if value != value:  # NaN check
            return None
        if value == float('inf') or value == float('-inf'):
            return str(value)
        return value
    if isinstance(value, str):
        return value

    # Handle any other numeric types (numpy, etc.)
    if hasattr(value, '__float__'):
        try:
            return float(value)
        except Exception:
            return str(value)
    if hasattr(value, '__int__'):
        try:
            return int(value)
        except Exception:
            return str(value)

    # Fallback: convert to string
    return str(value)


def get_bigquery_client() -> bigquery.Client:
    """Get or create a BigQuery client."""
    global _client
    if _client is None:
        project_id = os.environ.get('GCP_PROJECT_ID', 'hotcode-erp')
        _client = bigquery.Client(project=project_id)
    return _client


def get_table_schema(
    project_id: str = "hotcode-erp",
    dataset_id: str = "smartsuite",
    table_id: str = "smartsuite"
) -> Dict[str, Any]:
    """
    Fetch the schema of a BigQuery table.

    Args:
        project_id: The GCP project ID
        dataset_id: The BigQuery dataset ID
        table_id: The BigQuery table ID

    Returns:
        Dictionary containing table schema information with field names,
        types, descriptions, and sample values.
    """
    client = get_bigquery_client()
    table_ref = f"{project_id}.{dataset_id}.{table_id}"

    try:
        table = client.get_table(table_ref)

        schema_info = {
            "table": table_ref,
            "description": table.description or "No description",
            "num_rows": convert_to_json_safe(table.num_rows),
            "fields": []
        }

        for field in table.schema:
            field_info = {
                "name": str(field.name),
                "type": str(field.field_type),
                "mode": str(field.mode),
                "description": str(field.description) if field.description else ""
            }
            schema_info["fields"].append(field_info)

        return schema_info

    except Exception as e:
        return {"error": str(e)}


def list_available_tables(
    project_id: str = "hotcode-erp",
    dataset_id: str = "smartsuite"
) -> List[Dict[str, str]]:
    """
    List all available tables in a BigQuery dataset.

    Args:
        project_id: The GCP project ID
        dataset_id: The BigQuery dataset ID

    Returns:
        List of dictionaries with table_id and description.
    """
    client = get_bigquery_client()
    dataset_ref = f"{project_id}.{dataset_id}"

    try:
        tables = list(client.list_tables(dataset_ref))
        return [
            {
                "table_id": table.table_id,
                "full_path": f"{project_id}.{dataset_id}.{table.table_id}"
            }
            for table in tables
        ]
    except Exception as e:
        return [{"error": str(e)}]


def execute_sql_query(
    query: str,
    max_results: int = 100
) -> Dict[str, Any]:
    """
    Execute a SQL query on BigQuery and return the results.

    Args:
        query: The SQL query to execute. Must be a SELECT query for safety.
        max_results: Maximum number of rows to return (default 100).

    Returns:
        Dictionary containing the query results with columns and rows,
        or an error message if the query fails.
    """
    # Safety check - only allow SELECT queries
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT") and not query_upper.startswith("WITH"):
        return {
            "error": "Only SELECT queries are allowed for safety reasons. Query must start with SELECT or WITH (for CTEs).",
            "query": query
        }

    # Block dangerous operations - comprehensive list
    dangerous_keywords = [
        "DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER", "CREATE",
        "MERGE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL",
        "SET ", "DECLARE", "BEGIN", "COMMIT", "ROLLBACK"
    ]
    for keyword in dangerous_keywords:
        # Check for keyword as a separate word to avoid false positives
        if f" {keyword}" in f" {query_upper}" or query_upper.startswith(keyword):
            return {
                "error": f"Query contains forbidden keyword: {keyword.strip()}. Only read-only SELECT queries are allowed.",
                "query": query
            }

    client = get_bigquery_client()

    try:
        # Configure the query
        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=10 * 1024 * 1024 * 1024  # 10 GB limit
        )

        # Execute the query
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()

        # Convert to list of dicts
        rows = []
        columns = [field.name for field in results.schema]

        for i, row in enumerate(results):
            if i >= max_results:
                break
            row_dict = {}
            for col in columns:
                value = row[col]
                # Convert non-serializable types to JSON-safe values
                value = convert_to_json_safe(value)
                row_dict[col] = value
            rows.append(row_dict)

        result = {
            "success": True,
            "columns": columns,
            "rows": rows,
            "total_rows": convert_to_json_safe(results.total_rows),
            "returned_rows": len(rows),
            "query": query
        }

        # BUG #31 FIX: Ensure entire result is JSON-serializable
        # Double-check by attempting JSON serialization
        try:
            json.dumps(result)
        except (TypeError, ValueError) as json_err:
            # If serialization fails, recursively convert all values
            result = {k: convert_to_json_safe(v) for k, v in result.items()}

        return result

    except Exception as e:
        return {
            "error": str(e),
            "query": query
        }


def get_sample_data(
    project_id: str = "hotcode-erp",
    dataset_id: str = "smartsuite",
    table_id: str = "smartsuite",
    limit: int = 5
) -> Dict[str, Any]:
    """
    Get sample data from a table to help understand the data format.

    Args:
        project_id: The GCP project ID
        dataset_id: The BigQuery dataset ID
        table_id: The BigQuery table ID
        limit: Number of sample rows to return

    Returns:
        Dictionary with sample rows from the table.
    """
    query = f"SELECT * FROM `{project_id}.{dataset_id}.{table_id}` LIMIT {limit}"
    return execute_sql_query(query, max_results=limit)


def get_column_statistics(
    project_id: str = "hotcode-erp",
    dataset_id: str = "smartsuite",
    table_id: str = "smartsuite",
    column_name: str = ""
) -> Dict[str, Any]:
    """
    Get statistics for a specific column (distinct values, counts, etc.).

    Args:
        project_id: The GCP project ID
        dataset_id: The BigQuery dataset ID
        table_id: The BigQuery table ID
        column_name: The column to analyze

    Returns:
        Dictionary with column statistics.
    """
    if not column_name:
        return {"error": "column_name is required"}

    query = f"""
    SELECT
        COUNT(*) as total_rows,
        COUNT(DISTINCT `{column_name}`) as distinct_values,
        COUNT(`{column_name}`) as non_null_count
    FROM `{project_id}.{dataset_id}.{table_id}`
    """
    return execute_sql_query(query, max_results=1)


# Create FunctionTool wrappers for the agent
get_schema_tool = FunctionTool(func=get_table_schema)
list_tables_tool = FunctionTool(func=list_available_tables)
execute_query_tool = FunctionTool(func=execute_sql_query)
get_sample_tool = FunctionTool(func=get_sample_data)
get_stats_tool = FunctionTool(func=get_column_statistics)
