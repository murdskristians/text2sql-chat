"""
SmartSuite Tables and Records module.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Dict, Any, Iterator
import requests

if TYPE_CHECKING:
    from .client import SmartSuiteClient


class Record:
    """
    Represents a single record (row) in a SmartSuite table.

    Provides dictionary-like access to record fields.

    Attributes:
        id: The unique identifier of the record
        raw_data: The complete raw data from the API
    """

    def __init__(self, client: SmartSuiteClient, table_id: str, data: Dict[str, Any]):
        """
        Initialize a Record object.

        Args:
            client: The SmartSuiteClient instance
            table_id: The ID of the parent table
            data: Raw record data from the API
        """
        self._client = client
        self._table_id = table_id
        self._data = data
        self.id: str = data.get("id", "")

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Get the raw data from the API."""
        return self._data

    def __getitem__(self, key: str) -> Any:
        """
        Get a field value by key (dictionary-like access).

        Args:
            key: The field slug or key to access.

        Returns:
            The value of the field.
        """
        return self._data.get(key)

    def __contains__(self, key: str) -> bool:
        """Check if a field exists in the record."""
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a field value with a default.

        Args:
            key: The field slug or key to access.
            default: Default value if key is not found.

        Returns:
            The value of the field or the default.
        """
        return self._data.get(key, default)

    def keys(self) -> List[str]:
        """Get all field keys in the record."""
        return list(self._data.keys())

    def values(self) -> List[Any]:
        """Get all field values in the record."""
        return list(self._data.values())

    def items(self) -> List[tuple]:
        """Get all key-value pairs in the record."""
        return list(self._data.items())

    def to_dict(self) -> Dict[str, Any]:
        """Convert the record to a plain dictionary."""
        return dict(self._data)

    def __repr__(self) -> str:
        return f"Record(id='{self.id}')"


class RecordsManager:
    """
    Manager for Record operations within a table.

    Provides methods to list, filter, and retrieve records.
    """

    def __init__(self, client: SmartSuiteClient, table_id: str):
        """
        Initialize the RecordsManager.

        Args:
            client: The SmartSuiteClient instance
            table_id: The ID of the table
        """
        self._client = client
        self._table_id = table_id

    def list(
        self,
        filter: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Dict[str, Any]]] = None,
        hydrated: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Record]:
        """
        Get records from the table.

        Args:
            filter: Optional filter criteria (SmartSuite filter format).
            sort: Optional sort criteria (SmartSuite sort format).
            hydrated: If True, returns human-readable values for linked records.
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of Record objects.

        Raises:
            RuntimeError: If the API request fails.

        Example:
            >>> records = table.records.list(hydrated=True)
            >>> for record in records:
            ...     print(record["title"])
        """
        url = f"{self._client.BASE_URL}/applications/{self._table_id}/records/list/"

        payload = {
            "filter": filter or {},
            "sort": sort or [],
            "hydrated": hydrated
        }

        if limit is not None:
            payload["limit"] = limit
        if offset > 0:
            payload["offset"] = offset

        try:
            response = requests.post(url, headers=self._client.headers, json=payload)
            response.raise_for_status()

            data = response.json()
            items = data.get("items", [])
            return [Record(self._client, self._table_id, item) for item in items]

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch records: {e}") from e

    def get(self, record_id: str) -> Record:
        """
        Get a specific record by ID.

        Args:
            record_id: The ID of the record to retrieve.

        Returns:
            A Record object.

        Raises:
            RuntimeError: If the API request fails.
        """
        url = f"{self._client.BASE_URL}/applications/{self._table_id}/records/{record_id}/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            data = response.json()
            return Record(self._client, self._table_id, data)

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch record {record_id}: {e}") from e

    def filter(
        self,
        field: str,
        operator: str,
        value: Any,
        hydrated: bool = True
    ) -> List[Record]:
        """
        Filter records by a single field condition.

        Args:
            field: The field slug to filter on.
            operator: The comparison operator (eq, ne, contains, etc.).
            value: The value to compare against.
            hydrated: If True, returns human-readable values.

        Returns:
            List of matching Record objects.

        Example:
            >>> active = table.records.filter("status", "eq", "active")
        """
        filter_spec = {
            "operator": "and",
            "fields": [
                {
                    "field": field,
                    "comparison": operator,
                    "value": value
                }
            ]
        }
        return self.list(filter=filter_spec, hydrated=hydrated)

    def all(self, hydrated: bool = True) -> Iterator[Record]:
        """
        Iterate through all records in the table (handles pagination).

        Args:
            hydrated: If True, returns human-readable values.

        Yields:
            Record objects.

        Example:
            >>> for record in table.records.all():
            ...     print(record["title"])
        """
        offset = 0
        batch_size = 100

        while True:
            records = self.list(hydrated=hydrated, limit=batch_size, offset=offset)
            if not records:
                break

            for record in records:
                yield record

            if len(records) < batch_size:
                break

            offset += batch_size

    def count(self) -> int:
        """
        Get the total number of records in the table.

        Returns:
            The count of records.

        Note:
            This makes an API call to fetch records.
        """
        url = f"{self._client.BASE_URL}/applications/{self._table_id}/records/list/"

        payload = {
            "filter": {},
            "sort": [],
            "hydrated": False,
            "limit": 1
        }

        try:
            response = requests.post(url, headers=self._client.headers, json=payload)
            response.raise_for_status()

            data = response.json()
            return data.get("total", 0)

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to count records: {e}") from e


class Table:
    """
    Represents a SmartSuite Table (Application) with record access.

    This is a convenience class that wraps an Application with
    easier record access.

    Attributes:
        id: The unique identifier of the table
        name: The name of the table
        records: Manager for record operations
    """

    def __init__(self, client: SmartSuiteClient, table_id: str, data: Optional[Dict[str, Any]] = None):
        """
        Initialize a Table object.

        Args:
            client: The SmartSuiteClient instance
            table_id: The ID of the table
            data: Optional raw data from the API
        """
        self._client = client
        self.id = table_id
        self._data = data or {}
        self.name = self._data.get("name", "")
        self._records = RecordsManager(client, table_id)

    @property
    def records(self) -> RecordsManager:
        """Access the records manager for this table."""
        return self._records

    @property
    def structure(self) -> List[Dict[str, Any]]:
        """
        Get the schema/structure of this table.

        Returns:
            List of field definitions.
        """
        url = f"{self._client.BASE_URL}/applications/{self.id}/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            data = response.json()
            return data.get("structure", [])

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch table structure: {e}") from e

    @property
    def fields(self) -> List[Dict[str, str]]:
        """
        Get a simplified list of fields.

        Returns:
            List of dictionaries with label, slug, and field_type.
        """
        return [
            {
                "label": field.get("label"),
                "slug": field.get("slug"),
                "field_type": field.get("field_type")
            }
            for field in self.structure
        ]

    def get_rows(self, **kwargs) -> List[Record]:
        """
        Alias for records.list() for convenience.

        Returns:
            List of Record objects.
        """
        return self._records.list(**kwargs)

    def __repr__(self) -> str:
        return f"Table(id='{self.id}', name='{self.name}')"


class TablesManager:
    """
    Manager for Table operations.

    Provides methods to access and work with tables.
    """

    def __init__(self, client: SmartSuiteClient):
        """
        Initialize the TablesManager.

        Args:
            client: The SmartSuiteClient instance
        """
        self._client = client

    def get(self, table_id: str) -> Table:
        """
        Get a table by ID.

        Args:
            table_id: The ID of the table.

        Returns:
            A Table object.

        Example:
            >>> table = client.tables.get("abc123")
            >>> records = table.records.list()
        """
        # Fetch the application data to populate table info
        url = f"{self._client.BASE_URL}/applications/{table_id}/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            data = response.json()
            return Table(self._client, table_id, data)

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch table {table_id}: {e}") from e

    def list_in_solution(self, solution_id: str) -> List[Table]:
        """
        Get all tables in a solution.

        Args:
            solution_id: The ID of the solution.

        Returns:
            List of Table objects.

        Example:
            >>> tables = client.tables.list_in_solution("sol123")
            >>> for table in tables:
            ...     print(table.name)
        """
        url = f"{self._client.BASE_URL}/solutions/{solution_id}/"

        try:
            response = requests.get(url, headers=self._client.headers)
            response.raise_for_status()

            data = response.json()
            items = data.get("items", [])

            return [
                Table(self._client, item.get("id"), item)
                for item in items
            ]

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch tables for solution {solution_id}: {e}") from e
