import random
import math
from functools import reduce

def binomial_stderr(n: int, p:float = 0.5):
  """
  Returns the expected standard error for a large n "coin toss" distro.

  Note that the binomial is only approximated by the normal distro
  when n is large and p is not close to 0 or 1
  
  :param n: The number of trials
  :type n: int
  :param p: The probability of success for each trial
  :type p: float
  """
  return math.sqrt(p * (1 - p) / n)

def assert_binomial_result_is_close(successes: int, trials: int, expected_ratio: float, z_score:float=3.291):
  tolerance = z_score * binomial_stderr(trials, expected_ratio)
  assert math.isclose(
      float(successes)/trials,
      expected_ratio,
      abs_tol=tolerance,
    )

def weighted_shuffle(items: list, weights: list[float]) -> list:
  """
  Shuffle items where higher weights tend toward the top.
  
  Args:
    items: List of items to shuffle
    weights: List of weights (higher = more likely near top)
  
  Returns:
    Shuffled list with heavier items tending toward top
  """
  # Pair each item with a random value raised to (1/weight)
  # Higher weights make the random value larger on average
  paired = [(random.random() ** (1.0 / w), item) 
            for item, w in zip(items, weights)]
  
  # Sort by the random values (descending)
  paired.sort(reverse=True)
  
  # Return just the items
  return [item for _, item in paired]

def cumsum(vec):
    return reduce(lambda a,x: a+[a[-1]+x] if a else [x], vec, [])
