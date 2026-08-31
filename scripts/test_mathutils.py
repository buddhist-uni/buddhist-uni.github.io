import mathutils
import math

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
