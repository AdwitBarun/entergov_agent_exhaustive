DQ_CONFIG = {
    "null_thresholds": {"low": 5, "medium": 20, "high": 40},
    "critical_columns": {"customer_id", "account_id", "transaction_id", "order_id", "invoice_id", "employee_id"},
    "optional_column_name_patterns": ["middle_name", "nickname", "secondary", "alternate", "optional"],
    "semantic_nulls": {"", " ", "na", "n/a", "none", "null", "nan", "unknown", "not available", "-", "--", "?", "9999", "000000"},
    "dimension_weights": {"completeness": .25, "uniqueness": .20, "validity": .20, "consistency": .15, "integrity": .10, "timeliness": .10},
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
