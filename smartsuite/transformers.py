"""
SmartSuite Data Transformers module.

Provides utilities for cleaning and transforming SmartSuite data,
particularly for Firestore compatibility.
"""

from typing import Any, Dict, List, Optional, Set
import json


class DataTransformer:
    """
    Utility class for transforming and cleaning SmartSuite data.

    This class provides static methods for:
    - Cleaning data for Firestore compatibility
    - Flattening nested structures
    - Simplifying SmartSuite-specific data formats
    """

    # Default fields to exclude from cleaned data
    DEFAULT_EXCLUDE_KEYS: Set[str] = {
        "history",
        "links",
        "permissions",
        "member_roles",
        "audit_trail"
    }

    # Maximum depth for Firestore (Firestore limit is 20)
    MAX_DEPTH: int = 15

    @staticmethod
    def clean_for_firestore(
        data: Any,
        exclude_keys: Optional[Set[str]] = None,
        max_depth: int = 15,
        current_depth: int = 0
    ) -> Any:
        """
        Clean data for Firestore compatibility.

        Removes deeply nested structures and problematic fields.

        Args:
            data: The data to clean (dict, list, or primitive).
            exclude_keys: Set of keys to exclude from dictionaries.
            max_depth: Maximum nesting depth (Firestore limit is 20).
            current_depth: Current recursion depth (internal use).

        Returns:
            Cleaned data safe for Firestore import.

        Example:
            >>> cleaned = DataTransformer.clean_for_firestore(raw_data)
        """
        if exclude_keys is None:
            exclude_keys = DataTransformer.DEFAULT_EXCLUDE_KEYS

        # Stop at max depth to stay safely under Firestore's limit
        if current_depth > max_depth:
            return str(data)

        if isinstance(data, dict):
            cleaned = {}
            for key, value in data.items():
                if key not in exclude_keys:
                    cleaned[key] = DataTransformer.clean_for_firestore(
                        value, exclude_keys, max_depth, current_depth + 1
                    )
            return cleaned

        elif isinstance(data, list):
            return [
                DataTransformer.clean_for_firestore(
                    item, exclude_keys, max_depth, current_depth + 1
                )
                for item in data
            ]

        return data

    @staticmethod
    def simplify(data: Any, exclude_keys: Optional[Set[str]] = None) -> Any:
        """
        Simplify SmartSuite data by removing common unnecessary fields.

        Args:
            data: The data to simplify.
            exclude_keys: Additional keys to exclude.

        Returns:
            Simplified data.

        Example:
            >>> simple = DataTransformer.simplify(record.raw_data)
        """
        default_exclude = {"links", "history"}
        if exclude_keys:
            default_exclude = default_exclude.union(exclude_keys)

        if isinstance(data, dict):
            return {
                k: DataTransformer.simplify(v, exclude_keys)
                for k, v in data.items()
                if k not in default_exclude
            }
        elif isinstance(data, list):
            return [DataTransformer.simplify(item, exclude_keys) for item in data]

        return data

    @staticmethod
    def flatten(
        data: Dict[str, Any],
        parent_key: str = "",
        separator: str = "."
    ) -> Dict[str, Any]:
        """
        Flatten a nested dictionary into a single-level dictionary.

        Args:
            data: The nested dictionary to flatten.
            parent_key: Prefix for keys (internal use).
            separator: Character to use between nested key levels.

        Returns:
            Flattened dictionary with dot-notation keys.

        Example:
            >>> flat = DataTransformer.flatten({"a": {"b": 1}})
            >>> # Result: {"a.b": 1}
        """
        items: List[tuple] = []

        for key, value in data.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key

            if isinstance(value, dict):
                items.extend(
                    DataTransformer.flatten(value, new_key, separator).items()
                )
            elif isinstance(value, list):
                # Convert lists to indexed keys or JSON string
                if all(isinstance(item, dict) for item in value):
                    for i, item in enumerate(value):
                        items.extend(
                            DataTransformer.flatten(
                                item, f"{new_key}[{i}]", separator
                            ).items()
                        )
                else:
                    items.append((new_key, value))
            else:
                items.append((new_key, value))

        return dict(items)

    @staticmethod
    def to_firestore_batch(
        records: List[Dict[str, Any]],
        doc_prefix: str = "doc"
    ) -> Dict[str, Any]:
        """
        Convert a list of records to Firestore batch import format.

        Args:
            records: List of record dictionaries.
            doc_prefix: Prefix for document IDs.

        Returns:
            Dictionary formatted for Firestore import.

        Example:
            >>> batch = DataTransformer.to_firestore_batch(records)
            >>> # Result: {"doc_0": {...}, "doc_1": {...}, ...}
        """
        return {
            f"{doc_prefix}_{i}": DataTransformer.clean_for_firestore(record)
            for i, record in enumerate(records)
        }

    @staticmethod
    def extract_values(
        data: Dict[str, Any],
        keys: List[str]
    ) -> Dict[str, Any]:
        """
        Extract specific keys from a dictionary.

        Args:
            data: The source dictionary.
            keys: List of keys to extract.

        Returns:
            Dictionary containing only the specified keys.

        Example:
            >>> extracted = DataTransformer.extract_values(
            ...     record, ["title", "status", "created_at"]
            ... )
        """
        return {key: data.get(key) for key in keys if key in data}

    @staticmethod
    def to_json(
        data: Any,
        filename: str,
        indent: int = 2,
        clean: bool = True
    ) -> str:
        """
        Save data to a JSON file.

        Args:
            data: The data to save.
            filename: Path to the output file.
            indent: JSON indentation level.
            clean: If True, clean data for Firestore first.

        Returns:
            The filename of the saved file.

        Example:
            >>> DataTransformer.to_json(records, "output.json")
        """
        if clean:
            data = DataTransformer.clean_for_firestore(data)

        with open(filename, "w") as f:
            json.dump(data, f, indent=indent)

        return filename

    @staticmethod
    def from_json(filename: str) -> Any:
        """
        Load data from a JSON file.

        Args:
            filename: Path to the input file.

        Returns:
            The loaded data.

        Example:
            >>> data = DataTransformer.from_json("input.json")
        """
        with open(filename, "r") as f:
            return json.load(f)
