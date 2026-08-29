# Canvas LMS Semester Use

This folder adds Canvas deployment and student-launch materials without changing the Northbridge Components MBA Master Budget Simulation itself.

## Recommended graded-semester configuration

1. Host one class-wide copy of the application on an HTTPS-capable Python host or institutional server.
2. Keep `data/budget_simulation.db` on persistent storage and back it up regularly.
3. Set a private professor password before the database is first created with `BUDGET_SIM_PROFESSOR_PASSWORD`.
4. In Canvas, add the hosted HTTPS application as a Module **External URL** and select **Load in a new tab**. This is the most reliable browser configuration because it avoids third-party-cookie restrictions that can affect framed sites.
5. Create the student accounts in the Professor section and distribute each student's simulation username/password through your normal course process.
6. Use the existing Professor dashboard and `Export Scores CSV` feature for semester grading records.

## Optional embedded Canvas configuration

If the institution specifically wants the application displayed inside a Canvas frame, host the application behind HTTPS and set:

- `BUDGET_SIM_CANVAS_EMBED=1`
- `BUDGET_SIM_SECURE_COOKIES=1`
- `BUDGET_SIM_NO_BROWSER=1`

Canvas embedding can still be affected by browser or institutional third-party-cookie policies. If a student cannot remain signed in inside the frame, use the same hosted URL with Canvas **Load in a new tab** instead.

## Student download option

`Student_Semester_Launcher.html` is a portable student launcher. The first time it is opened, the student enters the instructor-provided HTTPS application URL. The launcher remembers that URL on that computer and opens the live semester simulation in a browser tab. This avoids distributing the server-side solution and grading source code to students.

## Canvas Common Cartridge

`Northbridge_MBA_Budget_Simulation_Canvas_Module.imscc` is a small Canvas-importable Common Cartridge that adds a Start Here module item and the portable student launcher. After import, the instructor should also add the actual hosted simulation URL as an External URL module item.
