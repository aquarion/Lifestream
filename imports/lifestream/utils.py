"""Utility functions for Lifestream."""

from datetime import timedelta

import simplejson as json


class AnAttributeError(Exception):
    pass


def convertNiceTime(number, format):
    if format == "decimal" or format == "dec":
        return int(number)

    if format == "binary" or format == "bin":
        return Denary2Binary(number)

    if format == "hex" or format == "hexadecimal":
        print("Converting %s to hex" % number)
        return hex(int(number))

    if format == "oct" or format == "octal":
        print("Converting %s to oct" % number)
        return oct(int(number))

    if format == "roman" or format == "roman":
        print("Converting %s to roman" % number)
        return int_to_roman(int(number))

    return False


def yearsago(years, from_date=None):
    from datetime import datetime

    if from_date is None:
        from_date = datetime.now()
    try:
        return from_date.replace(year=from_date.year - years)
    except ValueError:
        # Must be 2/29!
        assert from_date.month == 2 and from_date.day == 29  # can be removed
        return from_date.replace(month=2, day=28, year=from_date.year - years)


def is_jsonable(x):
    try:
        json.dumps(x)
        return True
    except:
        return False


def force_json(incoming):
    if incoming is dict:
        outgoing = {}
        for key, value in incoming:
            outgoing[key] = force_json(incoming)
        return outgoing
    elif incoming is tuple or incoming is list:
        outgoing = []
        for value in incoming:
            outgoing.append(force_json(incoming))
        return outgoing
    else:
        if is_jsonable(incoming):
            return force_json(incoming)
        else:
            return str(incoming)
    raise Exception("Logic failure")


def niceTimeDelta(delta_object, format="decimal"):

    if type(delta_object) is int:
        delta_object = timedelta(seconds=delta_object)

    try:
        years = 0
        days = delta_object.days
        hours = delta_object.seconds // 3600
        minutes = (delta_object.seconds // 60) % 60
        if days > 365:
            years = int(days / 365)
            days = int(days % 365)

    except AnAttributeError:
        years = int(delta_object / (60 * 60 * 24 * 365))
        remainder = delta_object % (60 * 60 * 24 * 365)
        days = int(remainder / (60 * 60 * 24))
        remainder = delta_object % (60 * 60 * 24)
        hours = remainder / (60 * 60)
        remainder = delta_object % (60 * 60)
        minutes = remainder / 60

    if int(years) == 1:
        years_message = "1 year, "
    elif years > 1:
        years_message = "%s years, " % convertNiceTime(years, format)
    else:
        years_message = ""

    if days < 7 and years == 0:
        hours = hours + (24 * days)
        days = 0

    # if (hours < 48 and years == 0 and days < 3):
    #   minutes = minutes + (60*hours)
    #   hours = 0;

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
