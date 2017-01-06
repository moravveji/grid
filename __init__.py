__all__ = [
           'db_def',            # definition of database class for interactions
           'insert_def',        # definition of a class for data insertion
           'insert_lib',        # various functionalities for inserting data into tables
           'read',              # read ascii files
           'var_def',           # define basic data variables and class objects
           'var_lib',           # extra supporting functions for variables/data handling
           'version',           # track versions, release dates, and the changelog
           ]

from .version import __version__
# try:
#   import psycopg2
# except ImportError:
#   print 'ImportError: Please try installing psycopg2 first:'
#   print '<https://pypi.python.org/pypi/psycopg2>'