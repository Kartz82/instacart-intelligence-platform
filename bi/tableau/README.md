# Tableau Public dashboards

Five dashboards over the dbt marts, answering the same business questions as the Power BI
report, published free on Tableau Public.

| Step | Command / file |
| :--- | :--- |
| Export marts to CSV | `python bi/tableau/export_for_tableau.py` → `bi/tableau/data/` (git-ignored) |
| Build the workbook | `TABLEAU_BUILD_GUIDE.md`: data sources, parameters, calculated fields, LOD expressions, layouts |
| Verify | Guide §5: every tile checked against the verified Postgres figures |
| Public link | TODO: verify (paste the Tableau Public URL once published) |
