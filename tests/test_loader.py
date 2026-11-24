import numpy as np
import pandas as pd
import pytest
import torch
from renaro.contract import HOLDOUT_START, PROV_CODES
from renaro.data.dummy import business_days, make_panel, make_target, make_mask, make_nodes, write_dummy
from renaro.data.io import load_panel, validate_dataset, holdout_guard
from renaro.data.datasets import WindowDataset, WindowSpec, Normalizer, make_loader

@pytest.fixture(scope='module')
def dataset(tmp_path_factory):
    dest = tmp_path_factory.mktemp('rawit') / 'dataset_v1'
    write_dummy(dest, seed=17)
    return dest

@pytest.fixture(scope='module')
def panel(dataset):
    return load_panel(dataset)


def test_schema_and_dates(dataset, panel):
    validate_dataset(dataset)
    assert len(panel.node_codes) == 34
    assert panel.node_codes == list(PROV_CODES)
    assert panel.mask.shape == (34, 34)
    assert panel.mask.dtype == np.uint8
    assert not panel.mask.diagonal().any()
    assert abs(panel.mask.sum() / (34 * 33) - 0.14) < 0.05
    assert panel.dates.min() == pd.Timestamp('2017-07-03')
    assert panel.dates.max() == pd.Timestamp('2026-05-29')
    holdout_guard(panel.panel)
    holdout_guard(panel.target)
    assert panel.dates.max() < pd.Timestamp(HOLDOUT_START)


def test_deterministic_seed():
    days = business_days()[:10]
    pd.testing.assert_frame_equal(make_panel(days, 3), make_panel(days, 3))
    assert np.array_equal(make_mask(3), make_mask(3))


def test_split_hash_stable(dataset):
    assert load_panel(dataset).split_hash == load_panel(dataset).split_hash


def test_target_h_semantics(panel):
    k, h = 100, 5
    y, mask = panel.target_at(k, h)
    rows = panel.target[panel.target.date == panel.dates[k+h-1]].set_index('prov_code').reindex(panel.node_codes)
    assert y.shape == mask.shape == (34,)
    assert np.array_equal(mask, rows.is_observed.to_numpy(dtype=bool))
    assert np.allclose(y[mask], rows.price.to_numpy()[mask])


def test_tensor_shapes_and_holdout(panel):
    ds = WindowDataset(panel, 'O1', 'train', WindowSpec(window=60, horizons=(5,10,20), node_subset=('11',)))
    item = ds[0]
    assert item['X'].shape == (60,34,10)
    assert item['C'].shape == (60,34,5)
    assert item['y'].shape == item['y_mask'].shape == (3,34)
    assert item['X'].dtype == item['y'].dtype == torch.float32
    assert item['y_mask'].dtype == torch.bool
    assert item['t_index'].dtype == torch.int64
    assert not item['y_mask'][:, 1:].any()
    assert pd.Timestamp(item['date']) < pd.Timestamp(HOLDOUT_START)
    assert ds.dates[ds.decision_indices[-1] + max(ds.spec.horizons)] <= pd.Timestamp('2022-06-30')


def test_normalization_only_train(panel):
    train = WindowDataset(panel, 'O1', 'train')
    val = WindowDataset(panel, 'O1', 'val')
    assert np.array_equal(train.mean, val.mean)
    assert np.array_equal(train.std, val.std)
    raw = np.array([[[1.0], [np.nan]], [[3.0], [5.0]]])
    norm = Normalizer().fit(raw)
    assert np.isclose(norm.mean[0], 3.0)
    assert np.isfinite(norm.transform(raw)).all()


def test_gpu_batch_under_50mb(panel):
    ds = WindowDataset(panel, 'O1', 'train')
    batch = next(iter(make_loader(ds, batch_size=8, shuffle=False)))
    tensor_bytes = sum(x.numel()*x.element_size() for x in batch.values() if isinstance(x, torch.Tensor))
    assert tensor_bytes < 50 * 1024 * 1024
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        device_batch = {k: v.cuda() if isinstance(v, torch.Tensor) else v for k,v in batch.items()}
        torch.cuda.synchronize()
        assert torch.cuda.max_memory_allocated() < 50 * 1024 * 1024
        del device_batch
