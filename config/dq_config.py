"""
config/dq_config.py
=====================
Tunable thresholds and rules for agents/data_quality_agent.py, kept separate
from the agent logic so you can retune behavior without touching code.

Edit this file to change what counts as "critical" vs "high" vs "medium"
severity for null percentages, which columns are treated as mandatory
business keys, and the min/max valid ranges for common numeric field names
(age, price, salary, etc).
"""
DQ_CONFIG = {
    # Null-percentage cutoffs (%) that map to severity: >=40% -> high,
    # >=20% -> medium, >=5% -> low, below that -> no finding raised.
    "null_thresholds": {"low": 5, "medium": 20, "high": 40},

    # Columns (by lowercase name) that are always treated as mandatory keys:
    # ANY null in these columns is escalated straight to "critical" severity,
    # regardless of the overall null percentage threshold above.
    "critical_columns": {"customer_id", "account_id", "transaction_id", "order_id", "invoice_id", "employee_id"},

    # Column-name substrings that mark a field as optional (nulls in these
    # columns are NOT flagged at all, unless the column is also in
    # critical_columns above).
    "optional_column_name_patterns": ["middle_name", "nickname", "secondary", "alternate", "optional"],

    # String values treated as "semantic nulls" even when not technically NaN
    # (e.g. the literal text "unknown" or "9999" used as a placeholder).
    "semantic_nulls": {"", " ", "na", "n/a", "none", "null", "nan", "unknown", "not available", "-", "--", "?", "9999", "000000"},

    # Weights (must sum to 1.0) used to combine the six DQ dimension scores
    # into the Data Quality Agent's single overall score.
    "dimension_weights": {"completeness": .25, "uniqueness": .20, "validity": .20, "consistency": .15, "integrity": .10, "timeliness": .10},

    # Generic numeric-range validation rules, matched by substring against
    # column names (e.g. a column named "transaction_amount" matches "amount").
    # min/max of None means "no bound on that side".
    "generic_numeric_rules": {
        "age": {"min": 0, "max": 120, "severity": "high"},
        "rating": {"min": 0, "max": 5, "severity": "medium"},
        "percentage": {"min": 0, "max": 100, "severity": "medium"},
        "percent": {"min": 0, "max": 100, "severity": "medium"},
        "quantity": {"min": 0, "max": None, "severity": "medium"},
        "amount": {"min": 0, "max": None, "severity": "high"},
        "price": {"min": 0, "max": None, "severity": "high"},
        "salary": {"min": 0, "max": None, "severity": "high"},
        "balance": {"min": 0, "max": None, "severity": "medium"}
    }
}
