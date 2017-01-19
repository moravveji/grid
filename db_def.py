
"""
Define the basic class objects of the database (db), and some basic functionalities.
Some of the methods are wrappers around similar methods in psycopg2, with an additional
underscore "_" in the name; e.g. 
- grid_db.execute_one() wraps around psycopg2.execute()
- grid_db.execute_many() wraps around psycopg2.executemany()
- grid_db.fetch_one() wraps around psycopg2.fetchone()
- grid_db.fetch_many() wraps around psycopg2.fetchmany()
"""

import sys, os, glob
import logging
import numpy as np 
import subprocess
import psycopg2

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
logger = logging.getLogger(__name__)
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
class grid_db:
  """
  The class to interact with the grid, and execute SQL commands/querries
  """
  # ...................................
  def __init__(self, dbname='grid'):
    """
    The constructor of the class. Example of use:

    >>>my_job = db_def.grid_db()
    >>>cursor = my_job.get_cursor()
    >>>

    @param dbname: the name of the running database server. By default, it is called "grid" too.
    @type dbname: string
    """
    if exists(dbname) is False:
      logger.error('grid_db.__init__: Database "{0}" does not exist'.format(dbname))
      sys.exit(1)

    self.dbname = dbname

    connection  = psycopg2.connect('dbname={0}'.format(dbname))
    cursor      = connection.cursor()

    self.connection = connection
    self.cursor     = cursor

  def __enter__(self):
    return self 

  def __exit__(self, type, value, traceback):
    self.get_cursor().close()
    self.get_connection().close()

  # Setters
  # ...................................
  def set_dbname(self, dbname):
    self.dbname = dbname

  # Getters
  # ...................................
  def get_dbname(self):
    return self.dbname

  # ...................................
  def get_connection(self):
    return self.connection

  # ...................................
  def get_cursor(self):
    return self.cursor

  # Methods
  # ...................................
  def commit(self):
    """
    Wrapper around the psycopg2.cursor.commit()
    """
    self.connection.commit()

  # ...................................
  def execute_one(self, cmnd, value):
    """
    **Execute AND commit** one SQL command on the cursor, passed by the "cmnd"
    """
    self.cursor.execute(cmnd, value)
    self.commit()

  # ...................................
  def execute_many(self, cmnd, values):
    """
    **Execute AND commit** many (a list of) SQL commands on the cursor.
    The command is passed by the "cmnd", and the corresponding values are passed
    by the "values" tuple. This function is very useful for inserting data into
    the database.

    @param cmnd: A general command to execute many. E.g., cmnd can look like the 
           the following: cmnd = 'insert into table_name (var1, var2) values (?, ?)'
           This ensures that the execute/commit process is protected against possible
           Injection Attacks. 
    @type cmnd: string
    @param values: A list of tuples to execute the command. For every execute/commit
          transaction, one tuple must be in this list. The order of the quantities 
          in each tuple must match the order of the parameters in the command.
    @type values: list of tuples
    """
    if not isinstance(values, list):
      logger.error('execute_many: the 2nd argument (i.e. values) must be a list of tuples.')
      sys.exit(1)

    n_vals  = len(values)
    if n_vals == 0:
      logger.error('execute_many: the list of values is empty')
      sys.exit(1)

    cursor  = self.get_cursor()
    cursor.executemany(cmnd, values)
    self.commit()

  # ...................................
  def fetch_one(self):
    """
    A wrapper around the psycopg2.fetchone() method
    """
    return self.get_cursor().fetchone() 

  # ...................................
  def fetch_many(self):
    """
    A wrapper around psycopg2.fetchmany()
    """
    return self.get_cursor().fetchmany()

  # ...................................
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def exists(dbname):
  """
  Check if the database already exists.
  Returns True if the database exists, and False otherwise.
  """
  cmnd   = 'psql -lqt | cut -d \| -f 1 | grep -w {0}'.format(dbname)
  exe    = subprocess.Popen(cmnd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  stdout = exe.stdout.read().rstrip('\r\n').strip()
  stderr = exe.stderr.read().rstrip('\r\n').strip()
  err    = exe.returncode
  # print '1:', cmnd
  # print '2:', stdout
  # print '3:', stderr
  # print '4:', err
  if err is not None:
    logger.info('grid_db.exists(): Command failed: "{0}"'.format(cmnd))
    return False
  else:
    try:
      assert stdout == dbname
      return True
    except AssertionError:
      return False

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

