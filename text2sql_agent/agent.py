"""
Text-to-SQL Agent using Google ADK.

This agent converts natural language queries to SQL, executes them on BigQuery,
and returns the results in a user-friendly format.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool

from .bigquery_tools import (
    get_schema_tool,
    list_tables_tool,
    execute_query_tool,
    get_sample_tool,
    get_stats_tool,
)

# Schema information for the agent's knowledge
SCHEMA_KNOWLEDGE = """
## Available BigQuery Tables

### Project: smartsuitebigqueryproject
### Dataset: smartsuite_demo

Reltek's procurement demo warehouse. Five related tables covering tenders,
the offers suppliers submit against them, the materials being bought, the
employees involved, and the transports that deliver them.

Relationships:
- offers.tender_id     -> tenders.tender_id
- offers.material_id   -> materials.material_id
- tenders.material_id  -> materials.material_id
- tenders.requester_id -> employees.employee_id
- tenders.buyer_id     -> employees.employee_id
- transports.tender_id -> tenders.tender_id
- transports.assigned_to_id -> employees.employee_id
- materials.responsible_employee_id -> employees.employee_id

---

### Table: offers
Description: Supplier offers submitted against a tender. ~14,400 rows.
Columns:
- offer_id (STRING): Unique offer identifier
- tender_id (STRING): Tender this offer answers
- material_id (STRING): Material being offered
- supplier_name (STRING): Supplier company name
- supplier_contact (STRING): Supplier contact person
- price_eur (FLOAT): Offered price in EUR
- currency (STRING): Currency code
- status (STRING): One of 'Won', 'Rejected', 'Submitted', 'Under Review'
- is_winner (BOOLEAN): TRUE if this offer won the tender
- revision_count (INTEGER): Number of revisions
- valid_until (DATE): Offer expiry date
- submitted_at (TIMESTAMP): When the offer was submitted

---

### Table: tenders
Description: Procurement tenders raised by Reltek. ~5,000 rows.
Columns:
- tender_id (STRING): Unique tender identifier
- tender_name (STRING): Name of the tender
- material_id (STRING): Material being procured
- project_code (STRING): Project the tender belongs to
- project_type (STRING): Type of project
- requester_id (STRING): Employee who requested it
- buyer_id (STRING): Employee responsible for buying
- department (STRING): One of 'Quality Assurance', 'Site Operations',
  'Logistics', 'Procurement', 'Design', 'Finance', 'Engineering'
- status (STRING): One of 'Delivered', 'Awarded', 'Open', 'In Review',
  'Cancelled', 'Draft'
- quantity (FLOAT): Quantity required
- unit (STRING): Unit of measure
- contract_total_eur (FLOAT): Total contract value in EUR
- savings_eur (FLOAT): Savings achieved in EUR
- offer_count (INTEGER): Number of offers received
- created_date (DATE): When the tender was created
- planned_delivery_date (DATE): Planned delivery date
- actual_delivery_date (DATE): Actual delivery date
- delivered (BOOLEAN): TRUE once delivered
- delay_days (INTEGER): Days late (negative means early)
- year (INTEGER): Year of creation
- month (INTEGER): Month of creation
- description (STRING): Free-text description

---

### Table: materials
Description: Catalogue of materials Reltek procures.
Columns:
- material_id (STRING): Unique material identifier
- material_name (STRING): Name of the material
- material_group (STRING): One of 'Glazing', 'Finishes', 'Plumbing', 'Steel',
  'Insulation', 'Concrete', 'Electrical', 'Timber'
- industry_sector (STRING): Industry sector
- unit (STRING): Unit of measure
- standard_code (STRING): Standard/norm code
- standard_status (STRING): Status of the standard
- responsible_employee_id (STRING): Employee responsible
- description (STRING): Free-text description
- is_active (BOOLEAN): TRUE if still in the catalogue
- created_at (TIMESTAMP): Creation timestamp
- updated_at (TIMESTAMP): Last update timestamp

---

### Table: employees
Description: Reltek staff involved in procurement. 45 rows.
Columns:
- employee_id (STRING): Unique employee identifier
- full_name (STRING): Employee full name
- email (STRING): Reltek email address
- department (STRING): Department name
- title (STRING): Job title
- office_location (STRING): Office location
- status (STRING): Employment status
- hired_date (DATE): Date hired

---

### Table: transports
Description: Deliveries linked to tenders.
Columns:
- transport_id (STRING): Unique transport identifier
- tender_id (STRING): Tender being delivered against
- route_from (STRING): Origin
- route_to (STRING): Destination
- cargo_description (STRING): What is being carried
- weight_kg (FLOAT): Cargo weight in kilograms
- transport_group (STRING): Transport category
- carrier_name (STRING): Carrier company
- status (STRING): One of 'Delivered', 'Scheduled', 'Requested',
  'In Transit', 'Cancelled'
- cost_eur (FLOAT): Transport cost in EUR
- assigned_to_id (STRING): Employee coordinating it
- ready_at (TIMESTAMP): When cargo was ready
- requested_delivery_date (TIMESTAMP): Requested delivery
- confirmed_delivery_date (TIMESTAMP): Confirmed delivery

---

## Common Query Patterns

1. **Winning offers**:
   `WHERE is_winner = TRUE` (a BOOLEAN, not the string 'true')

2. **Count records**:
   `SELECT COUNT(*) FROM table_name`

3. **Get distinct values**:
   `SELECT DISTINCT column_name FROM table_name`

4. **Filter by status**:
   `WHERE status = 'Won'` - status values are capitalised

5. **Search text**:
   `WHERE column_name LIKE '%search_term%'`

6. **Date filtering**:
   `WHERE created_date >= '2024-01-01'` - created_date is a real DATE

7. **Money and aggregation**:
   price_eur, contract_total_eur, savings_eur and cost_eur are FLOAT, so
   SUM/AVG work directly without casting.

8. **Joining offers to tenders**:
   `JOIN ... ON offers.tender_id = tenders.tender_id`
"""

# SQL Query Generation Instructions
SQL_INSTRUCTIONS = """
## SQL Query Generation Rules

1. **Always use fully qualified table names**: `smartsuitebigqueryproject.smartsuite_demo.table_name`
2. **Use backticks** for table and column names with special characters
3. **Limit results** to avoid large data transfers - use LIMIT clause
4. **Only SELECT queries** are allowed - no modifications
5. **Handle NULL values** appropriately in conditions
6. **Use appropriate aggregations** (COUNT, SUM, AVG, etc.) when needed
7. **Join tables** when the query requires data from multiple sources

## Query Building Process

1. Understand the user's intent from their natural language query
2. Identify which table(s) contain the relevant data
3. Determine the columns needed
4. Apply appropriate filters and conditions
5. Add sorting if relevant
6. Limit results to a reasonable number

## Example Translations

User: "Show me 5 offers"
SQL: SELECT * FROM `smartsuitebigqueryproject.smartsuite_demo.offers` LIMIT 5

User: "How many materials do we have?"
SQL: SELECT COUNT(*) as total_materials FROM `smartsuitebigqueryproject.smartsuite_demo.materials`

User: "List tenders that were delivered late"
SQL: SELECT tender_name, department, delay_days FROM `smartsuitebigqueryproject.smartsuite_demo.tenders` WHERE delay_days > 0 ORDER BY delay_days DESC LIMIT 100

User: "Find offers from Northwind Steel"
SQL: SELECT * FROM `smartsuitebigqueryproject.smartsuite_demo.offers` WHERE supplier_name LIKE '%Northwind%' LIMIT 100

User: "Which supplier won the most tenders?"
SQL: SELECT supplier_name, COUNT(*) AS wins FROM `smartsuitebigqueryproject.smartsuite_demo.offers` WHERE is_winner = TRUE GROUP BY supplier_name ORDER BY wins DESC LIMIT 10

User: "Total savings by department"
SQL: SELECT department, SUM(savings_eur) AS total_savings FROM `smartsuitebigqueryproject.smartsuite_demo.tenders` GROUP BY department ORDER BY total_savings DESC
"""


# Sub-agent for schema exploration
schema_explorer_agent = LlmAgent(
    name='Schema_Explorer',
    model='gemini-2.5-flash',
    description='Agent specialized in exploring BigQuery table schemas and data structure.',
    instruction='''You are a schema exploration specialist. Your job is to:
1. List available tables when asked
2. Fetch and explain table schemas
3. Get sample data to understand data formats
4. Provide column statistics when needed

Use the available tools to gather schema information and help the main agent understand the data structure.''',
    tools=[
        get_schema_tool,
        list_tables_tool,
        get_sample_tool,
        get_stats_tool,
    ],
)

# Sub-agent for SQL execution
sql_executor_agent = LlmAgent(
    name='SQL_Executor',
    model='gemini-2.5-flash',
    description='Agent specialized in executing SQL queries on BigQuery.',
    instruction='''You are a SQL execution specialist. Your job is to:
1. Execute SQL queries provided by the main agent
2. Return results in a clear, formatted way
3. Handle errors gracefully and provide helpful error messages
4. Suggest query optimizations if needed

Only execute SELECT queries for safety. Report any errors clearly.''',
    tools=[
        execute_query_tool,
    ],
)

# Main Text-to-SQL Agent
root_agent = LlmAgent(
    name='Reltek_Data_Assistant',
    model='gemini-2.5-pro',
    description="Reltek's procurement data assistant - converts natural language to SQL and runs it on BigQuery.",
    instruction=f'''You are the Reltek data assistant. Reltek is a construction
and procurement company; you answer questions about its tenders, supplier
offers, materials, staff and deliveries. Your primary function is to:

1. **Understand** the user's natural language query
2. **Analyze** which tables and columns are relevant
3. **Generate** accurate SQL queries
4. **Execute** the queries with `execute_sql_query`
5. **Present** results in a clear, user-friendly format

{SCHEMA_KNOWLEDGE}

{SQL_INSTRUCTIONS}

## Your Workflow

1. When a user asks a question:
   - First, understand what data they're looking for
   - If unclear, ask clarifying questions

2. Generate the SQL query:
   - Use the schema knowledge above
   - If you need more schema details, call `get_table_schema`
   - Write clean, efficient SQL

3. Execute and present results:
   - Call `execute_sql_query` to run the query
   - Format the results nicely for the user
   - If there are many results, summarize key findings
   - If there's an error, explain it and suggest fixes

4. Follow-up:
   - Offer to refine the query if needed
   - Suggest related queries the user might find useful

## Available Tools

Call tools by these exact names. Never prefix a tool with an agent name
(`SQL_Executor.execute_sql_query` is not a tool and will fail):

- `execute_sql_query(query, max_results)` - run a SELECT query on BigQuery
- `get_table_schema(project_id, dataset_id, table_id)` - inspect a table's columns
- `Schema_Explorer(request)` - delegate deeper schema exploration
- `SQL_Executor(request)` - delegate query execution

Prefer `execute_sql_query` and `get_table_schema` directly; they do the work in
one step.

## Important Guidelines

- Always use fully qualified table names: `smartsuitebigqueryproject.smartsuite_demo.table_name`
- Default to LIMIT 100 unless user specifies otherwise
- For text searches, use LIKE with wildcards
- Booleans (is_winner, delivered, is_active) are real BOOLEANs - compare to
  TRUE/FALSE, never to the strings 'true'/'false'
- Explain your SQL before executing if the query is complex
- If unsure about column names, check the schema first
''',
    # Registered as AgentTools only. Listing them as sub_agents too exposed the
    # same agents through two mechanisms and led the model to invent namespaced
    # calls like `SQL_Executor.execute_sql_query`.
    tools=[
        agent_tool.AgentTool(agent=schema_explorer_agent),
        agent_tool.AgentTool(agent=sql_executor_agent),
        get_schema_tool,
        execute_query_tool,
    ],
)
