import random
import math
import heapq
from collections.abc import Collection, Iterator
from typing import Generic, TypeVar
from functools import reduce
from typing import Callable

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
  tolerance = z_score * binomial_stderr(trials, p=expected_ratio)
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

def gen_waypoint_power_decay_func(x_1: float, y_1: float, x_2: float, y_2: float) -> Callable[[float], float]:
  """
  Generates a callable function that smoothly interpolates between
    - f(0) -> 1
    - f(x_1) -> y_1
    - f(x_2) -> y_2
  
  Domain:
    x_2 > x_1 > 0
    1.0 > y_1 > y_2
  
  :return: The function
  :rtype: Callable[[float], float]
  """
  if x_1 > x_2:
    return gen_waypoint_power_decay_func(x_2, y_2, x_1, y_1)
  assert x_2 > x_1
  assert x_1 > 0
  assert 1.0 > y_1
  assert y_1 > y_2
  reduction = 1 - y_2
  K = math.log((1 - y_1) / reduction) / math.log(x_1 / x_2)
  D = reduction * x_2 ** (-K)
  return lambda x: 1.0-D*x**K

# W represents the weight type (must be comparable for heap ordering)
# T represents the object payload type
W = TypeVar("W")
T = TypeVar("T")
Item = tuple[W, T]
class TopNHeap(Generic[W, T], Collection[Item[W, T]]):
    def __init__(self, n: int) -> None:
        self.n: int = n
        self.data: list[Item[W, T]] = []

    def push(self, weight: W, obj: T) -> None:
        item: Item[W, T] = (weight, obj)
        if len(self.data) < self.n:
            heapq.heappush(self.data, item)
        # pyrefly: ignore [unsupported-operation]
        elif weight >= self.data[0][0]:
            heapq.heappushpop(self.data, item)

    def get_sorted(self, reverse: bool = True) -> list[Item[W, T]]:
        """Returns items ordered by weight (highest to lowest by default)."""
        # pyrefly: ignore [no-matching-overload]
        return sorted(self.data, reverse=reverse)

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[Item[W, T]]:
        """Yields elements from the heap (unordered)."""
        return iter(self.data)

    def __contains__(self, item: T | Item[W, T]) -> bool:
      if any(items[1] == item for items in self.data):
        return True
      if isinstance(item, tuple):
        return item in self.data
      return False

    def __repr__(self) -> str:
        return f"TopNHeap({self.get_sorted()})"
