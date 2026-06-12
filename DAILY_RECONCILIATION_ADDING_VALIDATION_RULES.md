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
├── base.py              # Rule protocol + RuleResult dataclass
├── registry.py          # RuleRegistry singleton + auto-discovery
├── engine.py            # validate_batch() — calls registry, collects issues
├── __init__.py          # Loads all rule modules, then freezes registry
└── rules/               # Modular rule files (each self-registers)
    ├── generic.py       # Generic reusable rules (NotEmpty, MaxLength, etc.)
    ├── id_rules.py      # ID field validation
    ├── country.py       # Country code validation
    ├── numeric.py       # Numeric field validation
    ├── dates.py         # Date field validation
    └── indicators.py    # Y/N indicator validation
```

**To add a new rule:** Create a new file in the `rules/` directory (or add to an
existing thematic file), define your rule class, auto-register it, and add an import
to `__init__.py`. No `freeze()` call needed — the framework manages it.

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

A module-level singleton. Rules are registered against one or more column names via
the `@rule_registry.register(...)` decorator. The registry is **frozen** centrally in
`validation/__init__.py` after all rule modules are imported — no further registration
is possible after module load.

### Column Names

All 50 column names are defined in `api/daily_recon/columns.py`. Use the exact
`COLUMN_NAMES` constants when registering rules. Helpful groupings are also defined
there: `ID_COLUMNS`, `DATE_COLUMNS`, `NUMERIC_COLUMNS`, `INDICATOR_COLUMNS`,
`COUNTRY_CODE_COLUMNS`.

---

## Step-by-Step: Adding a Rule

### Step 1 — Choose or create a rule file

Rules are organised by theme in `api/daily_recon/validation/rules/`:

- **`generic.py`** — reusable rules (NotEmpty, MaxLength, Regex, AllowedValues)
- **`id_rules.py`** — ID field validation
- **`country.py`** — country code validation
- **`numeric.py`** — numeric field validation
- **`dates.py`** — date field validation
- **`indicators.py`** — Y/N indicator validation
- **New file** — create a new `.py` file if your rule doesn't fit these categories

### Step 2 — Write your rule class

Define a class with `rule_id` and `validate()` method. That's all that's required.

**Example: require `TRADEREF` to start with a specific prefix**

```python
class TradeRefPrefixRule:
    """Rule: TRADEREF must start with 'TXR-'."""

    rule_id = "trade_ref_prefix"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Check TRADEREF starts with TXR-.

        Args:
            value: The cell value to validate.
            record: The entire row dict (for cross-field rules).

        Returns:
            A RuleResult with validation outcome and optional suggested fix.
        """
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
        """Check QUANTITY when TRANSIND = Y.

        Args:
            value: The cell value (QUANTITY column).
            record: The entire row dict (contains TRANSIND).

        Returns:
            A RuleResult with validation outcome.
        """
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

### Step 3 — Register your rule in the same file

At the **bottom** of the same file where you defined your rule, instantiate it and
call `rule_registry.register()`:

```python
# ────────────────────────────────────────────────────────────────────────────
# Auto-register rule
# ────────────────────────────────────────────────────────────────────────────

_trade_ref_prefix = TradeRefPrefixRule()
rule_registry.register("TRADEREF")(_trade_ref_prefix)

_qty_positive_if_transaction = QuantityPositiveIfTransactionRule()
rule_registry.register("QUANTITY")(_qty_positive_if_transaction)
```

To register the **same rule against multiple columns** in one call:

```python
from ..columns import ID_COLUMNS  # import column groups from columns.py

_id_not_empty = IdNotEmptyRule()
rule_registry.register(*ID_COLUMNS)(_id_not_empty)
```

**Column groups available** from `api/daily_recon/columns.py`:
- `ID_COLUMNS` — `BUYER_ID`, `SELLER_ID`, `EXENTITYID`, `VENUETXNID`, `TRADEREF`
- `DATE_COLUMNS` — `BUYER_DOB`, `SELLER_DOB`, `BUYDECDOB`, `SELLDEC_DOB`
- `DATETIME_COLUMNS` — `TRDDATTIM`
- `NUMERIC_COLUMNS` — `QUANTITY`, `PRICE`, `NETAMT`, `DERIVATIVE_NOTIONAL_INCREASE_DECREASE`
- `COUNTRY_CODE_COLUMNS` — `BUYER_BRANCH_COUNTRY`, `SELLER_BRANCH_COUNTRY`
- `INDICATOR_COLUMNS` — `FRMDIRIND`, `TRANSIND`, `SHRTSELIND`, `OTCPSTIND`, `COMDERIND`, `SECFININD`

### Step 4 — Add an import to `validation/__init__.py`

Edit `api/daily_recon/validation/__init__.py` and add your module to the imports
**before** the `rule_registry.freeze()` line:

```python
from . import rules  # noqa: F401
from .rules import (  # noqa: F401
    country,
    dates,
    generic,
    id_rules,
    indicators,
    numeric,
    my_new_rules,      # ← add your module here
)
```

The framework will automatically load your module, trigger all `@rule_registry.register(...)`
decorators, and then freeze the registry. **No `freeze()` call needed in your file.**

### Step 5 — Trigger a new run

No restart is needed (the module is re-imported per Celery task). Click
**Run Query Now** in the UI, or POST to `/api/daily-recon/runs/trigger`.
Your rule will fire on the next run, and any failures will appear in the
cell detail panel.

---

## Already-Registered Rules Reference

The following rules are live. Each is defined in its own thematic module:

| Rule class | `rule_id` | File | Columns registered against |
|---|---|---|---|
| `IdNotEmptyRule` | `id_not_empty` | `rules/id_rules.py` | All `ID_COLUMNS` |
| `IdFormatRule` | `id_format` | `rules/id_rules.py` | All `ID_COLUMNS` |
| `CountryCodeRule` | `country_code_valid` | `rules/country.py` | All `COUNTRY_CODE_COLUMNS` |
| `NumericRule` | `numeric` | `rules/numeric.py` | All `NUMERIC_COLUMNS` |
| `PositiveNumberRule` | `positive_number` | `rules/numeric.py` | `QUANTITY`, `DERIVATIVE_NOTIONAL_INCREASE_DECREASE` |
| `DateFormatRule` | `date_format` | `rules/dates.py` | All `DATE_COLUMNS` |
| `ReasonableDateRule` | `reasonable_date` | `rules/dates.py` | All `DATE_COLUMNS` |
| `IndicatorRule` | `indicator_valid` | `rules/indicators.py` | All `INDICATOR_COLUMNS` |

**Also available** but not yet registered: `NotEmptyRule`, `MaxLengthRule`, `RegexRule`,
`AllowedValuesRule` (in `rules/generic.py`) — register these against any columns as needed.

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

### Use BaseRule for runtime enforcement (optional)

By default, rules use the `Rule` protocol (structural typing — checked by static analysers only).
For runtime enforcement of the contract, subclass `BaseRule`:

```python
from api.daily_recon.validation.base import BaseRule

class MyStrictRule(BaseRule):
    """A rule that enforces the contract at class definition time."""

    @property
    def rule_id(self) -> str:
        """Unique identifier for this rule."""
        return "my_strict_rule"

    def validate(self, value: str | None, record: dict[str, str | None]) -> RuleResult:
        """Validate a cell value."""
        # ... your logic
        pass
```

If you forget to implement `validate()` or `rule_id`, Python will raise `TypeError`
at class definition time. For most cases, the protocol approach is simpler; use
`BaseRule` only if you want compile-time checking.

### Parameterised rules (reusable across columns)

Use `__init__` to make a rule configurable:

```python
class AllowedValuesRule:
    """Rule: value must be one of an allowed set."""

    rule_id = "allowed_values"

    def __init__(self, allowed: set[str], case_sensitive: bool = False):
        """Initialize with allowed values.

        Args:
            allowed: Set of allowed values.
            case_sensitive: Whether comparison is case-sensitive.
        """
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

When you add a new rule, it's a good practice to write tests. Here's how:

```python
# tests/test_daily_recon/test_custom_rules.py

from api.daily_recon.validation.rules.my_new_rules import MyCustomRule


def test_my_custom_rule_valid():
    """Test that valid values pass."""
    rule = MyCustomRule()
    result = rule.validate("valid_value", {})
    assert result.is_valid


def test_my_custom_rule_invalid():
    """Test that invalid values fail with appropriate message."""
    rule = MyCustomRule()
    result = rule.validate("invalid_value", {})
    assert not result.is_valid
    assert "expected" in result.message.lower()


def test_my_custom_rule_blank_passes():
    """Test that blank values pass (if allowed by your rule)."""
    rule = MyCustomRule()
    result = rule.validate("", {})
    assert result.is_valid
```

Run the full test suite to ensure nothing regresses:

```powershell
conda activate txr_automation
pytest tests/ -k "daily_recon" -v
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

## How Framework Auto-Loading Works

When you add a rule module to `api/daily_recon/validation/rules/` and import it in
`__init__.py`, the framework automatically:

1. Imports the module (triggering all module-level code)
2. Executes all `rule_registry.register(...)` decorators
3. Calls `rule_registry.freeze()` to prevent late registration

**There is no `freeze()` call in your rule file.** The registry is frozen centrally
in `validation/__init__.py` after all rules are loaded. This prevents accidental
registration attempts from failing silently.

### Why This Matters

- **No merge conflicts** — each rule lives in its own file
- **No central file edits** — add new rules without touching a monolithic file
- **Type-safe** — IDE autocomplete works for column names (imported from `columns.py`)
- **Discoverable** — all rules are listed in `__init__.py` imports
- **Testable** — unfrozen registries can be created in tests for isolation

