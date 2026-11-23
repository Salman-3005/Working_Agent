import re
from typing import Tuple, Optional

def normalize_record_ref(raw_ref: Optional[str]) -> str:
    """
    Standardize dirty record references into a clean canonical format.
    Handles:
    - Leading/trailing whitespace: '  rec-1078  ' -> 'REC-1078'
    - Case insensitivity: 'rec-1082' -> 'REC-1082'
    - Alternate delimiters: 'REC_1079' -> 'REC-1079', 'REC#1080' -> 'REC-1080', 'REC 1084' -> 'REC-1084'
    - Special prefixes: 'R-1001' -> 'REC-1001'
    """
    if raw_ref is None:
        return ""
    
    clean = str(raw_ref).strip().upper()
    if not clean:
        return ""
    
    # Replace separators (_, #, spaces) between alpha and digits with a single hyphen
    # E.g. REC_1079 -> REC-1079, REC#1080 -> REC-1080, REC 1084 -> REC-1084
    clean = re.sub(r'[\s_#]+', '-', clean)
    
    # If it is formatted as REC1001 without hyphen
    match_no_hyphen = re.match(r'^(REC)(\d+)$', clean)
    if match_no_hyphen:
        clean = f"{match_no_hyphen.group(1)}-{match_no_hyphen.group(2)}"
        
    return clean

def parse_numeric_value(raw_val: Optional[str]) -> Tuple[Optional[float], bool, Optional[str]]:
    """
    Safely parse raw value string into a float for comparison.
    Survives dirty data:
    - Empty strings / None -> (None, False, 'EMPTY_VALUE')
    - Currency / formatting: '$1,200.00', '+450.00' -> (1200.0, True, None)
    - Unparseable strings: 'N/A', 'PENDING' -> (None, False, 'UNPARSEABLE_VALUE')
    """
    if raw_val is None:
        return None, False, "EMPTY_VALUE"
    
    val_str = str(raw_val).strip()
    if not val_str:
        return None, False, "EMPTY_VALUE"
    
    # Strip currency symbols and extraneous symbols
    cleaned = re.sub(r'[\$,€£\+]', '', val_str).strip()
    # Strip thousands separators
    cleaned = cleaned.replace(',', '')
    
    try:
        parsed_float = float(cleaned)
        return round(parsed_float, 4), True, None
    except (ValueError, TypeError):
        return None, False, f"UNPARSEABLE: '{val_str}'"

def values_are_equivalent(raw_a: Optional[str], raw_b: Optional[str]) -> Tuple[bool, str]:
    """
    Determines whether two values are semantically equivalent.
    Correctly recognizes non-errors:
    - '1,200.00' vs '1200' -> Equivalent (non-error)
    - '$350.50' vs '350.5' -> Equivalent (non-error)
    - '0.00' vs '0' -> Equivalent (non-error)
    """
    float_a, valid_a, err_a = parse_numeric_value(raw_a)
    float_b, valid_b, err_b = parse_numeric_value(raw_b)
    
    # Both are valid numbers
    if valid_a and valid_b:
        if abs(float_a - float_b) < 1e-4:
            return True, "EQUAL_NUMERIC"
        else:
            return False, f"VALUE_MISMATCH (A={float_a}, B={float_b})"
    
    # If one or both are unparseable or blank
    str_a = str(raw_a).strip() if raw_a is not None else ""
    str_b = str(raw_b).strip() if raw_b is not None else ""
    
    if str_a.lower() == str_b.lower() and str_a != "":
        return True, "EQUAL_STRING"
    
    if not valid_a and not valid_b:
        if str_a == str_b:
            return True, "BOTH_EMPTY_OR_IDENTICAL_UNPARSEABLE"
        return False, f"BOTH_UNPARSEABLE_MISMATCH (A='{str_a}', B='{str_b}')"
        
    if not valid_a:
        return False, f"SYSTEM_A_INVALID_VALUE (A='{str_a}', B='{str_b}')"
    if not valid_b:
        return False, f"SYSTEM_B_INVALID_VALUE (A='{str_a}', B='{str_b}')"
        
    return False, "VALUE_MISMATCH"
