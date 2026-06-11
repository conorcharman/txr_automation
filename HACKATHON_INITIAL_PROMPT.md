You are a senior software engineer tasked with analysing an existing codebase and producing a detailed, implementation-ready technical plan for a new feature.
Your goal is to fully design the approach before any code is written.

🎯 Feature Overview
We need to build a new feature called:

“Daily Reconciliation”

This feature will:

Query an external SQL database to retrieve a report
Map the result into a Python object model
Persist the data into PostgreSQL
Run validation rules at the column level for each row
Flag errors and optionally suggest fixes per cell
Allow users to manually correct data and approve rows
Display everything in a new UI tab
Export the corrected report as CSV


🧠 Your Objective
You must produce a detailed, structured plan describing:

Architecture
Data modelling (Python + PostgreSQL)
Validation framework
Performance approach
Separation from existing code

Do NOT write full implementation code.
Focus on clear design decisions with rationale.

🧾 Input Report Schema
The SQL query will return a fixed set of columns.
REPSTS, TRADEREF, VENUETXNID, EXENTITYID, FRMDIRIND, SUBMITID,
BUYER_ID, BUYER_BRANCH_COUNTRY, BUYER_FIRST_NAME, BUYER_SURNAME, BUYER_DOB,
BUY_DECISION_MAKER, BUYDECFORE, BUYDEC_SURNAME, BUYDECDOB,
SELLER_ID, SELLER_BRANCH_COUNTRY, SELLER_FIRST_NAME, SELLER_SURNAME, SELLER_DOB,
SELL_DECISION_MAKER, SELLDEC_FIRST_NAME, SELLDEC_SURNAME, SELLDEC_DOB,
TRANSIND, TRANSIDBUY, TRANSIDSEL, TRDDATTIM, TRADING_CAPACITY,
QUANTITY, QUANCUR, DERIVATIVE_NOTIONAL_INCREASE_DECREASE,
PRICE, PRICUR, NETAMT, VENUE, CNTBRCHMEM, INVDECFIRM,
CNTBRCHDEC, EXINFIRM, CNTBRCHEX, SHRTSELIND, OTCPSTIND,
COMDERIND, SECFININD

All rows share the same schema.

🐍 Python Data Model Requirement
You must define a Python representation of a row, including:

Strong typing (dates, numbers, strings where possible)
A structure suitable for:

Validation
Persistence



Also explain:

How SQL results map → Python model
How this model feeds into validation and storage


🗄️ PostgreSQL Schema (CRITICAL REQUIREMENT)
You must design a fully defined SQL schema (DDL).
✅ The schema MUST support:
Per cell (row + column):

Original value
Error flag (is_errored)
Suggested fix (nullable)
Manually corrected value (nullable)

Per row:

Approval status (approved)
Aggregate error state


✅ Design Expectations:

Provide actual SQL CREATE TABLE statements
Include:

Primary keys
Foreign keys
Indexes


Must scale to large datasets
Must be easy to query


✅ Important Constraint:
Even though columns are fixed:

Do NOT create a wide table with one column per field
Instead, treat columns as data entities (e.g., column_name + value)

You must justify your design choice (e.g., normalized vs JSON vs hybrid).

🧩 Validation Framework Design (VERY IMPORTANT)
Validation rules operate as follows:
✅ Model

Each column can have 0–5 validation rules
Rules are defined per column (not per row)
Each rule:

Takes a cell value
Returns:

isValid
optional error message
optional suggested fix






✅ Requirements
Your framework must:

Be extensible (easy to add/remove rules)
Avoid hardcoding rule logic in row processing
Support:

Rule registration per column
Re-running validation safely


Be traceable (which rule failed and why)


⚙️ Performance

Must scale efficiently across all rows
Must support parallelism where possible
Avoid:

Sequential per-cell validation loops


Prefer:

Batch processing
Precompiled column → rules mapping




🧱 Separation of Concerns (IMPORTANT)
This feature must be cleanly isolated from the rest of the system.
Your plan must:

Introduce a separate module/service boundary (e.g. reconciliation domain)
Avoid tight coupling with existing reporting logic
Use independent:

Database tables
Services
Validation framework




🖥️ UI Requirements
Add a new tab:

Daily Reconciliation

The UI must:

Display a table of rows
Highlight:

Cells with errors
Rows with errors


Show suggested fixes inline
Allow:

Accepting suggested fixes
Manual edits


Allow marking rows as:

✅ Approved




📤 CSV Export

Export corrected data as CSV
Use:

Corrected values (if present)
Otherwise suggested/original values


Only include:

Final approved data




🔄 Data Flow (Must Be Defined Clearly)
You must describe this pipeline:
External SQL → Python Object → Validation → PostgreSQL → UI → CSV Export

Include how:

Column names remain consistent across all layers
Data transformations occur


⚡ Performance Requirements
Your design must:

Handle large datasets efficiently
Avoid N+1 queries
Use:

Batch inserts/updates
Efficient indexing
Parallel validation strategies




🧩 Deliverables
Structure your response as:
1. High-Level Architecture
2. Python Data Model
3. ✅ PostgreSQL Schema (Full SQL DDL)
4. Backend Design
5. ✅ Validation Framework Design
6. Frontend Plan
7. CSV Export Strategy
8. Performance Strategy
9. Edge Cases & Risks
10. Incremental Delivery Plan

⚠️ Constraints

Production-grade design
Scalable and maintainable
Prefer clarity over cleverness
Avoid over-engineering


✅ Output Style

Use headings and bullet points
Be precise and practical
Justify major design decisions


✅ Important Mindset
Design this as if it will be:

Reviewed by senior engineers
Implemented by a team
Scaled in production