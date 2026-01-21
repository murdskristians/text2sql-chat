"""
SmartSuite Applications module.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Dict, Any
import requests

if TYPE_CHECKING:
    from .client import SmartSuiteClient


class Field:
    """
    Represents a field in a SmartSuite Application.

    Attributes:
        label: The display label of the field
        slug: The programmatic name of the field
        field_type: The type of the field (text, number, etc.)
        raw_data: The complete raw data from the API
    """

    def __init__(self, data: Dict[str, Any]):
        """
        Initialize a Field object.

        Args:
            data: Raw field data from the API
        """
        self._data = data
        self.label: str = data.get("label", "")
        self.slug: str = data.get("slug", "")
        self.field_type: str = data.get("field_type", "")

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Get the raw data from the API."""
        return self._data

    def __repr__(self) -> str:
        return f"Field(label='{self.label}', slug='{self.slug}', type='{self.field_type}')"


class Application:
    """
    Represents a SmartSuite Application (also known as a Table).

    An Application contains fields (columns) and records (rows).

    Attributes:
        id: The unique identifier of the application
        name: The name of the application
        solution_id: The ID of the parent solution
        raw_data: The complete raw data from the API
    """

    def __init__(self, client: SmartSuiteClient, data: Dict[str, Any]):
        """
        Initialize an Application object.

        Args:
            client: The SmartSuiteClient instance
            data: Raw application data from the API
        """
        self._client = client
        self._data = data
        self.id: str = data.get("id", "")
        self.name: str = data.get("name", "")
        self.solution_id: str = data.get("solution", "")

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Get the raw data from the API."""
        return self._data

    @property
    def structure(self) -> List[Field]:
        """
        Get the schema/structure of this application.

        Returns:
            List of Field objects describing the application's fields.
        """
        url = f"{self._client.BASE_URL}/applications/{self.id}/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            data = response.json()
            schema = data.get("structure", [])
            return [Field(field_data) for field_data in schema]

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch structure: {e}") from e

    @property
    def fields(self) -> List[Field]:
        """Alias for structure property."""
        return self.structure

    def get_field(self, slug: str) -> Optional[Field]:
        """
        Get a specific field by its slug.

        Args:
            slug: The slug of the field to find.

        Returns:
            A Field object if found, None otherwise.
        """
        for field in self.structure:
            if field.slug == slug:
                return field
        return None

    def get_field_by_label(self, label: str) -> Optional[Field]:
        """
        Get a specific field by its label.

        Args:
            label: The label of the field to find.

        Returns:
            A Field object if found, None otherwise.
        """
        for field in self.structure:
            if field.label == label:
                return field
        return None

    @property
    def records(self):
        """
        Access records in this application through the Tables manager.

        Returns:
            A Table object that provides access to records.
        """
        return self._client.tables.get(self.id)

    def __repr__(self) -> str:
        return f"Application(id='{self.id}', name='{self.name}')"


class ApplicationsManager:
    """
    Manager for Application operations.

    Provides methods to list and retrieve applications from SmartSuite.
    """

    def __init__(self, client: SmartSuiteClient):
        """
        Initialize the ApplicationsManager.

        Args:
            client: The SmartSuiteClient instance
        """
        self._client = client

    def list(self, solution_id: Optional[str] = None) -> List[Application]:
        """
        Get all applications, optionally filtered by solution.

        Args:
            solution_id: Optional solution ID to filter applications.

        Returns:
            List of Application objects.

        Raises:
            RuntimeError: If the API request fails.

        Example:
            >>> apps = client.applications.list()
            >>> for app in apps:
            ...     print(f"{app.name}: {app.id}")
        """
        url = f"{self._client.BASE_URL}/applications/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            apps_data = response.json()

            # Filter by solution if specified
            if solution_id:
                apps_data = [
                    app for app in apps_data
                    if app.get("solution") == solution_id
                ]

            return [Application(self._client, app) for app in apps_data]

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch applications: {e}") from e

    def get(self, app_id: str) -> Application:
        """
        Get a specific application by ID.

        Args:
            app_id: The ID of the application to retrieve.

        Returns:
            An Application object.

        Raises:
            RuntimeError: If the API request fails.

        Example:
            >>> app = client.applications.get("abc123")
            >>> print(app.name)
            >>> for field in app.fields:
            ...     print(field.label)
        """
        url = f"{self._client.BASE_URL}/applications/{app_id}/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            data = response.json()
            return Application(self._client, data)

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch application {app_id}: {e}") from e

    def get_by_name(
        self,
        name: str,
        solution_id: Optional[str] = None
    ) -> Optional[Application]:
        """
        Find an application by name.

        Args:
            name: The name of the application to find.
            solution_id: Optional solution ID to narrow the search.

        Returns:
            An Application object if found, None otherwise.

        Example:
            >>> app = client.applications.get_by_name("Products")
            >>> if app:
            ...     print(app.id)
        """
        apps = self.list(solution_id=solution_id)
        for app in apps:
            if app.name == name:
                return app
        return None
