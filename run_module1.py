"""Run the Module 1 synthetic prototype and report attention diagnostics."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import yaml
from renaro.data.io import load_panel
from renaro.baselines.naive import asof_prices
from renaro.models.module1_training import fit, predict, prepare

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
    panel = load_panel(args.data, unseal=False)
    eval_parts = ('val',) if args.val_only else ('val', 'test')
    cfg.update(edge_features=args.edge_features, calendar_file=args.calendar_file)
    model, spec, loaders, device, prior = prepare(
        panel, cfg, glob, args.origin, args.seed, eval_parts, smoke=args.smoke,
    )
    cfg.update(
        edge_features=str(args.edge_features) if args.edge_features else None,
        calendar_file=str(args.calendar_file) if args.calendar_file else None,
    )
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
