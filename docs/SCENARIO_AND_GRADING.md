# Scenario and Grading Design

## Scenario

Northbridge Components, Inc. is an AI-generated, medium-size manufacturer of precision components for industrial automation equipment. The student acts as the corporate budget manager and prepares a quarterly master budget for fiscal year 2027.

The case includes seasonal sales, lagged cash collections, production and inventory policies, direct material purchasing and payment lags, labor standards, variable and fixed overhead, SG&A behavior, capital expenditures, dividends, taxes, a minimum-cash requirement, and a revolving line of credit. The complete case facts and assignment requirements are displayed inside the professor access suite; the student portal opens directly to the budget workspace.

## Required schedules

1. Sales budget
2. Cash collections budget
3. Production budget
4. Direct materials purchases and cash payments budget
5. Direct labor budget
6. Manufacturing overhead budget
7. Inventory and cost of goods sold budget
8. Selling, general, and administrative expense budget
9. Supporting cash and financing schedule
10. Pro-forma income statement
11. Pro-forma balance sheet
12. Pro-forma statement of cash flows

## Grading

The schedules are weighted to 100 total points. Each graded cell within a schedule receives an equal share of that schedule's points. Currency amounts are correct within $1.00; unit and labor-hour amounts are correct within 0.5. The professor can change maximum attempts, passing score, and whether students see cell-level correctness.

| Schedule | Weight |
|---|---:|
| Sales | 5 |
| Cash collections | 8 |
| Production | 8 |
| Direct materials | 12 |
| Direct labor | 7 |
| Manufacturing overhead | 8 |
| Inventory and COGS | 10 |
| SG&A | 7 |
| Cash and financing | 10 |
| Pro-forma income statement | 10 |
| Pro-forma balance sheet | 8 |
| Pro-forma statement of cash flows | 7 |


## Section A automated sales calculation

Students enter budgeted unit sales for Q1 through Q4. The application calculates total annual units and each quarterly and annual budgeted sales revenue amount using `Budgeted Unit Sales × Selling Price per Unit`. Calculated fields are read-only in the browser and are recalculated again by the server before saving or grading.


## Student learning support and grade penalties

The Budget Workspace displays a cumulative grade as the student progresses. The raw cumulative grade is calculated from the same weighted cell-level grading rules used at submission. Blank or incorrect graded cells currently earn zero assignment points, so the displayed cumulative grade rises as correct work is completed. The display also shows completion count and support-tool deductions.

Each schedule provides:

- **Detailed Explanation** - additional conceptual explanation with no grade penalty.
- **Answer Hint / Assistance** - procedural guidance for the schedule. The first use in a schedule is recorded in `student_support_events` and deducts the percentage-point amount configured by the professor who owns the student roster record. Reopening the same section does not create an additional deduction.
- **Check My Work** - can be enabled or disabled independently by each professor and, when enabled, is available once per schedule. It reports which current cells are correct or need review without disclosing expected numerical answers. Its first use is recorded and deducts that professor's configured percentage-point amount.

Penalties are assignment percentage points. For example, a raw score of 90.00 with two recorded penalty points becomes a final adjusted grade of 88.00. The final adjusted grade cannot fall below zero. Support events persist in the Render-hosted SQLite database across browser sessions and redeployments. A professor's **Reset Attempts** action also clears the student's support events so a professor-authorized reset begins with no support penalties.

## Student grade PDF

After a submission, the Results page provides a downloadable PDF grade report for Canvas upload. It includes the student's name, attempt number, submission time, raw assignment score, Assistance count, Check My Work count, total penalty points, final adjusted grade, and schedule-level results.
