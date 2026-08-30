# Canvas LMS Semester Use

This folder adds Canvas deployment and student-launch materials. Assignment content is unchanged; student access uses the roster-based Student Table.

## Recommended graded-semester configuration

1. Host one class-wide copy of the application on an HTTPS-capable Python host or institutional server.
2. Keep `data/budget_simulation.db` on persistent storage and back it up regularly.
3. Set a private professor password before the database is first created with `BUDGET_SIM_PROFESSOR_PASSWORD`.
4. In Canvas, add the hosted HTTPS application as a Module **External URL** and select **Load in a new tab**. This is the most reliable browser configuration because it avoids third-party-cookie restrictions that can affect framed sites.
5. Confirm the preloaded Student Table in the original Professor section. Professor 1 and Professor 2 maintain independent Student Tables and begin empty. On first access, each rostered student enters the exact roster name and creates a five-digit numerical password; the same password is used thereafter.
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

Professor access also includes **Professor 1 / 12345** and **Professor 2 / 12345**. At semester end, the protected Professor dashboard provides **Clear Student Table**; it removes only the signed-in professor's students and leaves the other professor tables plus Canvas/Render/GitHub deployment intact.


## Student grade-document workflow
After a graded submission, students can download a server-generated PDF grade report from the Results page and upload that PDF to the corresponding Canvas assignment. The public Render HTTPS address and Canvas External URL workflow are unchanged.

## Professor-specific policies
Each professor independently controls maximum attempts, Check My Work availability, Check My Work penalty points, and Answer Hint / Assistance penalty points for students in that professor's Student Table. Changes do not alter the other two professors' settings.
