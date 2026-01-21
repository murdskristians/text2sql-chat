"""
SmartSuite API Client - Main entry point for the API.
"""

import os
from typing import Optional
from dotenv import load_dotenv

from .solutions import SolutionsManager
from .applications import ApplicationsManager
from .tables import TablesManager


class SmartSuiteClient:
    """
    Main client for interacting with the SmartSuite API.

    This client provides access to all SmartSuite resources through
    object-oriented managers.

    Attributes:
        solutions: Manager for Solution operations
        applications: Manager for Application operations
        tables: Manager for Table/Record operations

    Example:
        >>> client = SmartSuiteClient()
        >>> solutions = client.solutions.list()
        >>> for sol in solutions:
        ...     print(sol.name)
    """

    BASE_URL = "https://app.smartsuite.com/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        workspace_id: Optional[str] = None,
        env_file: Optional[str] = None
    ):
        """
        Initialize the SmartSuite client.

        Args:
            api_key: SmartSuite API key. If not provided, reads from
                     SMARTSUITE_API_KEY environment variable.
            workspace_id: SmartSuite workspace ID. If not provided, reads from
                          SMARTSUITE_WORKSPACE_ID environment variable.
            env_file: Path to .env file. Defaults to .env in current directory.

        Raises:
            ValueError: If API key or workspace ID is not provided and
                        cannot be found in environment variables.
        """
        # Load environment variables from .env file
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        self._api_key = api_key or os.getenv("SMARTSUITE_API_KEY")
        self._workspace_id = workspace_id or os.getenv("SMARTSUITE_WORKSPACE_ID")

        if not self._api_key:
            raise ValueError(
                "API key is required. Provide it as an argument or set "
                "SMARTSUITE_API_KEY environment variable."
            )

        if not self._workspace_id:
            raise ValueError(
                "Workspace ID is required. Provide it as an argument or set "
                "SMARTSUITE_WORKSPACE_ID environment variable."
            )

        # Initialize managers
        self._solutions = SolutionsManager(self)
        self._applications = ApplicationsManager(self)
        self._tables = TablesManager(self)

    @property
    def headers(self) -> dict:
        """Get the HTTP headers for API requests."""
        return {
            "Authorization": f"Token {self._api_key}",
            "Account-Id": self._workspace_id,
            "Content-Type": "application/json"
        }

    @property
    def solutions(self) -> SolutionsManager:
        """Access the Solutions manager."""
        return self._solutions

    @property
    def applications(self) -> ApplicationsManager:
        """Access the Applications manager."""
        return self._applications

    @property
    def tables(self) -> TablesManager:
        """Access the Tables manager."""
        return self._tables

    @property
    def workspace_id(self) -> str:
        """Get the workspace ID."""
        return self._workspace_id

    def __repr__(self) -> str:
        return f"SmartSuiteClient(workspace_id='{self._workspace_id}')"
