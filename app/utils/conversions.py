from decimal import Decimal, InvalidOperation


def to_float(value):
    return float(str(value or "0").replace(",", "."))


def to_decimal(val):
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        return Decimal(str(val))
    s = str(val).strip()
    # aceita "1.234,56" e "1234,56"
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None
