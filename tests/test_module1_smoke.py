import pytest

torch = pytest.importorskip("torch")

from renaro.models.module1 import ClimateConditionedLagGraph


@pytest.mark.parametrize("batch_size", [32])
def test_module1_forward_backward(batch_size):
    torch.manual_seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    b, t, n = (batch_size if device.type == "cuda" else 2), 60, 34
    model = ClimateConditionedLagGraph(
        10, 5, n_edge_features=4, n_calendar_future=4,
        hidden=64, n_lags=8, horizons=(5, 10, 20), forecast_aligned=True,
        n_nodes=n,
    ).to(device)
    x = torch.randn(b, t, n, 10, device=device)
    c = torch.randn(b, t, n, 5, device=device)
    s = torch.randn(n, n, 4, device=device)
    mask = torch.ones(n, n, dtype=torch.bool, device=device)
    mask[:, 0] = False
    mask[0, 1] = False
    cal = torch.randn(b, 3, 4, device=device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    y, a = model(x, c, s, mask, cal)
    assert y.shape == (b, 3, n)
    assert a.shape == (b, n, n, 8)
    assert torch.isfinite(y).all() and torch.isfinite(a).all()
    assert (a[:, :, 0, :] == 0).all()
    assert (a[:, 0, 1, :] == 0).all()
    assert torch.allclose(a.sum((-1, -2)) + model.last_null_mass,
                          torch.ones(b, n, device=device), atol=1e-5)
    loss = y.square().mean() + 1e-4 * model.entropy_regularizer(a)
    loss.backward()
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
    if device.type == "cuda":
        allocated = torch.cuda.max_memory_allocated(device)
        reserved = torch.cuda.max_memory_reserved(device)
        print(f"batch32 peak allocated={allocated} reserved={reserved}")
        assert allocated < 3_000_000_000
    else:
        print("GPU memory DoD: NOT TESTED (CPU only)")
