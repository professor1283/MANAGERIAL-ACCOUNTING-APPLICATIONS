# Northbridge Components MBA Master Budget Simulation

A web-enabled graduate managerial accounting assignment built with Python standard-library tools, SQLite, and an optional Microsoft Dynamics 365 / Dataverse Web API integration layer.

## Included functionality

- Separate professor and student sections, with assignment case information housed in the professor access suite
- AI-generated medium-size manufacturing company and complete budget data
- Quarterly sales, collections, production, direct materials, direct labor, manufacturing overhead, inventory/COGS, and SG&A budgets
- Section A provides student input fields for quarterly budgeted unit sales and automatically calculates annual units and quarterly/annual sales revenue using the selling price per unit
- Supporting cash and line-of-credit financing schedule
- Pro-forma income statement, balance sheet, and indirect statement of cash flows
- Draft saving, weighted automated grading, configurable attempts, and detailed feedback
- Professor assignment-information view, roster-based Student Table, student addition, attempt reset, solution view, and CSV score export
- SQLite relational database, audit log, data dictionary, SQL schema, and budget-cell catalog
- Optional Microsoft Dataverse Web API adapter and table mapping
- Responsive browser interface and Progressive Web App shell

## Launch

### Windows

Double-click `Launch_Budget_Simulation.bat`.

The launcher first uses `runtime/python.exe` when available. If neither a portable runtime nor Python is present, the launcher automatically runs `Prepare_Portable_Runtime.ps1` to download the official Python 3.13.5 embeddable runtime from python.org. This does not install Python into Windows.

### Linux/macOS

Run `./Launch_Budget_Simulation.sh`.

## Access accounts

- Professor login name: `Professor` (or `professor`). The local default password is `3150`; set `BUDGET_SIM_PROFESSOR_PASSWORD` to a private value for hosted use.
- Students: the Student Table is preloaded from the supplied course roster. On first access, a rostered student enters the exact roster name and creates a five-digit numerical password. The same five digits are required on later visits.
- Student passwords are intentionally stored as plain-text five-character digit strings in `student_roster.password`, as configured for this course.

## Web access

- Local computer: `http://127.0.0.1:8080`
- Same network: `http://<server-ip>:8080`
- Internet deployment: host the folder on a Python-capable server, set `BUDGET_SIM_NO_BROWSER=1`, and place it behind HTTPS. On Render, the server automatically honors the platform `PORT` value unless `BUDGET_SIM_PORT` is explicitly set.

## Microsoft Dynamics / Dataverse

The application works immediately with SQLite. `dynamics_adapter.py` implements an optional Dataverse Web API v9.2 client using OAuth bearer tokens. A licensed Dataverse tenant, custom tables, Microsoft Entra registration, and organizational credentials must be supplied by the deploying institution; those cannot be embedded in a downloadable application.

See:

- `docs/dynamics_integration.html`
- `docs/dataverse_table_mapping.csv`
- `docs/data_dictionary.csv`
- `.env.example`

## Important files

- `server.py` — web server, authentication, API, database, grading, instructor controls
- `budget_engine.py` — scenario assumptions, solution calculations, schedules, grading keys
- `dynamics_adapter.py` — optional Dataverse synchronization client
- `docs/schema.sql` — relational schema, including the roster-based `student_roster` table
- `docs/data_dictionary.csv` — field-level data dictionary
- `docs/budget_cell_catalog.csv` — every graded cell and instructor solution
- `data/budget_simulation.db` — created on first launch
