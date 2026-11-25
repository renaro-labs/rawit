"""Run one graph baseline on dummy/synthetic data, never sealed holdout."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import yaml
from torch.utils.data import Subset
from renaro.data.io import load_panel
from renaro.data.datasets import WindowDataset, WindowSpec, make_loader, FEATURES
from renaro.eval.splits import rolling_origin, split_indices
from renaro.baselines.naive import asof_prices
from renaro.models.module1 import ClimateConditionedLagGraph
from renaro.train_loop import masked_log_mae, seed_everything

def predict(model, batch, device, context):
    edge, mask, calendar, horizons = context
    k = batch['t_index'].cpu().numpy()
    indices = k[:, None] + np.asarray(horizons)[None, :] - 1
    cal = torch.from_numpy(calendar[indices]).to(device)
    x = batch['X'].to(device)
    return model(x, batch['C'].to(device), edge.expand(x.shape[0], -1, -1, -1), mask, cal)


def graph_context(panel, spec, device, edge_path, calendar_path=None, prior_type="none"):
    n = len(panel.node_codes)
    if edge_path is None:
        edge = np.zeros((n,n,4), dtype=np.float32)
        edge[:,:,1] = panel.mask
    else:
        edge = np.load(edge_path, allow_pickle=False).astype(np.float32)
        if edge.shape != (n,n,4) or not np.isfinite(edge).all():
            raise ValueError('Expected finite edge array [N,N,4]')
        if not np.array_equal(edge[:,:,1], panel.mask):
            raise ValueError('Edge BPS flags do not match panel mask')
    # Provisional deterministic calendar: no target or observed climate is read.
    dow = np.asarray(panel.dates.day_of_week, dtype=float)
    month = np.asarray(panel.dates.month, dtype=float)-1
    calendar = np.stack([np.sin(2*np.pi*dow/7), np.cos(2*np.pi*dow/7),
                         np.sin(2*np.pi*month/12), np.cos(2*np.pi*month/12)], axis=-1).astype(np.float32)
    if calendar_path is not None:
        cols = ['is_ramadan', 'days_to_lebaran', 'dow', 'month']
        ref = pd.read_csv(calendar_path, parse_dates=['date']).set_index('date')
        if not ref.index.is_unique:
            raise ValueError('Duplicate calendar dates')
        ref = ref.reindex(panel.dates)
        if ref[cols].isna().any().any():
            raise ValueError('Missing calendar dates or features')
        ram = ref['is_ramadan'].astype(str).str.lower().map({'true': 1., 'false': 0.})
        days, weekday, month = (pd.to_numeric(ref[k], errors='raise') for k in cols[1:])
        if not (days.ge(0).all() and weekday.between(0,6).all() and month.between(1,12).all()):
            raise ValueError('Invalid calendar features')
        calendar = np.stack([ram, days/366., weekday/6., (month-1)/11.], axis=-1).astype(np.float32)
        if not np.isfinite(calendar).all():
            raise ValueError('Nonfinite calendar features')
    if prior_type == 'none':
        candidate = np.ones((n, n), dtype=bool)
    elif prior_type == 'bps':
        candidate = np.asarray(panel.mask, dtype=bool)
    else:
        raise ValueError(f'Unsupported prior: {prior_type}')
    print(f'Candidate prior={prior_type}; edges={candidate.sum()}; empty rows={(~candidate.any(axis=1)).sum()}')
    return (torch.as_tensor(edge, device=device).unsqueeze(0),
            torch.as_tensor(candidate, dtype=torch.bool, device=device), calendar, spec.horizons)

@torch.no_grad()
def evaluate(model, loader, device, prior=None):
    model.eval()
    total, count = 0.0, 0
    for batch in loader:
        x = batch['X'].to(device)
        y = batch['y'].to(device)
        mask = batch['y_mask'].to(device).bool()
        if not mask.any():
            continue
        pred = predict(model, batch, device, prior)[0].float().exp()
        errors = (pred[mask] - y[mask]).abs()
        if not torch.isfinite(errors).all():
            raise FloatingPointError('Nonfinite validation error')
        total += errors.double().sum().item()
        count += mask.sum().item()
    if not count:
        raise ValueError('No valid validation targets')
    return total / count


def fit(model, train_loader, val_loader, *, device, a_prior=None,
        lr=1e-3, epochs=200, patience=15, grad_clip=5.0, amp=True,
        checkpoint=None, entropy_lambda=0.0001):
    device = torch.device(device)
    if min(epochs, patience, lr, grad_clip) <= 0:
        raise ValueError('Training settings must be positive')
    model = model.to(device)
    prior = a_prior
    use_amp = amp and device.type == 'cuda'
    if device.type == 'cuda':
        torch.cuda.synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scaler = torch.amp.GradScaler('cuda', enabled=use_amp)
    best, best_state, best_epoch, stale = float('inf'), None, 0, 0
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        total, count = 0.0, 0
        ent_total = 0.0
        for batch in train_loader:
            x = batch['X'].to(device)
            y = batch['y'].to(device)
            mask = batch['y_mask'].to(device).bool()
            n = mask.sum().item()
            if not n:
                continue
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=use_amp):
                pred, a = predict(model, batch, device, prior)
            mae = masked_log_mae(pred, y, mask)
            entropy = model.entropy_regularizer(a)
            loss = mae + entropy_lambda * entropy
            if not torch.isfinite(loss):
                raise FloatingPointError('Nonfinite training loss')
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            scaler.step(optimizer)
            scaler.update()
            total += mae.item() * n
            count += n
            ent_total += entropy.item() * n
        if not count:
            raise ValueError('No valid training targets')
        val = evaluate(model, val_loader, device, prior)
        history.append({'epoch': epoch, 'train_log_mae': total/count, 'val_mae_rp': val, 'train_entropy': ent_total/count})
        print(f'Epoch {epoch:03d} | log MAE={total/count:.6f} | val MAE={val:.2f}')
        if val < best:
            best, best_epoch, stale = val, epoch, 0
            best_state = {k: v.detach().cpu().clone() for k,v in model.state_dict().items()}
        else:
            stale += 1
            if stale >= patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    if checkpoint is not None:
        from pathlib import Path
        path = Path(checkpoint)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({'model_state_dict': best_state, 'best_epoch': best_epoch, 'val_mae_rp': best}, path)
    allocated = reserved = None
    if device.type == 'cuda':
        torch.cuda.synchronize(device)
        allocated = torch.cuda.max_memory_allocated(device)/1e9
        reserved = torch.cuda.max_memory_reserved(device)/1e9
    return {'best_epoch': best_epoch, 'best_val_mae_rp': best, 'history': history,
            'peak_allocated_gb': allocated, 'peak_reserved_gb': reserved}



def main():
    p = argparse.ArgumentParser()
    p.add_argument('--batch-size', type=int)
    p.add_argument('--edge-features', type=Path)
    p.add_argument('--calendar-file', type=Path, help='Retrospective project calendar; synthetic prototype only')
    p.add_argument('--allow-provisional', action='store_true')
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--origin', choices=['O1','O2','O3'], default='O1')
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--epochs', type=int)
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--val-only', action='store_true', help='Do not evaluate test during tuning')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    args.model = 'module1'
    cfg = yaml.safe_load(Path('configs/models/module1.yaml').read_text())
    if not args.allow_provisional:
        p.error('Calendar convention is provisional; use --allow-provisional for prototype only')
    if args.data.resolve() != Path('data/synth/default').resolve():
        p.error('Only data/synth/default is allowed')
    if args.batch_size is not None:
        cfg['batch_size'] = args.batch_size
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required')
    glob = yaml.safe_load(Path('configs/global.yaml').read_text())
    if glob['target_transform'] != 'log_level' or args.seed not in glob['seeds']:
        raise ValueError('Protocol mismatch')
    if args.out.exists():
        raise FileExistsError(f'Use a new output directory: {args.out}')
    seed_everything(args.seed)
    panel = load_panel(args.data, unseal=False)
    spec = WindowSpec(window=glob['window'], horizons=tuple(glob['horizons']))
    split = rolling_origin(args.origin, panel.dates)
    loaders = {}
    eval_parts = ('val',) if args.val_only else ('val','test')
    for part in ('train', *eval_parts):
        ds = WindowDataset(panel, args.origin, part, spec)
        official = set(split_indices(split, panel.dates, part, horizon=max(spec.horizons)))
        keep = [i for i,k in enumerate(ds.decision_indices) if k in official]
        if args.smoke:
            keep = keep[:max(32, cfg['batch_size'])]
        if not keep:
            raise ValueError(f'Empty {part} intersection')
        print(f'{part}: {len(keep)} windows (official={len(official)})')
        loaders[part] = make_loader(Subset(ds, keep), batch_size=cfg['batch_size'], shuffle=part=='train')
    model = ClimateConditionedLagGraph(n_features=len(FEATURES), n_climate=5,
        n_edge_features=4, n_calendar_future=4, hidden=cfg['hidden'],
        n_lags=cfg['n_lags'], horizons=spec.horizons, null_option=True)
    # Initialize log-level head using only observed training labels.
    train = loaders['train'].dataset
    logs = []
    for item in train:
        logs.append(item['y'][item['y_mask']].log())
    center = torch.cat(logs).median().item()
    with torch.no_grad():
        model.head[-1].bias.fill_(center)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    prior = graph_context(panel, spec, device, args.edge_features, args.calendar_file, prior_type=cfg['prior'])
    if len(loaders['train'].dataset) < cfg['batch_size']:
        raise ValueError('Not enough windows for requested batch size')
    args.out.mkdir(parents=True)
    stats = fit(model, loaders['train'], loaders['val'], device=device, a_prior=prior,
                lr=cfg['lr'], epochs=args.epochs or (2 if args.smoke else cfg['epochs']),
                patience=cfg['patience'], grad_clip=cfg['grad_clip'], amp=cfg['amp'], checkpoint=args.out/'best.pt', entropy_lambda=cfg['entropy_lambda'])
    prices = asof_prices(panel)
    frames = []
    attention = []
    model.eval()
    with torch.no_grad():
        for part in eval_parts:
            for batch in loaders[part]:
                log_pred, a = predict(model, batch, device, prior)
                pred = log_pred.float().exp().cpu().numpy()
                valid = prior[1][None, :, :, None].expand_as(a)
                if not torch.isfinite(a).all() or (a[~valid] != 0).any():
                    raise ValueError('Invalid or unmasked attention')
                if not torch.allclose(a.float().sum((-1,-2)) + model.last_null_mass.float(), torch.ones_like(model.last_null_mass.float()), atol=1e-5):
                    raise ValueError('Attention plus null must sum to one')
                a = a.float().flatten(2)
                mass = a.sum(-1)
                q = a / mass.unsqueeze(-1).clamp_min(1e-12)
                ent = -(q*q.clamp_min(1e-12).log()).sum(-1)
                support = prior[1].sum(-1) * cfg['n_lags']
                eligible = (support[None, :] > 0) & (mass > 1e-12)
                normalizable = eligible & (support[None, :] > 1)
                norm_ent = ent / support.clamp_min(2).float().log()[None, :]
                attention.append(dict(part=part, rows=mass.numel(),
                    eligible_rows=eligible.sum().item(), eligible_entropy_sum=ent[eligible].sum().item(),
                    normalized_rows=normalizable.sum().item(), normalized_entropy_sum=norm_ent[normalizable].sum().item(),
                    conditional_entropy_sum=ent.sum().item(), null_mass_sum=(1-mass).sum().item(),
                    conditional_std_sum=q.std(-1, unbiased=False).sum().item()))
                for i,k in enumerate(batch['t_index'].tolist()):
                    for j,h in enumerate(spec.horizons):
                        frames.append(pd.DataFrame(dict(model=args.model,fold=args.origin,seed=args.seed,part=part,date=panel.dates[k],prov_code=panel.node_codes,h=h,y_true=batch['y'][i,j].numpy(),y_mask=batch['y_mask'][i,j].numpy(),y_pred=pred[i,j],naive_pred=prices.iloc[k].to_numpy())))
    result = pd.concat(frames, ignore_index=True)
    result.loc[~result.y_mask,'y_true'] = np.nan
    if not np.isfinite(result.loc[result.y_mask,'y_pred']).all():
        raise FloatingPointError('Nonfinite prediction')
    result.to_csv(args.out/'preds.csv',index=False)
    scores=[]
    for (part,h), group in result.groupby(['part','h']):
        common=group[group.y_mask & np.isfinite(group.naive_pred)]
        if common.empty:
            raise ValueError('No common evaluation targets')
        a=float((common.y_true-common.y_pred).abs().mean())
        b=float((common.y_true-common.naive_pred).abs().mean())
        scores.append(dict(part=part,h=int(h),n=len(common),model_mae=a,naive_mae=b,beats_naive=a<b))
    pd.DataFrame(attention).to_csv(args.out/'attention_batches.csv', index=False)
    stats['attention'] = {part: {key: sum(r[key] for r in attention if r['part']==part)/sum(r['rows'] for r in attention if r['part']==part) for key in ('conditional_entropy_sum','null_mass_sum','conditional_std_sum')} for part in eval_parts}
    for part in eval_parts:
        rows = [r for r in attention if r['part']==part]
        for name, numerator, denominator in [('eligible_entropy_mean','eligible_entropy_sum','eligible_rows'), ('normalized_entropy_mean','normalized_entropy_sum','normalized_rows')]:
            count = sum(r[denominator] for r in rows)
            stats['attention'][part][name] = sum(r[numerator] for r in rows)/count if count else None
    stats['candidate_edges'] = int(prior[1].sum().item())
    stats['candidate_empty_rows'] = int((~prior[1].any(-1)).sum().item())
    stats['candidate_counts_by_destination'] = prior[1].sum(-1).cpu().tolist()
    stats['val_only'] = args.val_only
    stats['provisional'] = True
    stats['edge_source'] = str(args.edge_features) if args.edge_features else 'BPS flag only; other channels zero'
    stats['calendar'] = ('target observation date; retrospective RAWIT calendar: is_ramadan, days_to_lebaran/366, dow/6, (month-1)/11' if args.calendar_file else 'target observation date; cyclic weekday and month')
    stats['calendar_source'] = str(args.calendar_file) if args.calendar_file else None
    stats.update(model=args.model,origin=args.origin,seed=args.seed,smoke=args.smoke,device=str(device),split_hash=panel.split_hash,config=cfg,epochs_requested=args.epochs or (2 if args.smoke else cfg['epochs']),scores=scores)
    (args.out/'summary.json').write_text(json.dumps(stats,indent=2))
    print(pd.DataFrame(scores).to_string(index=False))
    print('Peak GPU allocated/reserved:',stats['peak_allocated_gb'],stats['peak_reserved_gb'])
    print('RUN COMPLETE:',args.out)

if __name__=='__main__':
    main()
