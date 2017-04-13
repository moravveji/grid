
"""
This module provides some generic utilities to facilitate working with different datatypes
and input/outputs conveniently.
"""

import sys, os, glob
import logging
import numpy as np 

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

logger = logging.getLogger(__name__)

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

def list_to_recarray(list_input, dtype):
  """
  Convert a list of tuples to a numpy recordarray. Each tuple is one retrieved row of data from calling
  the SQL queries, and fetching them through e.g. db.fetch_all() method.

  @param list_input: The inputs to be converted to numpy record array. They are 
  """

  return np.core.records.fromarrays(np.array(list_input).T, dtype=dtype)

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def ndarray_to_recarray(arr, dtype):
  """
  Convert a numpy ndarray to a numpy record array

  @param arr: the input array
  @param dtype: the list of np.dtype for all columns/attributes
  @return: a corresponding record array
  """
  
  # return np.core.records.fromrecords(arr, dtype=dtype)
  return np.core.records.fromarrays(arr.T, dtype=dtype)

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def recarray_to_ndarray(rec):
  """
  Convert a numpy record array to a matrix ndarray

  @param rec: numpy record array
  @return: ndarray
  """
  
  return rec.view(np.float32).reshape(rec.shape + (-1, ))

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def prepend_with_column_1(matrix):
  """
  Add a column of ones to the m-by-n matrix, so that the result is a m-by-n+1 matrix
  @param matrix: The general matrix of any arbitrary size with m rows and n columns
  @type matrix: np.ndarray
  @return: a matrix of m rows and n+1 columns where the 0-th column is all one.
  @rtype: np.ndarray
  """
  if not len(matrix.shape) == 2:
    print matrix.shape
    print len(matrix.shape)
    logger.error('prepend_with_column_1: Only 2D arrays are currently supported')
    sys.exit(1)

  col_1 = np.ones(( matrix.shape[0], 1 )) 

  return np.concatenate([col_1, matrix], axis=1)

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def gaussian(x, mu, sigma):
  """
  Return the Normal (Gaussian) probability distribution function g(x) for x with mean mu and standard
  deviation sigma, following the definition 

  \f[
      N(x,\mu,\sigma)=\frac{1}{\sqrt{2\pi}\sigma}\exp\left[-\frac{1}{2}\left(\frac{x-\mu}{\sigma}\right)^2\right].
  \f]

  @param x: array or value of the input 
  @type x: ndarray or float
  @param mu: the mean of the population
  @type mu: float
  @param sigma: the standard deviation of the population around the mean
  @type sigma: npdarray or float
  @return: The probability of x being between the interval x and x+epsilon, where epsilon goes to zero
  @rtype: ndarray or float
  """
  if isinstance(x, np.ndarray) and isinstance(sigma, np.ndarray):
    try:
      assert len(x) == len(sigma)
    except AssertionError:
      logger.error('gaussian: the size of input arrays "x" and "sigma" must be identical')
      sys.exit(1)

  scale = 1./(np.sqrt(2*np.pi)*sigma)
  arg   = -0.5 * ((x - mu)**2/sigma**2)
  
  return  scale * np.exp(arg)

#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
#%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
