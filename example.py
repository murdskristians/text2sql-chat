"""
SmartSuite API Client - Usage Examples

This file demonstrates how to use the SmartSuite API client library.
"""
import pdb
import os
from smartsuite import SmartSuiteClient, DataTransformer
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import tqdm

def upload_file(json_file_path, collection_name, data):
    if not firebase_admin._apps:
        cred = credentials.Certificate(os.getenv("FIREBASE_API_KEY"))
        firebase_admin.initialize_app(cred)
    else:
        # Use the existing app
        firebase_admin.get_app()
    db = firestore.client(database_id="smartsuite")
    # 2. Read the JSON file
    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)
    except Exception:
        pass
    # 3. Upload data
    # Check if data is a list (multiple documents) or a single dict
    if isinstance(data, list):
        for record in data:
            db.collection(collection_name).add(record)
    else:
        db.collection(collection_name).add(data)
    
    print(f"Successfully uploaded data to {collection_name}")


def main():
    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    # Option 1: Use environment variables from .env file (recommended)
    client = SmartSuiteClient()

    # Option 2: Pass credentials directly
    # client = SmartSuiteClient(
    #     api_key="your_api_key",
    #     workspace_id="your_workspace_id"
    # )

    # Option 3: Specify a custom .env file path
    # client = SmartSuiteClient(env_file="/path/to/.env")

    print(f"Connected to workspace: {client.workspace_id}")
    print("=" * 60)

    # =========================================================================
    # SOLUTIONS
    # =========================================================================

    print("\n--- SOLUTIONS ---")

    # List all solutions
    solutions = client.solutions.list()
    for sol in solutions:
        print(f"  {sol.name} (ID: {sol.id})")

    # Get a specific solution by ID
    if solutions:
        solution = client.solutions.get(solutions[0].id)
        print(f"\nFirst solution details: {solution.name}")
        print(f"  Description: {solution.description}")

    # Find a solution by name
    # solution = client.solutions.get_by_name("My Solution Name")

    # =========================================================================
    # APPLICATIONS
    # =========================================================================

    print("\n--- APPLICATIONS ---")

    # List all applications
    apps = client.applications.list()
    for app in apps:
        print(f"  {app.name} (ID: {app.id})")

    # List applications in a specific solution
    if solutions:
        apps_in_solution = client.applications.list(solution_id=solutions[0].id)
        print(f"\nApplications in '{solutions[0].name}':")
        for app in apps_in_solution:
            print(f"  - {app.name}")

    # Get a specific application by ID
    if apps:
        app = client.applications.get(apps[0].id)
        print(f"\nApplication '{app.name}' structure:")
        for field in app.fields:
            print(f"  - {field.label} ({field.field_type})")

    # Find an application by name
    # app = client.applications.get_by_name("Products")

    # =========================================================================
    # TABLES AND RECORDS
    # =========================================================================

    print("\n--- TABLES AND RECORDS ---")

    # Get a table by ID
    if apps:
        for app in apps:
            table = client.tables.get(app.id)
            print(f"\nTable: {table.name}")

            # Get table structure/fields
            print("\nFields:")
            for field in table.fields:
                print(f"  - {field['label']} ({field['field_type']})")
            fields_name = [field['slug'] for field in table.fields]
            # List records (with hydration for readable values)
            print("\nRecords (first 5):")
            records = table.records.list(hydrated=True, limit=5)
            for record in records:
                json_record = {k:record[k] for k in fields_name}
                with open("temp.json", 'w') as f:
                    json.dump(json_record, f)
                    try:
                        if table.name == "Materiāls":
                            table_name = "Materials"
                            upload_file('temp.json', table_name, data=json_record)
                    except Exception as e:
                        print(f"Error: {e} ", table.name, record.id)
                # print(f"  Record ID: {record.id}")
                # # Access fields like a dictionary
                # print(f"    Title: {record['title']}")
                # print(f"    Status: {record.get('status', 'N/A')}")

            # Get record count
            total = table.records.count()
            print(f"\nTotal records in table: {total}")

        # Filter records
        # filtered = table.records.filter("status", "eq", "active")

        # Iterate through all records (handles pagination)
        # for record in table.records.all():
        #     print(record.id)

    # Get tables in a solution
    if solutions:
        tables = client.tables.list_in_solution(solutions[0].id)
        print(f"\nTables in solution '{solutions[0].name}':")
        for t in tables:
            print(f"  - {t.name} (ID: {t.id})")

    # =========================================================================
    # DATA TRANSFORMATION
    # =========================================================================

    print("\n--- DATA TRANSFORMATION ---")

    # Example: Clean data for Firestore
    if apps:
        for app in apps:
            table = client.tables.get(app   .id)
            records = table.records.list(limit=20)

            if records:
                # Clean a single record
                cleaned = DataTransformer.clean_for_firestore(records[0].raw_data)
                print(f"\nCleaned record has {len(cleaned)} top-level keys")

                # Simplify record (remove history, links, etc.)
                simplified = DataTransformer.simplify(records[0].raw_data)
                print(f"Simplified record has {len(simplified)} top-level keys")

                # Flatten nested data
                flat = DataTransformer.flatten(records[0].raw_data)
                print(f"Flattened record has {len(flat)} keys")

                # Convert to Firestore batch format
                batch = DataTransformer.to_firestore_batch(
                    [r.raw_data for r in records],
                    doc_prefix="record"
                )
                print(f"Batch contains {len(batch)} documents")

                # Save to JSON file
                # DataTransformer.to_json(batch, "export.json")

    # =========================================================================
    # CHAINING OPERATIONS
    # =========================================================================

    print("\n--- CHAINING EXAMPLE ---")

    # You can chain operations for convenience
    if solutions:
        # Get applications from a solution
        apps = solutions[0].applications
        print(f"Solution '{solutions[0].name}' has {len(apps)} applications")

        # Get tables from a solution
        tables = solutions[0].tables
        print(f"Solution '{solutions[0].name}' has {len(tables)} tables")

        # Access records directly from an application
        if apps:
            table = apps[0].records
            print(f"Application '{apps[0].name}' is ready for record access")

    print("\n" + "=" * 60)
    print("Examples completed!")


if __name__ == "__main__":
    main()
