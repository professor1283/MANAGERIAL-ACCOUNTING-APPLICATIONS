# Canvas LMS Read Me First

The simulation assignment content is unchanged. Canvas support remains an optional semester deployment layer; student authentication now uses the roster-based Student Table.

- Instructor setup: `canvas/Canvas_Instructor_Setup_Guide.html`
- Canvas Common Cartridge module: `canvas/Northbridge_MBA_Budget_Simulation_Canvas_Module.imscc`
- Student portable launcher: `canvas/Student_Semester_Launcher.html`
- Semester database backup: `Backup_Semester_Data.bat` or `Backup_Semester_Data.sh`

For a graded semester course, use one centrally hosted HTTPS copy of the simulation and add it to Canvas as an External URL that loads in a new tab. Student drafts and submissions will remain in the central `data/budget_simulation.db` database.

Student access: rostered students enter their full roster name and create a five-digit numerical password on first access. The same password is used for subsequent access.

### Student password reset for testing/support
An InPrivate/Incognito browser window clears browser cookies but does not clear a five-digit student password already stored in the persistent SQLite database. In the Professor section, use **Student Table → Remove Password** for the selected student when that student must return to true first-time password creation. This leaves saved work, submissions, and attempt history unchanged.

### Professor access
- Existing professor account: **Professor** with its existing configured password.
- Additional professor account: **Professor 1** / **12345**.
- Additional professor account: **Professor 2** / **12345**.

### End-of-semester Student Table clear
After grades and backups are complete, a professor may use **Professor Dashboard → Clear Student Table**. The operation requires explicit confirmation and permanently removes only that professor's student names, passwords, drafts, submissions, scores, and attempt history while preserving professor accounts, assignment content, Canvas access, Render hosting configuration, and GitHub deployment files. The cleared roster remains empty across Render restarts/redeployments.


## Student grading and support tools
The hosted application now displays a cumulative student grade and provides per-section Detailed Explanation, Assistance, and Check My Work controls. Answer Hint / Assistance and Check My Work use the penalty values configured by the professor who owns the student's roster record; Check My Work can also be enabled or disabled by that professor and remains limited to one use per section when enabled. After submission, students can select **Download Grade PDF for Canvas**, save the PDF locally, and upload it to the Canvas assignment. These additions do not change the Render HTTPS address, GitHub deployment workflow, or Canvas External URL configuration.

### Independent professor sections
Professor, Professor 1, and Professor 2 each see only their own Student Table, submissions, exports, and assignment-policy settings. The original supplied roster remains assigned to Professor; the other two professor tables begin empty. Students continue to sign in with only their roster name and five-digit password.
