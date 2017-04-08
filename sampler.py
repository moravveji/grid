
"""
This module prepares training/validatin/test datasets to train/validate/test an 
artificial neural network. This is achieved through the "sampling" class, which 
handles the task of collecting the models properly from the grid.

This module inherits from the "star" module, in order to sample the model frequencies
based on the observed frequencies.
"""

import sys, os, glob
import logging
import time
import itertools
import numpy as np 

import utils, db_def, db_lib, query, star

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

logger = logging.getLogger(__name__)

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%



#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# S A M P L I N G   C L A S S
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
class sampling(object):
  """
  This class carries out sampling of the learning sets from the database. This class inherits the
  "star.star()" object to represent a star
  """

  def __init__(self):

    #.............................
    # The basic search constraints
    #.............................
    # The database to retrieve samples from
    self.dbname = ''
    # Sampling function name
    self.sampling_func = None
    # Maximum sample size to slice from all possible combinations
    self.max_sample_size = -1
    # The range in log_Teff to constrain 
    self.range_log_Teff = []
    # The range in log_g to constrain
    self.range_log_g = []
    # The range in rotation rate (percentage)
    self.range_eta = []
    # The models.id for the sample
    self.ids_models = []
    # The rotation_rates.id for the sample
    self.ids_rot = []

    #.............................
    # The resulting sample of attributes
    #.............................
    # Status of the learning dataset
    self.learning_done = False
    # Exclude eta = 0 from features (avoid singular matrix)
    self.exclude_eta_column = False
    # Names of learning features in the order queried from database
    self.feature_names = ['']
    # Resulting sample of features (type numpy.recarray)
    self.learning_x = None
    # Corresponding 2D frequency matrix for all features (type numpy.ndarray)
    self.learning_y = None
    # The sample size 
    self.sample_size = 0

    #.............................
    # Search constraints for modes
    #.............................
    # Modes id_types (from grid.sql) to fetch frequencies from, e.g. [0, 6]
    # for radial (0) and quadrupole zonal (6) modes
    self.modes_id_types = []
    # Modes lower and upper frequency scan range
    self.modes_freq_range = []

    #.............................
    # Frequency search plans
    #.............................
    # Liberal search without any restriction
    self.search_freely_for_frequencies = False
    # Strict search for period spacings
    self.search_strictly_for_dP = False
    # Strict search for frequency spacings
    self.search_strictly_for_df = False
    # Match from closest smallest frequency
    # and proceed to higher frequencies
    self.match_lowest_frequency = True
    # How many sigma around search frequency to consider?
    self.sigma_match_frequency = 3.0

    #.............................
    # Sizes of different learning sets
    # Default: -1, means not set yet
    #.............................
    # Training, cross-validation and test samples
    self.training_percentage = -1
    self.training_size = -1
    self.training_x = -1
    self.training_y = -1
    self.training_set_done = False

    self.cross_valid_percentage = -1
    self.cross_valid_size = -1
    self.cross_valid_x = -1
    self.cross_valid_y = -1
    self.cross_valid_set_done = False

    self.test_percentage = -1
    self.test_size = -1
    self.test_x = -1
    self.test_y = -1
    self.test_set_done = False

    #.............................
    # Inheriting from the star module
    #.............................
    self.star = star.star()


  ##########################
  # Setter
  ##########################
  def setter(self, attr, val):
    """
    Set a sampling attribute, e.g.
    >>>MySample = sampler.sampling()
    >>>MySample.setter('range_log_Teff', [4.12, 4.27])

    @param attr: The name of the attribute to set
    @type attr: str
    @param val: The corresponding data (type and value) for the attribute. 
           Note that the users is mainly responsible for the sanity of the input values, 
           though we internally check for some basic compatibility. The val can take any
           datatype
    @type val: int, float, bool, list, etc.
    """
    if not hasattr(self, attr):
      logger.error('sampling: setter: Attribute "{0}" is unavailable'.format(attr))
      sys.exit(1)

    # Some attributes require extra care/check
    if attr == 'range_log_g':
      if not isinstance(val, list) or len(val) != 2:
        logger.error('sampling: setter: range_log_g: Range list must have only two elements')
        sys.exit(1)
    elif attr == 'range_log_Teff':
      if not isinstance(val, list) or len(val) != 2:
        logger.error('sampling: setter: range_log_Teff: Range list must have only two elements')
        sys.exit(1)
    elif attr == 'range_eta':
      if not isinstance(val, list) or len(val) != 2:
        logger.error('sampling: setter: range_eta: Range list must have only two elements')
        sys.exit(1)
    elif attr == 'modes_id_types':
      if not isinstance(val, list):
        logger.error('sampling: setter: modes_id_types: Input must be a list of integers from grid.sql')
        sys.exit(1)
    elif attr == 'modes_freq_range':
      if not isinstance(val, list) or len(val) != 2:
        logger.error('sampling: setter: modes_freq_range: Range list must have only two elements')
        sys.exit(1)
    
    setattr(self, attr, val)

  ##########################
  # Getter
  ##########################
  def get(self, attr):
    """
    General-purpose method to get the value of a canonical attribute of the object
    E.g.

    >>>MySample = MyProblem.get('learning_x')

    @param attr: the name of the available attribute of the class
    @type attr: string
    @return: the value of the attribute
    @rtype: float
    """
    if not hasattr(self, attr):
      logger.error('sampling: get: The attribute "{0}" is undefined'.format(attr))
      sys.exit(1)

    return getattr(self, attr)

  ##########################
  # Methods
  ##########################
  def build_learning_set(self):
    """
    This routine prepares a learning (training + cross-validation + test) set from the "tracks", "models",
    and "rotation_rates" table from the database "dbname". The sampling method of the data (constrained or
    unconstrained) is specified by passing the function name as "sampling_func", with the function arguments
    "sampling_args".

    The result from this function can be used to randomly build training, cross-validation, and/or test
    sets by random slicing.

    @param self: An instance of the sampling class
    @type self: obj
    @return: None. However, the "self.sample" attribute is set to a numpy record array whose columns are
          the following:
          - M_ini: initial mass of the model
          - fov: overshoot free parameter
          - Z: metallicity
          - logD: logarithm of extra diffusive mixing
          - Xc: central hydrogen mass fraction
          - eta: percentage rotation rate w.r.t. to the break up
    @rtype: None
    """
    _build_learning_sets(self)

  def split_learning_sets(self):
    """
    Split the learning set (prepared by calling build_learning_sets) into a training set, cross-validation
    set, and a test set. To do such, the following three attributes of the "sampling" class is used (so, they
    must have been already set to their non-default value):
      - training_percentage: (default -1); valid range: 0 to 100
      - cross_valid_percentage: (default -1); valid range: 0 to 100
      - test_percentage: (default -1); valid range: 0 to 100
    As a result of applying this method, the following variables are set
      - training_size = -1
      - training_x = -1
      - training_y = -1

      - cross_valid_size = -1
      - cross_valid_x = -1
      - cross_valid_y = -1

      - test_size = -1
      - test_x = -1
      - test_y = -1

    Note: once the training/cross-validation/test sets (i.e. *_x and *_y) are prepared, they are randomly
          shuffled internally. So, no need to reshuffle them later.

    @param self: An instance of the sampling class
    @type self: obj
    @return: the above nine parameters will be set
    @rtype: None
    """
    _split_learning_sets(self)


#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def _split_learning_sets(self):
  """
  Refer to the documentation of the public method split_learning_set().  
  """
  p_train     = float(self.training_percentage)
  p_cv        = float(self.cross_valid_percentage)
  p_test      = float(self.test_percentage)
  percentages = [p_train, p_cv, p_test]
  if any(p < -1e-15 for p in percentages):
    logger.error('_split_learning_sets: Change the default (-1) for self.*_percentage=-1')
    sys.exit(1)

  if not all(0 <= p <= 1 for p in percentages):
    logger.error('_split_learning_sets: All three self.*_percentage must be set between 0 and 100')
    sys.exit(1)

  if np.abs(1-(p_train + p_cv + p_test)) > 1e-5:
    logger.error('_split_learning_sets: The three self.*_percentage do not all up to 1.0 (+/- 1e-5)')
    sys.exit(1)

  n_learn     = self.sample_size
  n_train     = int(n_learn * p_train)
  n_cv        = int(n_learn * p_cv)
  n_test      = int(n_learn * p_test)

  # due to round-off, the sum of splitted sets may not add up to sample_size, then ...
  if n_learn != n_train + n_cv + n_test:
    n_train   = n_learn - (n_cv + n_test)
  self.setter('training_size', n_train)
  self.setter('cross_valid_size', n_cv)
  self.setter('test_size', n_test)

  # Make randomly shuffled indixes for slicing
  ind_learn   = np.arange(n_learn)
  np.random.shuffle(ind_learn)
  ind_train   = ind_learn[ : n_train]
  ind_cv      = ind_learn[n_train : n_train + n_cv]
  ind_test    = ind_learn[n_train + n_cv :]

  # slice the learning set into training/cross-validation/test sets
  learn_x     = np.empty_like(self.learning_x)
  learn_y     = np.empty_like(self.learning_y)
  learn_x[:]  = self.learning_x
  learn_y[:]  = self.learning_y

  self.setter('training_x', learn_x[ind_train])
  self.setter('training_y', learn_y[ind_train])
  self.setter('training_set_done', True)

  self.setter('cross_valid_x', learn_x[ind_cv])
  self.setter('cross_valid_y', learn_y[ind_cv])
  self.setter('cross_valid_set_done', True)

  self.setter('test_x', learn_x[ind_test])
  self.setter('test_y', learn_y[ind_test])
  self.setter('test_set_done', True)

  logger.info('_split_learning_sets" Training, Cross-Validation and Test sets are prepared')

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def _build_learning_sets(self):
  """
  Refer to the documentation of the public method build_learning_set().
  """
  # Sanity checks ...
  if not self.dbname:
    logger.error('_build_learning_sets: specify "dbname" attribute of the class')
    sys.exit(1)

  if self.sampling_func is None:
    logger.error('_build_learning_sets: specify "sampling_func" attribute of the class')
    sys.exit(1)

  if self.star.num_modes == 0:
    logger.error('_build_learning_sets: The "modes" attribute of the "star" object of "sampling" not set yet!')
    sys.exit(1)

  # Get the list of tuples for the (id_model, id_rot) to fetch model attributes
  # tups_ids   = sampling_func(*sampler_args)  
  if self.sampling_func is constrained_pick_models_and_rotation_ids:

    if not self.range_log_Teff or not self.range_log_g or not self.range_eta:
      logger.error('_build_learning_sets: specify "ranges" properly')
      sys.exit(1)

    tups_ids = constrained_pick_models_and_rotation_ids(dbname=self.dbname,
                    n=self.max_sample_size, range_log_Teff=self.range_log_Teff,
                    range_log_g=self.range_log_g, range_eta=self.range_eta)

    logger.info('_build_learning_sets: constrained_pick_models_and_rotation_ids() succeeded')

  elif self.sampling_func is randomly_pick_models_and_rotation_ids:
    tups_ids = randomly_pick_models_and_rotation_ids(dbname=self.dbname, n=self.max_sample_size)

    logger.info('_build_learning_sets: randomly_pick_models_and_rotation_ids succeeded')

  else:
    logger.error('_build_learning_sets: Wrong sampling function specified in the class')
    sys.exit(1)

  # Split the model ids from the eta ids
  n_tups     = len(tups_ids)
  if n_tups  == 0:
    logger.error('_build_learning_sets: The sampler returned empty list of ids.')
    sys.exit(1)
  # set the class attributes
  self.setter('ids_models', [tup[0] for tup in tups_ids] )
  self.setter('ids_rot', [tup[1] for tup in tups_ids]) 
  self.setter('sample_size', len(self.ids_models) )

  # convert the rotation ids to actual eta values through the look up dictionary
  dic_rot    = db_lib.get_dic_look_up_rotation_rates_id(self.dbname)

  # reverse the key/values of the dic, so that the id_rot be the key, and eta the values
  # also, the eta values are floats which are improper to compare. Instead, we convert
  # eta values to two-decimal point string representation, and do the conversion like that
  dic_rot_inv= {}
  for key, val in dic_rot.items():
    str_eta  = '{0:.2f}'.format(key[0])
    dic_rot_inv[(val, )] = str_eta
  # create a 1-element tuple of eta values in f4 format to be stiched to a tuple of 
  # other attributes below
  eta_vals   = [ ( np.float32(dic_rot_inv[(id_rot,)]), ) for id_rot in self.ids_rot ]
  logger.info('_build_learning_sets: all eta values successfully collected')

  # Even if one model id is passed (repeated) several times in the following query, only the first
  # occurance is effective. Therefore, the size of the returned results from the following query
  # is a factor (len(set(ids_rot))) larger than the result of the query. Then, the problem of 1-to-1
  # matching is resolved by setting up a look-up dictionary
  the_query  = query.get_M_ini_fov_Z_logD_Xc_from_models_id(self.ids_models)
  
  with db_def.grid_db(dbname=self.dbname) as the_db:
    the_db.execute_one(the_query, None)
    params   = the_db.fetch_all()
    n_par    = len(params)
    if n_par == 0:
      logger.error('_build_learning_sets: Found no matching model attributes')
      sys.exit(1)
    else:
      logger.info('_build_learning_sets: Fetched "{0}" unique models'.format(n_par))
    
    # local look-up dictionary
    dic_par  = {}
    for tup in params:
      key    = (tup[0], )   # i.e. models.id
      val    = tup[1:]      # i.e. (M_ini, fov, Z, logD, Xc)
      dic_par[key] = val
    logger.info('_build_learning_sets: Look up dictionary for models is built')

  reconst    = [dic_par[(key, )] for key in self.ids_models]
  dic_par    = []           # delete dic_par and release memory

  # whether or not include the eta column
  if self.exclude_eta_column:
    stiched  = reconst[:]
  else:
    stiched  = [reconst[k] + eta_vals[k] for k in range(self.sample_size)]
  reconst    = []           # destroy the list, and free up memory
  
  # Now, build the thoretical modes corresponding to each row in the sampled data
  # only accept those rows from the sample whose corresponding frequency row is useful
  # for our specific problem
  # inds_keep  = []
  rows_keep  = []
  freq_keep  = []
  modes_dtype= [('id_model', 'int32'), ('id_rot', 'int16'), ('n', 'int16'), 
                ('id_type', 'int16'), ('freq', 'float32')]

  with db_def.grid_db(dbname=self.dbname) as the_db:
    
    # Get the mode_types look up dictionary
    dic_mode_types = db_lib.get_dic_look_up_mode_types_id(the_db)

    # Execute the prepared statement to speed up querying for self.sample_size times
    statement= 'prepared_statement_modes_from_fixed_id_model_id_rot'
    if the_db.has_prepared_statement(statement):
      the_db.execute_one('deallocate {0}'.format(statement), None)

    tup_query= query.modes_from_fixed_id_model_id_rot_prepared_statement(statement,
                     id_type=self.modes_id_types, freq_range=self.modes_freq_range)
    prepared_statement = tup_query[0]
    exec_statement     = tup_query[1]
    the_db.execute_one(prepared_statement, None)

    # Now, query the database iteratively for all sampling ids
    for k, row in enumerate(stiched):
      id_model = self.ids_models[k]
      id_rot   = self.ids_rot[k]

      # pack all query constraints into a tuple
      tup_exec = (id_model, id_rot) + tuple(self.modes_id_types) + tuple(self.modes_freq_range)

      the_db.execute_one(exec_statement, tup_exec)
      this     = the_db.fetch_all()

      rec_this = utils.list_to_recarray(this, modes_dtype)

      # Trim off the GYRE list to match the observations
      rec_trim = _trim_modes(self, rec_this, dic_mode_types)

      # Decide whether or not to keep this (k-th) row based on the result of trimming
      if isinstance(rec_trim, bool) and rec_trim == False:
        # skip this row
        continue 
      else:
        # inds_keep.append(k)
        rows_keep.append(row)
        freq_keep.append( rec_trim['freq'] )

  matrix     = np.stack(rows_keep, axis=0)
  stiched    = []           # destroy the list, and free up memory

  self.setter('feature_names', ['M_ini', 'fov', 'Z', 'logD', 'Xc', 'eta'])
  self.setter('learning_x', matrix)
  self.setter('sample_size', len(matrix))

  # and packing the frequencies followed by forced conversion to cycles per day
  rec_freq   = np.stack(freq_keep, axis=0)
  rec_freq   /= star.Hz_to_cd
  self.setter('learning_y', rec_freq)

  self.setter('learning_done', True)
  logger.info('_build_learning_sets: the attributes sampled successfully')

  return None

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def _trim_modes(self, rec_gyre, dic_mode_types):
  """
  Plan a strategy to trim the GYRE frequency list, and adapt it to the observed list based on the 
  requests of the user, i.e. based on the following attributes of the sampling object: 
  - search_freely_for_frequencies (Default = False)
  - search_strictly_for_dP (Default = False)
  - search_strictly_for_df (Default = False)
  - match_lowest_frequency (Default = True)
  - match_lowest_frequency (Default = 3.0)

  Note: The first three booleans specify the search method, and they are all False by defult. We check
  internally that only one of the flags is set to True, and the rest being False!

  Note: The return value from this routine is identical to the return from the following three functions:
  - _trim_modes_freely()
  - _trim_modes_by_dP()
  - _trim_modes_by_df()

  @param self: an instance of the "sampler.sampling" class
  @type self: object
  @param rec_gyre: the GYRE output list of frequencies as fetched from the database. The following
           columns are available here:
           - id_model: int32
           - id_rot: int16
           - n: int16
           - id_type: int16
           - freq: float32
  @type rec_gyre: np.recarray
  @param dic_mode_types: Look up dictionary to match the modes identification (l, m) with the modes.id_type
        attribute in the database. This dictionary is fetched from db_lib.get_dic_look_up_mode_types_id(). 
        However, we pass it as an argument instead of fetching it internally to speed up this function.
  @type dic_mode_types: dict
  @return: False, if for any reason no match is found between the observed and the modeled frequency lists.
           If successful, a matching slice of the input GYRE frequency list is returned.
  @rtype: np.recarray or bool
  """
  bool_arr = np.array([self.search_freely_for_frequencies, self.search_strictly_for_dP, 
                       self.search_strictly_for_df])
  n_True   = np.sum( bool_arr * 1 )
  if n_True != 1:
    logger.error('_trim_modes: Only one of the frequency search flags must be True, and the rest False.')
    sys.exit(1)

  if self.search_freely_for_frequencies:
    return _trim_modes_freely()
  elif self.search_strictly_for_dP:
    return _trim_modes_by_dP(self.star.modes, rec_gyre, self.match_lowest_frequency, dic_mode_types)
  elif self.search_strictly_for_df:
    return _trim_modes_by_df()
  else:
    logger.error('_trim_modes: unexpected frequency search plan')
    sys.exit(1)

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def _trim_modes_freely():
  """
  Choose matching frequencies with all liberty, without any restrictions/constraint.
  Not developed yet
  """
  logger.error('_trim_modes_freely: Not developed yet')
  sys.exit(1)

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def _trim_modes_by_dP(modes, rec_gyre, match_lowest_frequency, dic_mode_types):
  """
  
  @param modes: The observed modes, where each mode in the list is an instance of the "star.mode" class
  @type modes: list of star.mode
  @param rec_gyre: The numpy record array from GYRE frequency list coming from one GYRE output file
  @type rec_gyre: np.recarray
  @param match_lowest_frequency: flag to specify whether to start matching the dP series from the lowest
        observed frequency (and move towards higher frequency modes), or the opposite?
  @type match_lowest_frequency: bool
  @param dic_mode_types: Look up dictionary to match the modes identification (l, m) with the modes.id_type
        attribute in the database. This dictionary is fetched from db_lib.get_dic_look_up_mode_types_id(). 
        However, we pass it as an argument instead of fetching it internally to speed up this function.
  @type dic_mode_types: dict
  @return: False if, for one among many reasons, it is not possible to trim the GYRE list based on the 
        observed modes. If it succeeds, the input GYRE list will be trimmed to match the size of the input
        modes, and then it will be returned.
  @rtype: np.recarray or bool
  """
  n_modes = len(modes)
  n_rec   = len(rec_gyre)
  if n_rec < n_modes:
    logger.warning('_trim_modes_by_dP: The number of observed modes is greater than the GYRE frequency list')
    return False

  freq_unit= modes[0].freq_unit
  if freq_unit != 'cd':
    logger.error('_trim_modes_by_dP: The observed freq_unit: "{0}" must be "cd".'.format(freq_unit))
    sys.exit(1)

  # From observations, we have ...
  obs_freq = np.array([mode.freq for mode in modes]) # unit: per day
  d_freq   = obs_freq[1:] - obs_freq[:-1]
  d_freq_lo= d_freq[0]  
  d_freq_hi= d_freq[-1] 
  obs_l    = np.array([mode.l for mode in modes])
  obs_m    = np.array([mode.m for mode in modes])
  obs_n    = np.array([mode.n for mode in modes])

  the_l    = list(set(obs_l))[0]
  the_m    = list(set(obs_m))[0]
  the_key  = (the_l, the_m)
  the_id   = dic_mode_types[the_key]

  # From the GYRE output, we also have ...
  rec_types= rec_gyre['id_type']

  ind_l_m  = np.where(rec_types == the_id)[0]
  n_ind    = len(ind_l_m)
  if n_ind == 0:
    logger.error('_trim_modes_by_dP: No match between (l,m) of observed and model modes list')
    return False

  rec_gyre = rec_gyre[ind_l_m]
  rec_freq = rec_gyre['freq']
  n_rec    = len(rec_gyre)
  if n_rec < n_modes:
    logger.error('_trim_modes_by_dP: Frequency list is too short for this observations')
    return False

  freq_lo   = obs_freq[0] - d_freq_lo / 2.
  freq_hi   = obs_freq[-1] + d_freq_hi / 2.
  ind_trim  = np.where((rec_freq >= freq_lo) & (rec_freq <= freq_hi))[0]
  n_trim    = len(ind_trim)

  if n_trim != n_modes:
    logger.warning('_trim_modes_by_dP: The trimmed array is smaller than the list of observed modes!')
    return False

  trimmed   = rec_gyre[ind_trim]
  
  return trimmed

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def _trim_modes_by_df():
  """
  Choose matching frequencies based on regularities/spacings in frequency domain
  Not developed yet
  """
  logger.error('_trim_modes_by_df: Not developed yet')
  sys.exit(1)

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%



#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
#  S A M P L I N G   T H E   I N P U T   M O D E L S
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def constrained_pick_models_and_rotation_ids(dbname, n, 
               range_log_Teff=[3.5, 5], range_log_g=[0, 5], range_eta=[0, 51]):
  """
  Return a combination of "models" id and "rotation_rate" id by applying constraints on log_Teff,
  log_g and rotation rates. For a totally random (unconstrained) 
  selection, you may call "randomly_pick_models_and_rotation_ids()", instead. 

  Notes:
  - the constraint ranges are inclusive. 
  - the results are fetched firectly from executing a SQL query
  - the combination of the models and rotation rates are shuffled
  
  Example of calling:
  >>>

  @param dbname: the name of the database
  @type dbname: str
  @param n: the *maximum* number of models to retrieve
  @type n: int
  @param range_log_Teff: the lower and upper range of log_Teff to scan the grid. Default: [3.5, 5]
  @type range_log_Teff: list/tuple
  @param range_log_g: the lower and upper range of log_g to scan the grid. Default: [0, 5]
  @type range_log_g: list/tuple
  @param range_eta: The range of rotation rates (in percentage w.r.t to critical, e.g. 15). 
         Default: [0, 50]
  @type range_eta: list/tuple
  @return: a shuffled list of 2-element tuples, with the first element being the model id, and the
         second element being the rotation_rate id.
  @rtype: list of tuples
  """
  if not (len(range_log_Teff) == len(range_log_g) == len(range_eta) == 2):
    logger.error('constrained_pick_models_and_rotation_ids: Input "range" lists must have size = 2')
    sys.exit(1)

  # Get proper queries for each table
  q_models   = query.with_constraints(dbname=dbname, table='models',
                            returned_columns=['id'], 
                            constraints_keys=['log_Teff', 'log_g'], 
                            constraints_ranges=[range_log_Teff, range_log_g])

  q_rot      = query.with_constraints(dbname=dbname, table='rotation_rates',
                            returned_columns=['id'], 
                            constraints_keys=['eta'],
                            constraints_ranges=[range_eta])

  # Now, execute the queries, and fetch the data
  with db_def.grid_db(dbname=dbname) as the_db:
    # Execute the query for models
    the_db.execute_one(q_models, None)
    ids_models = [tup[0] for tup in the_db.fetch_all()]
    n_mod    = len(ids_models)
    if n_mod == 0:
      logger.error('constrained_pick_models_and_rotation_ids: Found no matching models.')
      sys.exit()

    # Execute the query for rotation rates
    the_db.execute_one(q_rot, None)
    ids_rot    = [tup[0] for tup in the_db.fetch_all()]
    n_rot      = len(ids_rot)
    if n_rot   == 0:
      logger.error('constrained_pick_models_and_rotation_ids: Found no matching rotation rates')
      sys.exit(1)

  np.random.shuffle(ids_models)
  np.random.shuffle(ids_rot)

  combo      = [] 
  for id_rot in ids_rot:
    combo.extend( [(id_model, id_rot) for id_model in ids_models] )

  if n > 0:
    return combo[:n]
  else:
    return combo

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def randomly_pick_models_and_rotation_ids(dbname, n):
  """
  Return a randomly-selected models together with their rotation rates from the grid.
  This function fetches all model "id" number from the "models" table, in addition to all the "id"
  numbers from the "rotation_rates" table. Then, it iterates over them all, and creates all possible
  tupls with two elements: first element being the model id, and the second element being the rotaiton
  id. Then, this list is shuffled using the numpy.random.shuffle method, and only the subset of this
  whole list is returned, with the size specified by "n".

  @param dbname: The name of the database
  @type dbname: grid
  @param n: the size of the randomly-selected combinations of model id and rotation ids
  @type n: int
  @return: list of tuples where each tuple consists of two integers: 
     - the model id
     - the rotaiton id
  @rtype: list of tuples
  """
  if n < 1:
    logger.error('randomly_pick_models_and_rotation_ids: Specify n > 1')
    sys.exit(1)

  # Retrieve two look up dictionaries for the models table and the rotation table
  t1         = time.time()
  dic_models = db_lib.get_dic_look_up_models_id(dbname_or_dbobj=dbname)
  dic_rot    = db_lib.get_dic_look_up_rotation_rates_id(dbname_or_dbobj=dbname)
  t2         = time.time()
  print 'Fetching two look up dictionaries took {0:.2f} sec'.format(t2-t1)

  ids_models = np.array([dic_models[key] for key in dic_models.keys()], dtype=np.int32)
  ids_rot    = np.array([dic_rot[key] for key in dic_rot.keys()], dtype=np.int16)
  t3         = time.time()
  print 'List comprehensions took {0:.2f} sec'.format(t3-t2)

  n_mod      = len(ids_models)
  n_eta      = len(id_rot)
  # if n > n_mod*n_eta: n = n_mod * n_eta

  np.random.shuffle(ids_models)
  np.random.shuffle(ids_rot)
  t4         = time.time()
  print 'Shuffling took {0:.2f} sec'.format(t4-t3)
  combo      = []
  for id_rot in ids_rot:
    combo.extend( [(id_model, id_rot) for id_model in ids_models] )

  t5         = time.time()
  print 'The combo list took {0:.2f} sec'.format(t5-t4)

  print 'Total time spent is {0:.2f} sec'.format(t5-t1)
  logger.info('randomly_pick_models_and_rotation_ids: Total time spent is {0:.2f} sec'.format(t5-t1))

  return combo[:n]

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
