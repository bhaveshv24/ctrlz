from reservation import can_reserve


def test_exact_capacity():
    assert can_reserve(3, 3)


def test_spare_capacity():
    assert can_reserve(5, 3)


def test_insufficient_capacity():
    assert not can_reserve(2, 3)
