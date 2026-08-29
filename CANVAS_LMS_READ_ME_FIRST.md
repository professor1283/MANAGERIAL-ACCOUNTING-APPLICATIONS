# Canvas LMS Read Me First

The simulation itself is unchanged. Canvas support has been added as an optional semester deployment layer.

- Instructor setup: `canvas/Canvas_Instructor_Setup_Guide.html`
- Canvas Common Cartridge module: `canvas/Northbridge_MBA_Budget_Simulation_Canvas_Module.imscc`
- Student portable launcher: `canvas/Student_Semester_Launcher.html`
- Semester database backup: `Backup_Semester_Data.bat` or `Backup_Semester_Data.sh`

For a graded semester course, use one centrally hosted HTTPS copy of the simulation and add it to Canvas as an External URL that loads in a new tab. Student drafts and submissions will remain in the central `data/budget_simulation.db` database.
