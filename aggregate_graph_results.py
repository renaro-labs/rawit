"""Aggregate completed RAWIT O1 synthetic graph baseline runs (no retraining)."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs', type=Path, default=Path('experiments/runs'))
    ap.add_argument('--out', type=Path, default=Path('reports/baselines'))
    args = ap.parse_args()
    rows, runs = [], []
    reference, split_hash = None, None
    keys = ['part', 'date', 'prov_code', 'h']
    expected = {(p, h) for p in ('val', 'test') for h in (5, 10, 20)}
    for model in ('gwn', 'mtgnn'):
        for seed in range(5):
            path = args.runs / f'{model}_synth_O1_s{seed}'
            def check(condition, message):
                if not condition:
                    raise ValueError(f'{path}: {message}')
            check(all((path / f).is_file() for f in ('best.pt', 'preds.csv', 'summary.json')), 'missing artifacts')
            s = json.loads((path / 'summary.json').read_text(encoding='utf-8'))
            check((s['model'], s['origin'], s['seed'], s['smoke']) == (model, 'O1', seed, False), 'wrong run metadata')
            check(s['device'] == 'cuda', 'expected CUDA run')
            if split_hash is None:
                split_hash = s['split_hash']
            check(bool(split_hash) and s['split_hash'] == split_hash, 'split hash mismatch')
            df = pd.read_csv(path / 'preds.csv', dtype={'prov_code': str})
            check(df['model'].eq(model).all() and df['fold'].eq('O1').all() and df['seed'].eq(seed).all(), 'wrong prediction metadata')
            check(not df.duplicated(keys).any(), 'duplicate prediction keys')
            check(set(zip(df.part, df.h)) == expected, 'unexpected split/horizon')
            check(df.y_mask.isin([True, False]).all(), 'invalid mask')
            df = df.sort_values(keys).reset_index(drop=True)
            base = df[keys + ['y_true', 'y_mask', 'naive_pred']]
            if reference is None:
                reference = base.copy()
            else:
                check(reference.equals(base), 'evaluation keys, targets, mask or naive predictions differ')
            scores = {(v['part'], v['h']): v for v in s['scores']}
            check(len(s['scores']) == 6 and set(scores) == expected, 'invalid summary scores')
            for (part, h), g in df.groupby(['part', 'h']):
                g = g.loc[g.y_mask.astype(bool)]
                check(len(g) == {'val': 3774, 'test': 8160}[part], 'unexpected valid count')
                check(np.isfinite(g[['y_true', 'y_pred', 'naive_pred']].to_numpy()).all(), 'nonfinite valid predictions')
                mae = float(np.abs(g.y_true - g.y_pred).mean())
                naive = float(np.abs(g.y_true - g.naive_pred).mean())
                sc = scores[part, h]
                check(sc['n'] == len(g) and np.isclose(mae, sc['model_mae'], atol=.05, rtol=0) and np.isclose(naive, sc['naive_mae'], atol=.05, rtol=0), 'CSV/summary metric mismatch')
                check(naive > 0, 'zero naive MAE')
                rows.append(dict(model=model, seed=seed, origin='O1', part=part, h=h, n=len(g), model_mae=mae, naive_mae=naive, improvement_pct=100*(1-mae/naive), beats_naive=mae<naive))
            history = s['history']
            best = min(history, key=lambda v: v['val_mae_rp'])
            check(best['epoch'] == s['best_epoch'] and np.isclose(best['val_mae_rp'], s['best_val_mae_rp']), 'best epoch mismatch')
            stop = history[-1]['epoch']
            check(stop == s['epochs_requested'] or stop-s['best_epoch'] == s['config']['patience'], 'unexpected stop epoch')
            runs.append(dict(model=model, seed=seed, best_epoch=s['best_epoch'], stop_epoch=stop, best_val_mae_rp=s['best_val_mae_rp'], peak_allocated_gb=s['peak_allocated_gb'], peak_reserved_gb=s['peak_reserved_gb'], split_hash=split_hash))
            print(f'{model} seed {seed}: VALIDATED')
    metrics = pd.DataFrame(rows)
    run_metrics = pd.DataFrame(runs)
    summary = metrics.groupby(['model','part','h'], as_index=False).agg(seeds=('seed','nunique'), mean_mae=('model_mae','mean'), sd_mae=('model_mae','std'), min_mae=('model_mae','min'), max_mae=('model_mae','max'), naive_mae=('naive_mae','mean'), mean_improvement_pct=('improvement_pct','mean'), wins=('beats_naive','sum'))
    summary['win_rate_pct'] = 100*summary.wins/summary.seeds
    gpu = run_metrics.groupby('model', as_index=False).agg(mean_best_epoch=('best_epoch','mean'), max_peak_allocated_gb=('peak_allocated_gb','max'), max_peak_reserved_gb=('peak_reserved_gb','max'))
    gpu['under_3gb'] = (gpu.max_peak_allocated_gb < 3) & (gpu.max_peak_reserved_gb < 3)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, frame in [('graph_metrics', metrics), ('graph_summary', summary), ('graph_run_metrics', run_metrics), ('graph_gpu_summary', gpu)]:
        frame.to_csv(args.out / f'{name}.csv', index=False)
    print('\nTEST SUMMARY (Rp/kg; sample SD)')
    print(summary.loc[summary.part.eq('test')].to_string(index=False, float_format=lambda x: f'{x:.4f}'))
    print('\nGPU SUMMARY\n' + gpu.to_string(index=False))
    print('\nAGGREGATION COMPLETE:', args.out)


if __name__ == '__main__':
    main()
