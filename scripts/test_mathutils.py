import mathutils

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
