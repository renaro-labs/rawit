import numpy as np

from renaro.graph_perturb import add_edges, drop_edges, perturbation_grid, rewire_edges


def _base():
    a = np.zeros((5, 5), dtype=np.uint8)
    a[0, 1] = a[1, 2] = a[2, 3] = a[3, 4] = 1
    return a


def test_perturbations_keep_diagonal_and_are_deterministic():
    a = _base()
    for fn in (drop_edges, add_edges, rewire_edges):
        x = fn(a, 0.5, seed=7)
        y = fn(a, 0.5, seed=7)
        assert np.array_equal(x, y)
        assert np.array_equal(np.diag(x), np.zeros(5, dtype=np.uint8))


def test_drop_and_add_expected_direction():
    a = _base()
    assert drop_edges(a, 0.5, 1).sum() == 2
    assert add_edges(a, 1.0, 1).sum() > a.sum()


def test_grid_has_45_perturbations_plus_clean_and_none():
    items = list(perturbation_grid(_base()))
    assert len(items) == 47
    assert items[0][0] == "clean"
    assert items[1][0] == "none"
    assert sum(1 for name, *_ in items if name not in ("clean", "none")) == 45
