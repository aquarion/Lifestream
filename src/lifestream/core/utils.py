"""Utility functions for Lifestream."""

import json
from datetime import datetime, timedelta


class AnAttributeError(Exception):
    """Custom attribute error for Lifestream."""

    pass


def Denary2Binary(n: int) -> str:
    """Convert denary (decimal) integer to binary string."""
    if n < 0:
        return "-" + Denary2Binary(-n)
    if n == 0:
        return "0"
    binary = ""
    while n > 0:
        binary = str(n % 2) + binary
        n = n // 2
    return binary


def int_to_roman(num: int) -> str:
    """Convert an integer to a Roman numeral."""
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_num = ""
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syms[i]
            num -= val[i]
        i += 1
    return roman_num


def convertNiceTime(number: int, format: str) -> str | int | bool:
    """Convert a number to various formats."""
    if format == "decimal" or format == "dec":
        return int(number)

    if format == "binary" or format == "bin":
        return Denary2Binary(number)

    if format == "hex" or format == "hexadecimal":
        return hex(int(number))

    if format == "oct" or format == "octal":
        return oct(int(number))

    if format == "roman":
        return int_to_roman(int(number))

    return False


def yearsago(years: int, from_date: datetime | None = None) -> datetime:
    """Get a date `years` years ago from the given date."""
    if from_date is None:
        from_date = datetime.now()
    try:
        return from_date.replace(year=from_date.year - years)
    except ValueError:
        # Must be 2/29!
        assert from_date.month == 2 and from_date.day == 29
        return from_date.replace(month=2, day=28, year=from_date.year - years)


def is_jsonable(x) -> bool:
    """Check if an object can be serialized to JSON."""
    try:
        json.dumps(x)
        return True
    except (TypeError, ValueError):
        return False


def force_json(incoming):
    """Recursively convert an object to JSON-serializable form."""
    if isinstance(incoming, dict):
        outgoing = {}
        for key, value in incoming.items():
            outgoing[key] = force_json(value)
        return outgoing
    elif isinstance(incoming, (tuple, list)):
        outgoing = []
        for value in incoming:
            outgoing.append(force_json(value))
        return outgoing
    else:
        if is_jsonable(incoming):
            return incoming
        else:
            return str(incoming)


def niceTimeDelta(  # noqa: C901 - complexity tracked in https://github.com/aquarion/Lifestream/issues/60
    delta_object: timedelta | int | float,
    format: str = "decimal",
) -> str:
    """Format a timedelta as a human-readable string."""
    if isinstance(delta_object, (int, float)):
        delta_object = timedelta(seconds=int(delta_object))

    years = 0
    days = delta_object.days
    hours = delta_object.seconds // 3600
    minutes = (delta_object.seconds // 60) % 60
    if days > 365:
        years = int(days / 365)
        days = int(days % 365)

    if int(years) == 1:
        years_message = "1 year, "
    elif years > 1:
        years_message = "%s years, " % convertNiceTime(years, format)
    else:
        years_message = ""

    if days < 7 and years == 0:
        hours = hours + (24 * days)
        days = 0

    if int(days) == 1:
        days_message = "1 day, "
    elif days > 1:
        days_message = "%s days, " % days
    else:
        days_message = ""

    if int(hours) == 1:
        hours_message = "1 hour, "
    elif hours > 1:
        hours_message = "%s hours, " % hours
    else:
        hours_message = ""

    if int(minutes) == 1:
        minutes_message = "1 minute"
    elif minutes > 1:
        minutes_message = "%s minutes" % minutes
    else:
        minutes_message = ""

    string = years_message + days_message + hours_message + minutes_message

    if string == "":
        return "seconds"
    else:
        return string
