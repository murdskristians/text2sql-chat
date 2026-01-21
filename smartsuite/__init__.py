"""
SmartSuite API Client Library

A Python library for interacting with the SmartSuite API in an object-oriented manner.

Usage:
    from smartsuite import SmartSuiteClient

    client = SmartSuiteClient()  # Uses .env file
    # or
    client = SmartSuiteClient(api_key="your_key", workspace_id="your_workspace")

    # Get all solutions
    solutions = client.solutions.list()

    # Get a specific solution
    solution = client.solutions.get("solution_id")

    # Get applications in a solution
    apps = solution.applications

    # Get table records
    records = client.tables.get("table_id").records.list()
"""

from .client import SmartSuiteClient
from .solutions import Solution, SolutionsManager
from .applications import Application, ApplicationsManager
from .tables import Table, TablesManager, Record, RecordsManager
from .transformers import DataTransformer

__version__ = "1.0.0"
__all__ = [
    "SmartSuiteClient",
    "Solution",
    "SolutionsManager",
    "Application",
    "ApplicationsManager",
    "Table",
    "TablesManager",
    "Record",
    "RecordsManager",
    "DataTransformer",
]
