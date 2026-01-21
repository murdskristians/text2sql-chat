"""
SmartSuite Solutions module.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Dict, Any
import requests

if TYPE_CHECKING:
    from .client import SmartSuiteClient


class Solution:
    """
    Represents a SmartSuite Solution.

    A Solution is a container for Applications (tables) in SmartSuite.

    Attributes:
        id: The unique identifier of the solution
        name: The name of the solution
        description: Description of the solution
        raw_data: The complete raw data from the API
    """

    def __init__(self, client: SmartSuiteClient, data: Dict[str, Any]):
        """
        Initialize a Solution object.

        Args:
            client: The SmartSuiteClient instance
            data: Raw solution data from the API
        """
        self._client = client
        self._data = data
        self.id: str = data.get("id", "")
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "")

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Get the raw data from the API."""
        return self._data

    @property
    def applications(self) -> List:
        """
        Get all applications (tables) in this solution.

        Returns:
            List of Application objects belonging to this solution.
        """
        return self._client.applications.list(solution_id=self.id)

    @property
    def tables(self) -> List[Dict[str, str]]:
        """
        Get a simplified list of tables in this solution.

        Returns:
            List of dictionaries with table_name and table_id keys.
        """
        url = f"{self._client.BASE_URL}/solutions/{self.id}/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            data = response.json()
            items = data.get("items", [])

            return [
                {"table_name": item.get("name"), "table_id": item.get("id")}
                for item in items
            ]
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch tables: {e}") from e

    def __repr__(self) -> str:
        return f"Solution(id='{self.id}', name='{self.name}')"


class SolutionsManager:
    """
    Manager for Solution operations.

    Provides methods to list and retrieve solutions from SmartSuite.
    """

    def __init__(self, client: SmartSuiteClient):
        """
        Initialize the SolutionsManager.

        Args:
            client: The SmartSuiteClient instance
        """
        self._client = client

    def list(self) -> List[Solution]:
        """
        Get all solutions in the workspace.

        Returns:
            List of Solution objects.

        Raises:
            RuntimeError: If the API request fails.

        Example:
            >>> solutions = client.solutions.list()
            >>> for sol in solutions:
            ...     print(f"{sol.name}: {sol.id}")
        """
        url = f"{self._client.BASE_URL}/solutions/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            solutions_data = response.json()
            return [Solution(self._client, sol) for sol in solutions_data]

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch solutions: {e}") from e

    def get(self, solution_id: str) -> Solution:
        """
        Get a specific solution by ID.

        Args:
            solution_id: The ID of the solution to retrieve.

        Returns:
            A Solution object.

        Raises:
            RuntimeError: If the API request fails.

        Example:
            >>> solution = client.solutions.get("abc123")
            >>> print(solution.name)
        """
        url = f"{self._client.BASE_URL}/solutions/{solution_id}/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            data = response.json()
            return Solution(self._client, data)

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch solution {solution_id}: {e}") from e

    def get_by_name(self, name: str) -> Optional[Solution]:
        """
        Find a solution by name.

        Args:
            name: The name of the solution to find.

        Returns:
            A Solution object if found, None otherwise.

        Example:
            >>> solution = client.solutions.get_by_name("My Project")
            >>> if solution:
            ...     print(solution.id)
        """
        solutions = self.list()
        for sol in solutions:
            if sol.name == name:
                return sol
        return None
