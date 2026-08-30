# Northbridge Components MBA Master Budget Simulation

A web-enabled graduate managerial accounting assignment built with Python standard-library tools, SQLite, and an optional Microsoft Dynamics 365 / Dataverse Web API integration layer.

## Included functionality

- Separate professor and student sections, with assignment case information housed in the professor access suite
- AI-generated medium-size manufacturing company and complete budget data
- Quarterly sales, collections, production, direct materials, direct labor, manufacturing overhead, inventory/COGS, and SG&A budgets
- Section A provides student input fields for quarterly budgeted unit sales and automatically calculates annual units and quarterly/annual sales revenue using the selling price per unit
- Supporting cash and line-of-credit financing schedule
- Pro-forma income statement, balance sheet, and indirect statement of cash flows
- Draft saving, weighted automated grading, configurable attempts, detailed feedback, live cumulative grade display, and downloadable student grade PDFs for Canvas upload
- Per-section student learning support: free Detailed Explanation plus professor-configurable Answer Hint / Assistance and one-use-per-section Check My Work penalties
- Three professor-isolated Student Tables, professor-specific assignment policies, student addition, attempt reset, password removal, end-of-semester Student Table clear, solution view, and CSV score export
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

- Professor access: `Professor` uses the existing password (local default `3150`, or `BUDGET_SIM_PROFESSOR_PASSWORD` for hosted use). Two additional professor accounts are `Professor 1` / `12345` and `Professor 2` / `12345`.
- Students: the original Professor Student Table is preloaded from the supplied course roster; Professor 1 and Professor 2 begin with independent empty Student Tables. On first access, a rostered student enters the exact roster name and creates a five-digit numerical password. The same five digits are required on later visits.
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

### Student password reset for testing/support
An InPrivate/Incognito browser window clears browser cookies but does not clear a five-digit student password already stored in the persistent SQLite database. In the Professor section, use **Student Table → Remove Password** for the selected student when that student must return to true first-time password creation. This leaves saved work, submissions, and attempt history unchanged.

### End-of-semester Student Table clear
Inside the protected Professor dashboard, **Clear Student Table** permanently removes only the currently signed-in professor's student accounts, student-created passwords, drafts, submissions, scores, and attempt history after a two-stage confirmation. The other professors' Student Tables are not changed. Professor accounts, scenario/assignment data, Canvas launch resources, Render configuration, and GitHub deployment files remain intact. The initial supplied roster is seeded only once; after an intentional clear, it stays empty across Render restarts and redeployments until a professor adds new students or a future application revision supplies a new roster workflow.


### Student support, cumulative grade, and Canvas grade PDF
Each budget section includes three student tools. **Detailed Explanation** provides additional conceptual explanation without a grade penalty. **Answer Hint / Assistance** provides procedural guidance and records the owning professor's configured percentage-point deduction the first time it is used in that section; reopening the same section does not create another deduction. **Check My Work** may be enabled or disabled by the owning professor, may be used only once per section when enabled, and records that professor's configured percentage-point deduction. It identifies which current cells are correct or need review without displaying the correct numerical answers.

The Budget Workspace continuously displays the student's current cumulative score out of 100 assignment points, the raw score before penalties, total recorded penalty points, and graded-cell completion count. At submission, `submissions.raw_score` stores the score before penalties, `submissions.penalty_points` stores the deductions, and `submissions.score` stores the final adjusted grade.

After a graded submission, the Results page includes **Download Grade PDF for Canvas**. The server generates a PDF containing the student name, attempt, raw score, support-tool penalty summary, final adjusted grade, and section scores. The browser downloads the file so the student can save it and upload it to the appropriate Canvas assignment.


### Professor-specific Student Tables and settings
Each professor account owns an independent Student Table through `student_roster.professor_user_id`. Student additions, resets, password removals, score exports, submission views, and end-of-semester clears are restricted to the signed-in professor. `professor_settings` stores independent values for maximum attempts, passing score, feedback visibility, Check My Work availability, Check My Work penalty points, and Answer Hint / Assistance penalty points. Existing students from earlier versions migrate to the original Professor table. Student names remain globally unique so student login stays unchanged.
