"""MLE-H1-02 — synthetic climate-lag DGP. Graph orientation: G[dst, src]."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class SynthConfig:
    n_nodes: int = 34
    n_steps: int = 2400
    n_lags: int = 8
    density: float = 0.14
    noise_sd: float = 0.02
    seed: int = 0
    mode: str = 'conditioned'
    rho: float = 0.35
    beta: float = 0.20
    kappa: float = 1.5


def sample_graph(cfg, rng, bps_mask=None):
    if bps_mask is not None:
        g = np.asarray(bps_mask)
        if g.shape != (cfg.n_nodes, cfg.n_nodes) or not np.isin(g, [0, 1]).all():
            raise ValueError('Invalid BPS mask')
        g = g.astype(np.uint8).copy()
    else:
        g = (rng.random((cfg.n_nodes, cfg.n_nodes)) < cfg.density).astype(np.uint8)
    np.fill_diagonal(g, 0)
    return g


def sample_lags(cfg, graph, rng):
    normal = np.where(graph, rng.integers(1, min(4, cfg.n_lags)+1, graph.shape), 0)
    dry = np.where(graph, np.minimum(normal+2, cfg.n_lags), 0) if cfg.mode == 'conditioned' else normal.copy()
    return normal, dry


def sample_climate(cfg, rng):
    T, N = cfg.n_steps, cfg.n_nodes
    dry = np.zeros((T, N), dtype=bool)
    for j in range(N):
        t = int(rng.integers(0, 40))
        budget = int(T * .30)
        while t+10 <= T and budget >= 10:
            length = min(int(rng.integers(10, 41)), budget, T-t)
            dry[t:t+length, j] = True
            budget -= length
            t += length + int(rng.integers(65, 121))
    c = np.zeros((T, N))
    innovations = rng.normal(0, .8, (T, N))
    phase = rng.uniform(0, 2*np.pi, N)
    for t in range(T):
        c[t] = (.25*c[t-1] if t else 0) + innovations[t] + .08*np.sin(2*np.pi*t/260+phase)
    c -= .55*dry
    return c, dry


def simulate(cfg, bps_mask=None):
    if cfg.mode not in ('conditioned', 'unconditioned') or cfg.n_lags < 1 or cfg.n_steps < 1 or cfg.n_nodes < 2:
        raise ValueError('Invalid configuration')
    rng = np.random.default_rng(cfg.seed)
    G = sample_graph(cfg, rng, bps_mask)
    ln, ld = sample_lags(cfg, G, rng)
    c, dry = sample_climate(cfg, rng)
    T,N,L = cfg.n_steps,cfg.n_nodes,cfg.n_lags
    i,j = np.nonzero(G)
    # Bound incoming sum to keep feedback stable.
    weights = rng.uniform(.15,.30,len(i)) / np.maximum(1, np.bincount(i,minlength=N)[i])
    normal_delay, dry_delay = 5*ln[i,j], 5*ld[i,j]
    x = np.zeros((T,N)); u = np.zeros_like(x)
    A = np.zeros((T,N,N,L),dtype=np.float32)
    eps = rng.normal(0,cfg.noise_sd,(T,N))
    phase = rng.uniform(0,2*np.pi,N)
    for t in range(T):
        sn, sd = t-normal_delay, t-dry_delay
        valid_n = (sn>=0) & ~dry[np.maximum(sn,0),j]
        valid_d = (sd>=0) & dry[np.maximum(sd,0),j]
        # At transitions both candidates may be valid or neither. Dry wins ties;
        # no contribution in gaps. This is an explicit convention, not in starter.
        active = valid_d | valid_n
        source = np.where(valid_d,sd,sn)
        lag = np.where(valid_d,ld[i,j],ln[i,j])
        a = (weights*np.where(valid_d,cfg.kappa,1)).astype(np.float32)
        A[t,i[active],j[active],lag[active]-1] = a[active]
        incoming = np.bincount(i[active],weights=a[active]*u[source[active],j[active]],minlength=N)
        prev = x[t-1] if t else 0
        x[t] = cfg.rho*prev + incoming + .005*np.sin(2*np.pi*t/260+phase) + eps[t]
        u[t] = -cfg.beta*c[t] + x[t]-prev
    return dict(G=G,lag_normal=ln,lag_dry=ld,dry=dry,A_true=A,x=x,u=u,climate=c,cfg=cfg)


def sanity_xcorr(result, out_png):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    r=result; cfg=r['cfg']; T=cfg.n_steps
    delays=np.arange(1,5*cfg.n_lags+1); rows=[]
    # Use a fixed set of arrival times for each regime, defined by the actual
    # active edge lag and source state, never by the candidate correlation lag.
    for i,j in zip(*np.nonzero(r['G'])):
        curves=[]; peaks=[]; counts=[]
        for is_dry,key in [(False,'lag_normal'),(True,'lag_dry')]:
            lag=int(r[key][i,j]); expected=5*lag
            t=np.arange(5*cfg.n_lags,T)
            t=t[(r['A_true'][t,i,j,lag-1]!=0)&(r['dry'][t-expected,j]==is_dry)]
            counts.append(len(t))
            if len(t)<30: curves.append(np.full(len(delays),np.nan)); peaks.append(None); continue
            y=r['x'][t,i]; z=r['u'][t[:,None]-delays,j]
            y=y-y.mean(); z=z-z.mean(axis=0)
            den=np.sqrt((y*y).sum()*(z*z).sum(axis=0))
            corr=np.divide(y@z,den,out=np.full(len(delays),np.nan),where=den>0)
            curves.append(corr); peaks.append(int(delays[np.nanargmax(corr)]) if np.isfinite(corr).any() else None)
        expected=[5*int(r[k][i,j]) for k in ('lag_normal','lag_dry')]
        rows.append(dict(i=int(i),j=int(j),expected=expected,peaks=peaks,counts=counts,passed=peaks==expected,curves=curves))
    # Select first three passing edges in matrix order; disclose full results.
    chosen=[q for q in rows if q['passed']][:3]
    chosen += [q for q in rows if not q['passed']][:3-len(chosen)]
    fig,axes=plt.subplots(3,1,figsize=(10,9),sharex=True)
    for ax,q in zip(axes,chosen):
        for k,label,color in [(0,'Normal','tab:blue'),(1,'Dry','tab:orange')]:
            ax.plot(delays,q['curves'][k],label=f'{label}: peak={q["peaks"][k]}, n={q["counts"][k]}',color=color)
            ax.axvline(q['expected'][k],ls='--',color=color)
        ax.set_title(f'Edge {q["j"]} → {q["i"]} | '+('PASS' if q['passed'] else 'FAIL'))
        ax.set_ylabel('Pearson r'); ax.legend(); ax.grid(alpha=.2)
    axes[-1].set_xlabel('Lag (timestep; 5 = 1 pentad)')
    fig.suptitle(f'{cfg.mode}, seed={cfg.seed} — selected examples; {sum(q["passed"] for q in rows)}/{len(rows)} edges pass')
    fig.tight_layout(); out_png=Path(out_png); out_png.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(out_png,dpi=150); plt.close(fig)
    report=dict(mode=cfg.mode,seed=cfg.seed,total_edges=len(rows),passing_edges=sum(q['passed'] for q in rows),selected=[{k:v for k,v in q.items() if k!='curves'} for q in chosen],all_edges=[{k:v for k,v in q.items() if k!='curves'} for q in rows])
    out_png.with_suffix('.json').write_text(json.dumps(report,indent=2))
    return report


def export(result, out, provinces):
    r=result; cfg=r['cfg']; T,N=cfg.n_steps,cfg.n_nodes
    ref=pd.read_csv(provinces,dtype={'prov_code':str})
    if 'node_id' in ref: ref=ref.sort_values('node_id')
    codes=ref['prov_code'].str.zfill(2).to_numpy()
    if len(codes)!=N or len(set(codes))!=N: raise ValueError('Province mapping mismatch')
    dates=pd.bdate_range('2017-01-02',periods=T)
    c=pd.DataFrame(r['climate']); spells=np.zeros((T,N),int)
    for t in range(T): spells[t]=np.where(r['dry'][t],(spells[t-1] if t else 0)+1,0)
    panel=pd.DataFrame(dict(date=np.repeat(dates,N),prov_code=np.tile(codes,T),price=(40000*np.exp(r['x'])).ravel(),is_observed=True,rain_pentad_anom=c.rolling(5,min_periods=1).mean().to_numpy().ravel(),rain_30d_anom=c.rolling(30,min_periods=1).mean().to_numpy().ravel(),dry_spell_days=spells.ravel(),extreme_5d=False,roni=0.,is_ramadan=False,days_to_lebaran=np.nan,dow=np.repeat(dates.day_of_week,N),month=np.repeat(dates.month,N)))
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    panel.to_parquet(out/'panel.parquet',index=False)
    panel[['date','prov_code','price','is_observed']].to_parquet(out/'target.parquet',index=False)
    np.savez_compressed(out/'truth.npz',**{k:r[k] for k in ('G','lag_normal','lag_dry','dry','A_true','x','u','climate')},prov_code=codes.astype(str))


def main():
    import argparse
    import yaml
    ap=argparse.ArgumentParser(description='Synthetic climate-lag generator')
    ap.add_argument('--mode',choices=['conditioned','unconditioned'],default='conditioned')
    ap.add_argument('--seed',type=int,default=0)
    ap.add_argument('--out',type=Path,default=Path('data/synth'))
    ap.add_argument('--bps-mask',type=Path)
    ap.add_argument('--provinces',type=Path,default=Path('data/ref/provinces.csv'))
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args(); cfg=SynthConfig(seed=args.seed,mode=args.mode)
    mask=np.load(args.bps_mask,allow_pickle=False) if args.bps_mask else None
    r=simulate(cfg,mask); repeat=simulate(cfg,mask)
    assert all(np.array_equal(r[k],repeat[k]) for k in ('G','lag_normal','lag_dry','dry','A_true','x','u','climate'))
    del repeat
    assert np.all(r['dry'].mean(axis=0)<=.30)
    if cfg.mode=='unconditioned': assert np.array_equal(r['lag_normal'],r['lag_dry'])
    name='default' if cfg.mode=='conditioned' else 'unconditioned'
    png=Path('reports/synth')/('sanity_xcorr.png' if name=='default' else 'sanity_xcorr_unconditioned.png')
    report=sanity_xcorr(r,png)
    print('Determinism PASS; selected:',report['selected'])
    if not args.check_only:
        export(r,args.out/name,args.provinces)
        config=Path('configs/synth')/(name+'.yaml'); config.parent.mkdir(parents=True,exist_ok=True)
        config.write_text(yaml.safe_dump({**asdict(cfg),'bps_mask':str(args.bps_mask) if args.bps_mask else None},sort_keys=False))
    if len(report['selected'])!=3 or not all(q['passed'] for q in report['selected']): raise SystemExit('Cross-correlation DoD failed')

if __name__=='__main__': main()
