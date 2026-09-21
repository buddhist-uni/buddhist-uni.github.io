import mathutils
import math
from collections import defaultdict
from collections.abc import Collection


def test_cumsum():
    assert mathutils.cumsum([1, 2, 3]) == [1, 3, 6]

def test_weighted_shuffle():
    RUNS = 10000
    in_orders = 0
    wa = 2
    wb = 1
    for i in range(RUNS):
        result = mathutils.weighted_shuffle(
            ['a', 'b'],
            [wa, wb],
        )
        assert set(result) == set(['a', 'b'])
        assert len(result) == 2
        if result[0] == 'a':
            in_orders += 1
    mathutils.assert_binomial_result_is_close(
        in_orders,
        RUNS,
        expected_ratio=float(wa) / (wa+wb),
    )

def test_waypoint_power_decay():
    f = mathutils.gen_waypoint_power_decay_func(50, 0.3, 100, 0.1)
    assert math.isclose(
        f(0),
        1.0,
    )
    # a very sharp decline at the beginning
    assert math.isclose(
        f(1),
        0.83,
        abs_tol=0.001,
    )
    # linear in the middle
    assert math.isclose(
        f(49),
        0.305,
        abs_tol=0.0005,
    )
    assert math.isclose(
        f(50),
        0.3,
    )
    assert math.isclose(
        f(51),
        0.295,
        abs_tol=0.0005,
    )
    # and a very gradual decline at the end
    assert math.isclose(
        f(99),
        0.103,
        abs_tol=0.0005,
    )
    assert math.isclose(
        f(100),
        0.1,
    )
    f = mathutils.gen_waypoint_power_decay_func(50, 0.8, 100, 0.1)
    assert math.isclose(
        f(0),
        1.0,
    )
    # a very gradual decline at the beginning
    assert math.isclose(
        f(1),
        1.0,
        abs_tol=0.001,
    )
    # linear in the middle
    assert math.isclose(
        f(49),
        0.81,
        abs_tol=0.002,
    )
    assert math.isclose(
        f(50),
        0.8,
    )
    assert math.isclose(
        f(51),
        0.79,
        abs_tol=0.002,
    )
    # and a sharp decline at the end
    assert math.isclose(
        f(99),
        0.12,
        abs_tol=0.001,
    )
    assert math.isclose(
        f(100),
        0.1,
    )

class TestTopNHeap:
    def test_capacity_and_top_n_filtering(self):
        heap = mathutils.TopNHeap[int, str](n=3)
        data = [(10, "apple"), (5, "banana"), (20, "cherry"), (15, "date")]

        for weight, obj in data:
            heap.push(weight, obj)

        # Capacity should strictly be capped at N
        assert len(heap) == 3

        # Smallest element (5, 'banana') should have been evicted
        sorted_items = heap.get_sorted()
        assert sorted_items == [(20, "cherry"), (15, "date"), (10, "apple")]

    def test_under_capacity(self):
        heap = mathutils.TopNHeap[int, str](n=5)
        heap.push(1, "a")
        heap.push(2, "b")

        assert len(heap) == 2
        assert heap.get_sorted() == [(2, "b"), (1, "a")]

    def test_sorted_order_ascending_and_descending(self):
        heap = mathutils.TopNHeap[float, str](n=3)
        heap.push(1.1, "x")
        heap.push(3.3, "z")
        heap.push(2.2, "y")

        assert heap.get_sorted(reverse=True) == [(3.3, "z"), (2.2, "y"), (1.1, "x")]
        assert heap.get_sorted(reverse=False) == [(1.1, "x"), (2.2, "y"), (3.3, "z")]

    def test_smaller_element_discarded(self):
        heap = mathutils.TopNHeap[int, str](n=2)
        heap.push(10, "a")
        heap.push(20, "b")

        # Element smaller than current minimum (10) should be ignored
        heap.push(5, "c")

        assert len(heap) == 2
        assert heap.get_sorted() == [(20, "b"), (10, "a")]

    def test_isinstance_collection(self):
        heap = mathutils.TopNHeap[int, str](n=3)
        assert isinstance(heap, Collection)

    def test_len_operator(self):
        heap = mathutils.TopNHeap[int, str](n=3)
        assert len(heap) == 0
        heap.push(1, "a")
        assert len(heap) == 1

    def test_iteration(self):
        heap = mathutils.TopNHeap[int, str](n=3)
        heap.push(10, "a")
        heap.push(20, "b")

        extracted = list(heap)
        assert len(extracted) == 2
        assert (10, "a") in extracted
        assert (20, "b") in extracted

    def test_contains_operator(self):
        heap = mathutils.TopNHeap[int, str](n=3)
        heap.push(10, "a")

        assert (10, "a") in heap
        assert (99, "missing") not in heap


    def test_identical_weights_with_comparable_objects(self):
        heap = mathutils.TopNHeap[int, str](n=2)
        heap.push(10, "apple")
        heap.push(10, "banana")
        
        # At capacity N=2: root is (10, "apple") because "apple" < "banana"
        # Pushing (10, "cherry") evicts (10, "apple") because "apple" < "cherry"
        heap.push(10, "cherry")

        assert len(heap) == 2
        # Remaining elements are "cherry" and "banana"
        assert heap.get_sorted() == [(10, "cherry"), (10, "banana")]

    def test_float_weights(self):
        heap = mathutils.TopNHeap[float, str](n=2)
        heap.push(0.001, "small")
        heap.push(0.002, "large")
        heap.push(0.0015, "medium")

        assert heap.get_sorted() == [(0.002, "large"), (0.0015, "medium")]

    def test_defaultdict_factory(self):
        top_n_by_group: defaultdict[str, mathutils.TopNHeap[int, str]] = defaultdict(
            lambda: mathutils.TopNHeap[int, str](n=2)
        )

        stream = [
            ("group1", 10, "a"),
            ("group2", 100, "x"),
            ("group1", 20, "b"),
            ("group1", 30, "c"),
        ]

        for group, weight, item in stream:
            top_n_by_group[group].push(weight, item)

        assert len(top_n_by_group["group1"]) == 2
        assert top_n_by_group["group1"].get_sorted() == [(30, "c"), (20, "b")]

        assert len(top_n_by_group["group2"]) == 1
        assert top_n_by_group["group2"].get_sorted() == [(100, "x")]
