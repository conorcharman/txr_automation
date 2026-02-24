# SQL Extract Template v2.3 — Agent Instructions

## Overview

This template is used to extract child/parent contract records from CRSNET for Non-Zero Net Quantity (7_6) accuracy testing.

Given a list of transaction references (12-character strings, e.g. `44625CMGKHP1`), the agent must:

1. Filter out any references beginning with `CA`
2. Split each remaining reference into its five component fields
3. Insert the resulting rows into the `{VALUES}` placeholder in the template below

---

## Splitting a Transaction Reference

Each reference is exactly 12 characters. Split as follows:

| Field    | Chars  | Length | Example (`44625CMGKHP1`) |
|----------|--------|--------|--------------------------|
| `k_firm` | 1–3    | 3      | `446`                    |
| `k_year` | 4–5    | 2      | `25`                     |
| `k_accl` | 6      | 1      | `C`                      |
| `k_cont` | 7–11   | 5      | `MGKHP`                  |
| `k_suff` | 12     | 1      | `1`                      |

---

## VALUES Block Format

Each reference becomes one row. Rows are comma-separated. The last row has no trailing comma.

```
        ('446','25','C','MGKHP','1'),
        ('446','25','C','MGKFD','1'),
        ('446','25','C','MGKF9','1')
```

---

## SQL Template

Replace `{VALUES}` with the formatted rows described above.

```sql
WITH target_keys (k_firm, k_year, k_accl, k_cont, k_suff) AS (
    VALUES
{VALUES}
),
target_parent AS (
    SELECT
        n.NTFIRM,
        n.NTYEAR,
        n.NTACCL,
        n.NTCONT,
        n.NTSUFF
    FROM CRSNET n
    INNER JOIN target_keys k
        ON  n.GRFIRM = k.k_firm
        AND n.GRYEAR = k.k_year
        AND n.GRACCL = k.k_accl
        AND n.GRCONT = k.k_cont
        AND n.GRSUFF = k.k_suff
    WHERE n.STATUS = 'A'
),
children AS (
    SELECT
        c.GRFIRM,
        c.GRYEAR,
        c.GRACCL,
        c.GRCONT,
        c.GRSUFF,
        c.NTFIRM,
        c.NTYEAR,
        c.NTACCL,
        c.NTCONT,
        c.GRFIRM||c.GRYEAR||c.GRACCL||c.GRCONT||c.GRSUFF AS child_ref,
        c.NTFIRM||c.NTYEAR||c.NTACCL||c.NTCONT||c.NTSUFF  AS parent_ref
    FROM CRSNET c
    INNER JOIN target_parent tp
        ON  c.NTFIRM = tp.NTFIRM
        AND c.NTYEAR = tp.NTYEAR
        AND c.NTACCL = tp.NTACCL
        AND c.NTCONT = tp.NTCONT
        AND c.NTSUFF = tp.NTSUFF
    WHERE c.STATUS = 'A'
)
SELECT
    c.child_ref,
    co.QUAN15  AS child_qty,
    c.parent_ref,
    po.QUAN15  AS parent_qty,
    t1.TXNREPSTS  AS report_status,
    t2.TRDDATTIM  AS trade_date_time
FROM children c
LEFT JOIN ORDER co
    ON  c.GRFIRM = co.FRMCOD
    AND c.GRYEAR = co.YEAR
    AND c.GRACCL = co.ACCLTR
    AND c.GRCONT = co.CONTNO
LEFT JOIN ORDER po
    ON  c.NTFIRM = po.FRMCOD
    AND c.NTYEAR = po.YEAR
    AND c.NTACCL = po.ACCLTR
    AND c.NTCONT = po.CONTNO
LEFT JOIN TXNREP t1
    ON c.child_ref = t1.reportref
LEFT JOIN TXNREPESMA t2
    ON c.child_ref = t2.reportref
ORDER BY
    t2.TRDDATTIM ASC
```

---

## Notes

- This runs on **IBM DB2 for i** via the IBM System i Data Transfer tool
- `SYSIBM.SYSDUMMY1` is **not** used in this template — the `VALUES` table constructor is used instead, which avoids the DB2 for i limit of 256 subselects (SQL0101 reason code 4)
- References beginning with `CA` must be **excluded** — they use a different field schema and are not supported by this template
- The `STATUS = 'A'` filter is applied in `target_parent` to restrict CRSNET to active records only
- `ORDER` is a reserved word in some SQL dialects — if the extract tool requires it to be quoted or schema-qualified, adjust `LEFT JOIN ORDER` accordingly
