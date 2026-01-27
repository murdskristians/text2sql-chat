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

### Project: hotcode-erp
### Dataset: user_stories

---

### Table: offers
Description: Procurement offers data (Latvian and English)
Columns:
- language (STRING): Language code - 'lv' for Latvian, 'en' for English
- offer_name (STRING): Name of the offer/proposal
- description (STRING): Detailed description
- first_created (STRING): Creation timestamp
- last_updated (STRING): Last update timestamp
- followed_by (STRING): Users following this offer
- open_comments (STRING): Number of open comments
- auto_number (STRING): Auto-generated number
- procurement (STRING): Related procurement ID/name
- appendix (STRING): Appendix information
- date (STRING): Date of the offer
- status (STRING): Current status
- revision_count (STRING): Number of revisions
- formula (STRING): Formula field
- company (STRING): Company name
- materials (STRING): Related materials
- projects (STRING): Related projects
- company_contact (STRING): Company contact person
- link_to_companies (STRING): Link to companies
- material_group (STRING): Material group category
- record_id (STRING): Unique record identifier
- status_text (STRING): Status as text
- procurement_completed (STRING): Whether procurement is completed
- buyer (STRING): Buyer information
- contact_person_id (STRING): Contact person ID
- work_material (STRING): Work/material type
- work_material_type (STRING): Work/material type copy
- created_date (STRING): Created date
- created_by_id (STRING): Created by user ID
- created_by_email (STRING): Created by email
- updated_date (STRING): Updated date
- updated_by_id (STRING): Updated by user ID
- updated_by_email (STRING): Updated by email
- source_file (STRING): Source JSON file name

---

### Table: procurement
Description: Procurement data (Latvian and English)
Columns:
- language (STRING): Language code - 'lv' or 'en'
- procurement_name (STRING): Name of the procurement
- description (STRING): Detailed description
- assigned_to (STRING): Assigned person
- status (STRING): Current status
- planned (STRING): Is it planned
- first_created (STRING): Creation timestamp
- last_updated (STRING): Last update timestamp
- code_number (STRING): Code number (Šifrs I)
- project (STRING): Related project
- negotiated (STRING): Negotiated status
- procurement_item (STRING): Item being procured
- code (STRING): Code
- delay_costs_eur_day (STRING): Delay costs in EUR per day
- offer_count (STRING): Number of offers
- boss_call (STRING): Boss call status
- revisions (STRING): Revision information
- reminder (STRING): Reminder
- winner (STRING): Winning offer
- work_material (STRING): Work/material type
- participants (STRING): Participants
- offers (STRING): Related offers
- contract_sum_total (STRING): Total contract sum
- completed (STRING): Completed status
- calendar_month (STRING): Calendar month
- materials (STRING): Related materials
- material_group (STRING): Material group
- year (STRING): Year
- transport_count (STRING): Transport count
- requester (STRING): Person who requested
- status_counter (STRING): Status counter
- year_month (STRING): Year and month combined
- type (STRING): Type
- receiver_requester (STRING): Receiver/Requester
- has_documentation (STRING): Whether has documentation
- tenant (STRING): Tenant
- received (STRING): Received status
- receiver_department (STRING): Receiver department
- delivery_date (STRING): Delivery date
- procurement_receiver (STRING): Procurement receiver
- created_date_text (STRING): Created date as text
- project_type (STRING): Project type
- doc_request_success (STRING): Doc request success
- source_file (STRING): Source JSON file name

---

### Table: materials
Description: Materials catalog data (Latvian and English)
Columns:
- language (STRING): Language code - 'lv' or 'en'
- material_name (STRING): Name of the material
- description (STRING): Detailed description
- first_created (STRING): Creation timestamp
- last_updated (STRING): Last update timestamp
- followed_by (STRING): Users following
- open_comments (STRING): Open comments count
- auto_number (STRING): Auto-generated number
- procurements (STRING): Related procurements
- material_group (STRING): Material group category
- standard_files (STRING): Standard files attached
- procurement_participants (STRING): Procurement participants
- material_group_responsible (STRING): Responsible person for material group
- material_group_industry (STRING): Industry of material group
- standards_status (STRING): Status of standards
- count (STRING): Count
- link_to_companies (STRING): Link to companies
- record_id (STRING): Unique record identifier
- created_date (STRING): Created date
- created_by_id (STRING): Created by user ID
- created_by_email (STRING): Created by email
- updated_date (STRING): Updated date
- updated_by_id (STRING): Updated by user ID
- updated_by_email (STRING): Updated by email
- source_file (STRING): Source JSON file name

---

## Common Query Patterns

1. **Filter by language**:
   `WHERE language = 'en'` for English or `WHERE language = 'lv'` for Latvian

2. **Count records**:
   `SELECT COUNT(*) FROM table_name`

3. **Get distinct values**:
   `SELECT DISTINCT column_name FROM table_name`

4. **Filter by status**:
   `WHERE status = 'active'` or similar

5. **Search text**:
   `WHERE column_name LIKE '%search_term%'`

6. **Date filtering**:
   `WHERE created_date >= '2024-01-01'`
"""

# SQL Query Generation Instructions
SQL_INSTRUCTIONS = """
## SQL Query Generation Rules

1. **Always use fully qualified table names**: `hotcode-erp.user_stories.table_name`
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

User: "Show me all English offers"
SQL: SELECT * FROM `hotcode-erp.user_stories.offers` WHERE language = 'en' LIMIT 100

User: "How many materials do we have?"
SQL: SELECT COUNT(*) as total_materials FROM `hotcode-erp.user_stories.materials`

User: "List procurement items with status completed"
SQL: SELECT procurement_name, status, project FROM `hotcode-erp.user_stories.procurement` WHERE completed = 'true' LIMIT 100

User: "Find offers from company XYZ"
SQL: SELECT * FROM `hotcode-erp.user_stories.offers` WHERE company LIKE '%XYZ%' LIMIT 100
"""


# Sub-agent for schema exploration
schema_explorer_agent = LlmAgent(
    name='Schema_Explorer',
    model='gemini-2.0-flash',
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
    model='gemini-2.0-flash',
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
    name='Text2SQL_Agent',
    model='gemini-2.5-pro',
    description='Intelligent agent that converts natural language to SQL queries and executes them on BigQuery.',
    instruction=f'''You are an intelligent Text-to-SQL agent. Your primary function is to:

1. **Understand** the user's natural language query
2. **Analyze** which tables and columns are relevant
3. **Generate** accurate SQL queries
4. **Execute** the queries using the SQL Executor
5. **Present** results in a clear, user-friendly format

{SCHEMA_KNOWLEDGE}

{SQL_INSTRUCTIONS}

## Your Workflow

1. When a user asks a question:
   - First, understand what data they're looking for
   - If unclear, ask clarifying questions

2. Generate the SQL query:
   - Use the schema knowledge above
   - If you need more schema details, use the Schema Explorer
   - Write clean, efficient SQL

3. Execute and present results:
   - Use the SQL Executor to run the query
   - Format the results nicely for the user
   - If there are many results, summarize key findings
   - If there's an error, explain it and suggest fixes

4. Follow-up:
   - Offer to refine the query if needed
   - Suggest related queries the user might find useful

## Important Guidelines

- Always use fully qualified table names: `hotcode-erp.user_stories.table_name`
- Default to LIMIT 100 unless user specifies otherwise
- For text searches, use LIKE with wildcards
- When filtering by language, default to 'en' unless specified
- Explain your SQL before executing if the query is complex
- If unsure about column names, check the schema first
''',
    sub_agents=[schema_explorer_agent, sql_executor_agent],
    tools=[
        agent_tool.AgentTool(agent=schema_explorer_agent),
        agent_tool.AgentTool(agent=sql_executor_agent),
        get_schema_tool,
        execute_query_tool,
    ],
)
