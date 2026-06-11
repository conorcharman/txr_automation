# Daily Reconciliation — Adding Validation Rules

This document explains how the validation framework works and how to add new rules
that will flag cells in the Daily Reconciliation UI.

---

## How It Works (Overview)

When a reconciliation run is triggered, the pipeline is:

```
SQL Extract (FIGARO_CL)
        ↓
  validate_batch()          ← your rules fire here
        ↓
  Persist to PostgreSQL     ← issues stored per cell
        ↓
  React UI                  ← errors shown per row / cell
```

The validation layer lives entirely in:

```
api/daily_recon/validation/
├── base.py       # Rule protocol + RuleResult dataclass
├── registry.py   # RuleRegistry singleton
├── rules.py      # All built-in rules + column registrations  ← edit this
└── engine.py     # validate_batch() — calls registry, collects issues
```

The **only file you normally need to edit** is `rules.py`.

---

## Key Concepts

### `RuleResult`

Every rule returns a `RuleResult`:

```python
@dataclass
class RuleResult:
    is_valid: bool
    message: str | None = None          # shown in the UI error panel
    suggested_fix: str | None = None    # shown as "Suggested Fix" in the UI
```

### `Rule` Protocol

A rule is any class that has:

- `rule_id: str` — unique identifier shown in the UI (e.g. `"not_empty"`)
- `validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult`
  - `value` — the raw string value of the cell being validated
  - `record` — the **entire row** as a string dict (use this for cross-field rules)

### `rule_registry`

A module-level singleton. Rules are registered against one or more column names.
The registry is **frozen** at the end of `rules.py` — no further registration is
possible after module load. All registrations must happen in `rules.py` before the
`rule_registry.freeze()` call at the bottom.

### Column Names

All 50 column names are defined in `api/daily_recon/columns.py`. Use the exact
`COLUMN_NAMES` constants when registering rules. Helpful groupings are also defined
there: `ID_COLUMNS`, `DATE_COLUMNS`, `NUMERIC_COLUMNS`, `INDICATOR_COLUMNS`,
`COUNTRY_CODE_COLUMNS`.

---

## Step-by-Step: Adding a Rule

### Step 1 — Open `api/daily_recon/validation/rules.py`

All work happens in this one file.

### Step 2 — Write your rule class

Add it in a logical section (or create a new section with a divider comment).
The class needs `rule_id` and `validate()`. That's it.

**Example: require `TRADEREF` to start with a specific prefix**

```python
class TradeRefPrefixRule:
    """Rule: TRADEREF must start with 'TXR-'."""

    rule_id = "trade_ref_prefix"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check TRADEREF starts with TXR-."""
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)  # let not_empty handle blanks separately
        if not value.strip().startswith("TXR-"):
            return RuleResult(
                is_valid=False,
                message=f"Trade reference must begin with 'TXR-', got: {value}",
                suggested_fix=f"TXR-{value.strip()}",
            )
        return RuleResult(is_valid=True)
```

**Example: cross-field rule — quantity must be positive if TRANSIND is 'Y'**

```python
class QuantityPositiveIfTransactionRule:
    """Rule: QUANTITY must be > 0 when TRANSIND is Y."""

    rule_id = "quantity_positive_if_transaction"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check QUANTITY when TRANSIND = Y."""
        if record.get("TRANSIND", "").strip().upper() != "Y":
            return RuleResult(is_valid=True)  # rule only applies when TRANSIND = Y
        if value is None or value.strip() == "":
            return RuleResult(
                is_valid=False,
                message="QUANTITY cannot be empty when TRANSIND is Y.",
            )
        try:
            from decimal import Decimal
            if Decimal(value.strip()) <= 0:
                return RuleResult(
                    is_valid=False,
                    message=f"QUANTITY must be positive when TRANSIND is Y, got: {value}",
                )
        except Exception:
            return RuleResult(is_valid=False, message=f"QUANTITY is not a valid number: {value}")
        return RuleResult(is_valid=True)
```

### Step 3 — Instantiate and register your rule

Scroll to the bottom of `rules.py` — just **before** the `rule_registry.freeze()` call.
Create an instance and register it:

```python
# --- Add before rule_registry.freeze() ---

_trade_ref_prefix = TradeRefPrefixRule()
rule_registry.register("TRADEREF")(_trade_ref_prefix)

_qty_positive_if_transaction = QuantityPositiveIfTransactionRule()
rule_registry.register("QUANTITY")(_qty_positive_if_transaction)

# Freeze the registry at module load (no more rule registration allowed)
rule_registry.freeze()
```

To register the **same rule against multiple columns** in one call:

```python
rule_registry.register("BUYER_FIRST_NAME", "SELLER_FIRST_NAME", "BUYER_SURNAME", "SELLER_SURNAME")(
    NotEmptyRule()
)
```

### Step 4 — Trigger a new run

No restart is needed (the module is re-imported per Celery task). Click
**Run Query Now** in the UI, or POST to `/api/daily-recon/runs/trigger`.
Your rule will fire on the next run, and any failures will appear in the
cell detail panel.

---

## Already-Registered Rules Reference

The following rules are live today:

| Rule class | `rule_id` | Columns registered against |
|---|---|---|
| `IdNotEmptyRule` | `id_not_empty` | `BUYER_ID`, `SELLER_ID`, `EXENTITYID` |
| `IdFormatRule` | `id_format` | `BUYER_ID`, `SELLER_ID`, `EXENTITYID` |
| `CountryCodeRule` | `country_code_valid` | `BUYER_BRANCH_COUNTRY`, `SELLER_BRANCH_COUNTRY` |
| `NumericRule` | `numeric` | `QUANTITY`, `DERIVATIVE_NOTIONAL_INCREASE_DECREASE`, `PRICE`, `NETAMT` |
| `PositiveNumberRule` | `positive_number` | `QUANTITY`, `DERIVATIVE_NOTIONAL_INCREASE_DECREASE` |
| `DateFormatRule` | `date_format` | `BUYER_DOB`, `SELLER_DOB`, `BUYDECDOB`, `SELLDEC_DOB` |
| `ReasonableDateRule` | `reasonable_date` | `BUYER_DOB`, `SELLER_DOB`, `BUYDECDOB`, `SELLDEC_DOB` |
| `IndicatorRule` | `indicator_valid` | `FRMDIRIND`, `TRANSIND`, `SHRTSELIND`, `OTCPSTIND`, `COMDERIND`, `SECFININD` |

**Note:** `NotEmptyRule`, `MaxLengthRule`, and `RegexRule` are defined but not yet
registered against any columns — they are ready to be wired up.

---

## All 50 Column Names (for Reference)

These are the exact names to use when calling `rule_registry.register(...)`:

| Group | Column names |
|---|---|
| Transaction header | `REPSTS`, `TRADEREF`, `VENUETXNID`, `EXENTITYID`, `FRMDIRIND`, `SUBMITID` |
| Buyer identity | `BUYER_ID`, `BUYER_BRANCH_COUNTRY`, `BUYER_FIRST_NAME`, `BUYER_SURNAME`, `BUYER_DOB` |
| Buyer decision maker | `BUY_DECISION_MAKER`, `BUYDECFORE`, `BUYDEC_SURNAME`, `BUYDECDOB` |
| Seller identity | `SELLER_ID`, `SELLER_BRANCH_COUNTRY`, `SELLER_FIRST_NAME`, `SELLER_SURNAME`, `SELLER_DOB` |
| Seller decision maker | `SELL_DECISION_MAKER`, `SELLDEC_FIRST_NAME`, `SELLDEC_SURNAME`, `SELLDEC_DOB` |
| Transaction indicators | `TRANSIND`, `TRANSIDBUY`, `TRANSIDSEL`, `TRDDATTIM`, `TRADING_CAPACITY` |
| Quantity & pricing | `QUANTITY`, `QUANCUR`, `DERIVATIVE_NOTIONAL_INCREASE_DECREASE`, `PRICE`, `PRICUR`, `NETAMT` |
| Venue & routing | `VENUE`, `CNTBRCHMEM`, `INVDECFIRM`, `CNTBRCHDEC`, `EXINFIRM`, `CNTBRCHEX` |
| Indicators | `SHRTSELIND`, `OTCPSTIND`, `COMDERIND`, `SECFININD` |

---

## Useful Patterns

### Allow blank but validate if present

```python
def validate(self, value, record):
    if value is None or value.strip() == "":
        return RuleResult(is_valid=True)  # blank is OK; add NotEmptyRule separately
    # ... your logic
```

### Provide a suggested fix

Populate `suggested_fix` to give the reviewer a one-click correction in the UI:

```python
return RuleResult(
    is_valid=False,
    message="Value must be uppercase.",
    suggested_fix=value.strip().upper(),
)
```

### Parameterised rules (reusable across columns)

Use `__init__` to make a rule configurable:

```python
class AllowedValuesRule:
    """Rule: value must be one of an allowed set."""

    rule_id = "allowed_values"

    def __init__(self, allowed: set[str], case_sensitive: bool = False):
        self.allowed = allowed if case_sensitive else {v.upper() for v in allowed}
        self.case_sensitive = case_sensitive

    def validate(self, value, record):
        if value is None or value.strip() == "":
            return RuleResult(is_valid=True)
        check = value.strip() if self.case_sensitive else value.strip().upper()
        if check not in self.allowed:
            return RuleResult(
                is_valid=False,
                message=f"'{value}' is not an allowed value. Expected one of: {sorted(self.allowed)}",
            )
        return RuleResult(is_valid=True)
```

Register separate instances for different columns:

```python
_trading_capacity = AllowedValuesRule({"DEAL", "MATCHED_PRINCIPAL", "ANY_OTHER"})
rule_registry.register("TRADING_CAPACITY")(_trading_capacity)

_repsts = AllowedValuesRule({"NEWT", "MODI", "CANC", "VALU", "CORR", "EROR"})
rule_registry.register("REPSTS")(_repsts)
```

---

## Testing Your Rule

Run the existing test suite after adding a rule to confirm nothing regresses:

```powershell
conda activate txr_automation
pytest tests/ -k "daily_recon" -v
```

Write a focused unit test alongside your rule:

```python
# tests/test_api/test_daily_recon_rules.py

from api.daily_recon.validation.rules import TradeRefPrefixRule


def test_trade_ref_prefix_valid():
    rule = TradeRefPrefixRule()
    result = rule.validate("TXR-00123", {})
    assert result.is_valid


def test_trade_ref_prefix_invalid():
    rule = TradeRefPrefixRule()
    result = rule.validate("00123", {})
    assert not result.is_valid
    assert result.suggested_fix == "TXR-00123"


def test_trade_ref_prefix_blank_passes():
    rule = TradeRefPrefixRule()
    result = rule.validate("", {})
    assert result.is_valid  # blank allowed; not_empty is a separate rule
```

---

## Where Issues Appear in the UI

Once a rule fires, the issue is stored in the `daily_recon_cell_issue` table and
surfaced in the React frontend:

- **Row list** — rows with any errored cell show a red "N errors" badge
- **Cell grid** — the specific cell is highlighted in red with an alert icon
- **Cell detail modal** — lists every `rule_id` + `message` for that cell, and shows
  the `suggested_fix` with a one-click **Accept** button if provided

---

## Gotcha: Registry is Frozen at Import

The `rule_registry.freeze()` call at the bottom of `rules.py` prevents any further
registration once the module has been imported. If you try to register a rule in a
separate file that is imported *after* `rules.py`, you will get a `RuntimeError`.

**Always add registrations to `rules.py` before the `rule_registry.freeze()` line.**

