import pytest

torch = pytest.importorskip("torch")

from renaro.baselines.lag_graph import LagGraphLite
from renaro.baselines.latent_regime import LatentRegimeLite


def _inputs(device, batch=2, n=34):
    x = torch.randn(batch, 60, n, 10, device=device)
    c = torch.randn(batch, 60, n, 5, device=device)
    s = torch.randn(n, n, 4, device=device)
    mask = torch.ones(n, n, dtype=torch.bool, device=device)
    mask[:, 0] = False
    mask[0, 1] = False
    cal = torch.randn(batch, 3, 4, device=device)
    return x, c, s, mask, cal


def test_latent_regime_forward():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LatentRegimeLite(10, 5, n_nodes=34).to(device)
    x, c, s, mask, cal = _inputs(device)
    y, a = model(x, c, s, mask, cal)
    assert y.shape == (2, 3, 34)
    assert a.shape == (2, 34, 34, 1)
    assert torch.isfinite(y).all()
    assert torch.allclose(a.sum((-1, -2)), torch.ones(2, 34, device=device), atol=1e-5)


def test_lag_graph_forward():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LagGraphLite(10, 5, n_nodes=34, n_lags=8).to(device)
    x, c, s, mask, cal = _inputs(device)
    y, a = model(x, c, s, mask, cal)
    assert y.shape == (2, 3, 34)
    assert a.shape == (2, 34, 34, 8)
    assert torch.isfinite(y).all()
    assert torch.allclose(a.sum((-1, -2)) + model.last_null_mass,
                          torch.ones(2, 34, device=device), atol=1e-5)
