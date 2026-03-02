# Python

# Libraries

# Local
import lifestream
from lifestream.db import get_connection, get_cursor


def newstat(date, stat, number):
    dbcxn = get_connection()
    cursor = get_cursor(dbcxn)

    s_sql = "replace into lifestream_stats (`date`, `statistic`, `number`) values (%s, %s, %s);"
    cursor.execute(s_sql, (date, stat, number))

    # print cursor._last_executed

    dbcxn.commit()
    dbcxn.close()
    return True
