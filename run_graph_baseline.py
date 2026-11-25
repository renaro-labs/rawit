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
from renaro.baselines.gwn import GraphWaveNetLite
from renaro.baselines.mtgnn import MTGNNLite
from renaro.train_loop import fit, seed_everything


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', choices=['gwn','mtgnn'], required=True)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--origin', choices=['O1','O2','O3'], default='O1')
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--epochs', type=int)
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    cfg = yaml.safe_load(Path(f'configs/models/{args.model}.yaml').read_text())
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
    for part in ('train','val','test'):
        ds = WindowDataset(panel, args.origin, part, spec)
        official = set(split_indices(split, panel.dates, part, horizon=max(spec.horizons)))
        keep = [i for i,k in enumerate(ds.decision_indices) if k in official]
        if args.smoke:
            keep = keep[:16]
        if not keep:
            raise ValueError(f'Empty {part} intersection')
        print(f'{part}: {len(keep)} windows (official={len(official)})')
        loaders[part] = make_loader(Subset(ds, keep), batch_size=cfg['batch_size'], shuffle=part=='train')
    cls = GraphWaveNetLite if args.model=='gwn' else MTGNNLite
    kwargs = {k:cfg[k] for k in ('hidden','n_layers','embedding_dim','dropout')}
    kwargs.update(n_nodes=glob['project']['n_nodes'], horizons=spec.horizons)
    kwargs.update(use_prior=cfg['use_prior']) if args.model=='gwn' else kwargs.update(top_k=cfg['top_k'])
    model = cls(len(FEATURES), **kwargs)
    # Initialize log-level head using only observed training labels.
    train = loaders['train'].dataset
    logs = []
    for item in train:
        logs.append(item['y'][item['y_mask']].log())
    center = torch.cat(logs).median().item()
    with torch.no_grad():
        model.output_head[-1].bias.fill_(center)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    prior = torch.as_tensor(panel.mask, dtype=torch.float32, device=device) if args.model=='gwn' and cfg['use_prior'] else None
    args.out.mkdir(parents=True)
    stats = fit(model, loaders['train'], loaders['val'], device=device, a_prior=prior,
                lr=cfg['lr'], epochs=args.epochs or (2 if args.smoke else cfg['epochs']),
                patience=cfg['patience'], grad_clip=cfg['grad_clip'], amp=cfg['amp'], checkpoint=args.out/'best.pt')
    prices = asof_prices(panel)
    frames = []
    model.eval()
    with torch.no_grad():
        for part in ('val','test'):
            for batch in loaders[part]:
                pred = model(batch['X'].to(device), prior).float().exp().cpu().numpy()
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
    stats.update(model=args.model,origin=args.origin,seed=args.seed,smoke=args.smoke,device=str(device),split_hash=panel.split_hash,config=cfg,epochs_requested=args.epochs or (2 if args.smoke else cfg['epochs']),scores=scores)
    (args.out/'summary.json').write_text(json.dumps(stats,indent=2))
    print(pd.DataFrame(scores).to_string(index=False))
    print('Peak GPU allocated/reserved:',stats['peak_allocated_gb'],stats['peak_reserved_gb'])
    print('RUN COMPLETE:',args.out)

if __name__=='__main__':
    main()
