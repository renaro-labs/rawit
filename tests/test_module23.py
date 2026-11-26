import pytest

torch = pytest.importorskip("torch")

from renaro.models.module23 import Module23


def _inputs(device, batch=2, n=34):
    x = torch.randn(batch, 60, n, 10, device=device)
    c = torch.randn(batch, 60, n, 5, device=device)
    s = torch.randn(n, n, 4, device=device)
    mask = torch.ones(n, n, dtype=torch.bool, device=device)
    mask[:, 0] = False
    mask[0, 1] = False
    cal = torch.randn(batch, 3, 4, device=device)
    return x, c, s, mask, cal


def test_module23_forward_and_gate_extremes():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = Module23(10, 5, n_nodes=34, n_lags=6).to(device)
    x, c, s, mask, cal = _inputs(device)
    y, a = model(x, c, s, mask, cal)
    assert y.shape == (2, 3, 34)
    assert a.shape == (2, 34, 34, 6)
    assert model.last_gate.shape == (2, 34, 1)
    assert torch.isfinite(y).all()

    model.gate_override = 1.0
    y1, _ = model(x, c, s, mask, cal)
    assert torch.allclose(model.last_gate, torch.ones_like(model.last_gate))
    model.gate_override = 0.0
    y0, _ = model(x, c, s, mask, cal)
    assert torch.allclose(model.last_gate, torch.zeros_like(model.last_gate))
    assert not torch.allclose(y1, y0)


def test_module23_variants_forward():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    x, c, s, mask, cal = _inputs(device)
    for kwargs in (
        {"no_gate": True},
        {"n_lags": 1},
        {"no_calendar": True},
        {"no_climate_gate": True, "no_climate": True},
    ):
        kwargs.setdefault("n_nodes", 34)
        model = Module23(10, 5, **kwargs).to(device)
        y, _ = model(x, c, s, mask, cal)
        assert y.shape == (2, 3, 34)
        assert torch.isfinite(y).all()
