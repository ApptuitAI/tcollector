#!/usr/bin/env python
# This file is part of tcollector.
# Copyright (C) 2011  The tcollector Authors.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser
# General Public License for more details.  You should have received a copy
# of the GNU Lesser General Public License along with this program.  If not,
# see <http://www.gnu.org/licenses/>.
"""Collector for MySQL."""

# pylint does not understand the mysqldb module and errors out that OperationalError does not exist in MySQLdb
# See https://github.com/PyCQA/pylint/issues/1138
# disable the no-member check for now and hope we catch it in IDEA
#
# pylint: disable=no-member
#

import errno
import os
import re
import socket
import sys
import time

try:
    import MySQLdb
except ImportError:
    MySQLdb = None  # This is handled gracefully in main()

from collectors.etc import mysqlconf
from collectors.lib import utils
from collectors.etc import yaml_conf
from collectors.etc import metric_naming

COLLECTION_INTERVAL = 15  # seconds
CONNECT_TIMEOUT = 2  # seconds
# How frequently we try to find new databases.
DB_REFRESH_INTERVAL = 60  # seconds
# Usual locations where to find the default socket file.
DEFAULT_SOCKFILES = set([
    "/tmp/mysql.sock",  # MySQL's own default.
    "/var/lib/mysql/mysql.sock",  # RH-type / RPM systems.
    "/var/run/mysqld/mysqld.sock",  # Debian-type systems.
])
# Directories under which to search additional socket files.
SEARCH_DIRS = [
    "/var/lib/mysql",
]

METRIC_MAPPING = yaml_conf.load_collector_configuration('mysql_metrics.yml')


class DB(object):
    """Represents a MySQL server (as we can monitor more than 1 MySQL)."""

    def __init__(self, db_connection_props, db_config_host, db_custom_tags, dbname, db, cursor, version):
        self.dbname = dbname
        self.db = db
        self.cursor = cursor
        self.version = version
        self.master = None
        self.slave_bytes_executed = None
        self.relay_bytes_relayed = None

        version = version.split(".")
        try:
            self.major = int(version[0])
            self.medium = int(version[1])
        except (ValueError, IndexError) as e:
            self.major = self.medium = 0

        self.remotehostconnect = True
        self.db_connection_props = db_connection_props
        self.db_config_host = db_config_host
        self.db_custom_tags = db_custom_tags

    def __str__(self):
        return "DB(%r, %r, version=%r)" % (self.db_config_host, self.dbname,
                                           self.version)

    def __repr__(self):
        return self.__str__()

    def isShowGlobalStatusSafe(self):
        """Returns whether or not SHOW GLOBAL STATUS is safe to run."""
        # We can't run SHOW GLOBAL STATUS on versions prior to 5.1 because it
        # locks the entire database for too long and severely impacts traffic.
        return self.major > 5 or (self.major == 5 and self.medium >= 1)

    def query(self, sql):
        """Executes the given SQL statement and returns a sequence of rows."""
        assert self.cursor, "%s already closed?" % (self,)
        try:
            self.cursor.execute(sql)
        except MySQLdb.OperationalError as mysql_op_err:
            (errcode, msg) = mysql_op_err.args
            if errcode != 2006:  # "MySQL server has gone away"
                raise
            self._reconnect()
        return self.cursor.fetchall()

    def close(self):
        """Closes the connection to this MySQL server."""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.db:
            self.db.close()
            self.db = None

    def _reconnect(self):
        """Reconnects to this MySQL server."""
        self.close()
        self.db = mysql_connect(self.db_connection_props)
        self.cursor = self.db.cursor()


def mysql_connect(conn_props):
    """Connects to the MySQL server using the specified connection properties."""
    return MySQLdb.connect(host=conn_props[0],
                           port=conn_props[1],
                           user=conn_props[2].encode('utf-8'),
                           passwd=conn_props[3].encode('utf-8'))


def todict(db, row):
    """Transforms a row (returned by DB.query) into a dict keyed by column names.
  
    Args:
      db: The DB instance from which this row was obtained.
      row: A row as returned by DB.query
    """
    d = {}
    for i, field in enumerate(db.cursor.description):
        column = field[0].lower()  # Lower-case to normalize field names.
        d[column] = row[i]
    return d


def get_dbname(sockfile):
    """Returns the name of the DB based on the path to the socket file."""
    if sockfile in DEFAULT_SOCKFILES:
        return "default"
    m = re.search("/mysql-(.+)/[^.]+\.sock$", sockfile)
    if not m:
        utils.err("error: couldn't guess the name of the DB for " + sockfile)
        return None
    return m.group(1)


def find_sockfiles():
    """Returns a list of paths to socket files to monitor."""
    paths = []
    # Look for socket files.
    for dir in SEARCH_DIRS:
        if not os.path.isdir(dir) or not os.access(dir, os.R_OK):
            continue
        for name in os.listdir(dir):
            subdir = os.path.join(dir, name)
            if not os.path.isdir(subdir) or not os.access(subdir, os.R_OK):
                continue
            for subname in os.listdir(subdir):
                path = os.path.join(subdir, subname)
                if utils.is_sockfile(path):
                    paths.append(path)
                    break  # We only expect 1 socket file per DB, so get out.
    # Try the default locations.
    for sockfile in DEFAULT_SOCKFILES:
        if not utils.is_sockfile(sockfile):
            continue
        paths.append(sockfile)
    return paths


def die():
    exit(13)


def find_databases(dbs=None):
    """Returns a map of dbname (string) to DB instances to monitor.
  
    Args:
      dbs: A map of dbname (string) to DB instances already monitored.
        This map will be modified in place if it's not None.
    """
    if dbs is None:
        dbs = {}
    for db_config_host in mysqlconf.get_db_hosts():
        if db_config_host in dbs:
            continue
        conn_props = mysqlconf.get_db_connection_properties(db_config_host)
        db_name = "default"
        try:
            db = mysql_connect(conn_props)
            cursor = db.cursor()
            cursor.execute("SELECT VERSION()")
            connected = True
        except (EnvironmentError, EOFError, RuntimeError, socket.error,
                MySQLdb.MySQLError) as e:
            utils.err("Couldn't connect to %s: %s" % (conn_props[2] + "@" + db_config_host + ":" + str(conn_props[1]), e))
            continue

        if connected:
            version = cursor.fetchone()[0]
            dbs[db_config_host] = DB(db_connection_props=conn_props, db_config_host=db_config_host,
                                     db_custom_tags=mysqlconf.get_db_custom_tags(db_config_host),
                                     dbname=db_name, db=db, cursor=cursor, version=version)

    if not dbs:
        die()

    return dbs


def now():
    return int(time.time())


def isyes(s):
    if s.lower() == "yes":
        return 1
    return 0


def collectInnodbStatus(db):
    """Collects and prints InnoDB stats about the given DB instance."""
    ts = now()

    def printmetric(metric, value, tags=""):
        print("mysql.%s %d %s schema=%s%s" % (metric, ts, value, db.dbname, tags))
        metric_naming.print_if_apptuit_standard_metric("mysql." + metric, METRIC_MAPPING, ts, value,
                                                       tags=mysqlconf.get_db_custom_tags(db.db_config_host),
                                                       tags_str="schema=" + db.dbname + tags)

    innodb_status = db.query("SHOW ENGINE INNODB STATUS")[0][2]
    m = re.search("^(\d{6}\s+\d{1,2}:\d\d:\d\d) INNODB MONITOR OUTPUT$",
                  innodb_status, re.M)
    if m:  # If we have it, try to use InnoDB's own timestamp.
        ts = int(time.mktime(time.strptime(m.group(1), "%y%m%d %H:%M:%S")))

    line = None

    def match(regexp):
        return re.match(regexp, line)

    for line in innodb_status.split("\n"):
        # SEMAPHORES
        m = match("OS WAIT ARRAY INFO: reservation count (\d+), signal count (\d+)")
        if m:
            printmetric("innodb.oswait_array.reservation_count", m.group(1))
            printmetric("innodb.oswait_array.signal_count", m.group(2))
            continue
        m = match("Mutex spin waits (\d+), rounds (\d+), OS waits (\d+)")
        if m:
            printmetric("innodb.locks.spin_waits", m.group(1), " type=mutex")
            printmetric("innodb.locks.rounds", m.group(2), " type=mutex")
            printmetric("innodb.locks.os_waits", m.group(3), " type=mutex")
            continue
        m = match("RW-shared spins (\d+), OS waits (\d+);"
                  " RW-excl spins (\d+), OS waits (\d+)")
        if m:
            printmetric("innodb.locks.spin_waits", m.group(1), " type=rw-shared")
            printmetric("innodb.locks.os_waits", m.group(2), " type=rw-shared")
            printmetric("innodb.locks.spin_waits", m.group(3), " type=rw-exclusive")
            printmetric("innodb.locks.os_waits", m.group(4), " type=rw-exclusive")
            continue
        # GG 20141015 - RW-shared and RW-excl got separate lines and rounds in 5.5+
        m = match("RW-shared spins (\d+), rounds (\d+), OS waits (\d+)")
        if m:
            printmetric("locks.spin_waits", m.group(1), " type=rw-shared")
            printmetric("locks.rounds", m.group(2), " type=rw-shared")
            printmetric("locks.os_waits", m.group(3), " type=rw-shared")
            continue
        m = match("RW-excl spins (\d+), rounds (\d+), OS waits (\d+)")
        if m:
            printmetric("locks.spin_waits", m.group(1), " type=rw-exclusive")
            printmetric("locks.rounds", m.group(2), " type=rw-exclusive")
            printmetric("locks.os_waits", m.group(3), " type=rw-exclusive")
            continue
        # INSERT BUFFER AND ADAPTIVE HASH INDEX
        # TODO(tsuna): According to the code in ibuf0ibuf.c, this line and
        # the following one can appear multiple times.  I've never seen this.
        # If that happens, we need to aggregate the values here instead of
        # printing them directly.
        m = match("Ibuf: size (\d+), free list len (\d+), seg size (\d+),")
        if m:
            printmetric("innodb.ibuf.size", m.group(1))
            printmetric("innodb.ibuf.free_list_len", m.group(2))
            printmetric("innodb.ibuf.seg_size", m.group(3))
            continue
        m = match("(\d+) inserts, (\d+) merged recs, (\d+) merges")
        if m:
            printmetric("innodb.ibuf.inserts", m.group(1))
            printmetric("innodb.ibuf.merged_recs", m.group(2))
            printmetric("innodb.ibuf.merges", m.group(3))
            continue
        # ROW OPERATIONS
        m = match("\d+ queries inside InnoDB, (\d+) queries in queue")
        if m:
            printmetric("innodb.queries_queued", m.group(1))
            continue
        m = match("(\d+) read views open inside InnoDB")
        if m:
            printmetric("innodb.opened_read_views", m.group(1))
            continue
        # TRANSACTION
        m = match("History list length (\d+)")
        if m:
            printmetric("innodb.history_list_length", m.group(1))
            continue


def collect(db):
    """Collects and prints stats about the given DB instance."""

    ts = now()

    def printmetric(metric, value, tags=""):
        print("mysql.%s %d %s schema=%s%s" % (metric, ts, value, db.dbname, tags))
        metric_naming.print_if_apptuit_standard_metric("mysql." + metric, METRIC_MAPPING, ts, value,
                                                       tags=mysqlconf.get_db_custom_tags(db.db_config_host),
                                                       tags_str="schema=" + db.dbname + tags)

    has_innodb = False
    if db.isShowGlobalStatusSafe():
        for metric, value in db.query("SHOW GLOBAL STATUS"):
            try:
                if "." in value:
                    value = float(value)
                else:
                    value = int(value)
            except ValueError:
                continue
            metric = metric.lower()
            has_innodb = has_innodb or metric.startswith("innodb")
            printmetric(metric, value)

    if has_innodb:
        collectInnodbStatus(db)

    if has_innodb and False:  # Disabled because it's too expensive for InnoDB.
        waits = {}  # maps a mutex name to the number of waits
        ts = now()
        for engine, mutex, status in db.query("SHOW ENGINE INNODB MUTEX"):
            if not status.startswith("os_waits"):
                continue
            m = re.search("&(\w+)(?:->(\w+))?$", mutex)
            if not m:
                continue
            mutex, kind = m.groups()
            if kind:
                mutex += "." + kind
            wait_count = int(status.split("=", 1)[1])
            waits[mutex] = waits.get(mutex, 0) + wait_count
        for mutex, wait_count in waits.items():
            printmetric("innodb.locks", wait_count, " mutex=" + mutex)

    ts = now()

    mysql_slave_status = db.query("SHOW SLAVE STATUS")
    if mysql_slave_status:
        slave_status = todict(db, mysql_slave_status[0])
        master_host = slave_status["master_host"]
    else:
        master_host = None

    if master_host and master_host != "None":
        sbm = slave_status.get("seconds_behind_master")
        if isinstance(sbm, int):
            printmetric("slave.seconds_behind_master", sbm)
        printmetric("slave.bytes_executed", slave_status["exec_master_log_pos"])
        printmetric("slave.bytes_relayed", slave_status["read_master_log_pos"])
        printmetric("slave.thread_io_running",
                    isyes(slave_status["slave_io_running"]))
        printmetric("slave.thread_sql_running",
                    isyes(slave_status["slave_sql_running"]))

    states = {}  # maps a connection state to number of connections in that state
    for row in db.query("SHOW PROCESSLIST"):
        id, user, host, db_, cmd, time, state = row[:7]
        states[cmd] = states.get(cmd, 0) + 1
    for state, count in states.items():
        state = state.lower().replace(" ", "_")
        printmetric("connection_states", count, " state=%s" % state)


def main(args):
    """Collects and dumps stats from a MySQL server."""
    if MySQLdb is None:
        utils.err("error: Python module `MySQLdb' is missing")
        return 1

    last_db_refresh = now()
    dbs = find_databases()
    while True:
        ts = now()
        if ts - last_db_refresh >= DB_REFRESH_INTERVAL:
            find_databases(dbs)
            last_db_refresh = ts

        errs = []
        for dbname, db in dbs.items():
            try:
                collect(db)
            except (EnvironmentError, EOFError, RuntimeError, socket.error,
                    MySQLdb.MySQLError) as e:
                if isinstance(e, IOError) and e[0] == errno.EPIPE:
                    # Exit on a broken pipe.  There's no point in continuing
                    # because no one will read our stdout anyway.
                    return 2
                utils.err("error: failed to collect data from %s: %s" % (db, e))
                errs.append(dbname)

        for dbname in errs:
            del dbs[dbname]

        sys.stdout.flush()
        time.sleep(COLLECTION_INTERVAL)


if __name__ == "__main__":
    sys.stdin.close()
    sys.exit(main(sys.argv))
