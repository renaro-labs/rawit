"""MLE-H2-02: climate-conditioned lag graph; A[i,j] is j -> i."""
from __future__ import annotations
import torch
from torch import nn
from renaro.contract import N_LAG_BINS


class ClimateConditionedLagGraph(nn.Module):
    def __init__(self, n_features: int, n_climate: int,
                 n_edge_features: int = 4, n_calendar_future: int = 4,
                 hidden: int = 64, n_lags: int = N_LAG_BINS,
                 horizons: tuple[int, ...] = (5, 10, 20),
                 null_option: bool = True, *,
                 forecast_aligned: bool = False, n_nodes: int | None = None):
        super().__init__()
        self.n_lags = n_lags
        self.horizons = tuple(horizons)
        self.null_option = null_option
        self.no_climate = False
        self.forecast_aligned = forecast_aligned
        self.edge_lag_bias = (
            nn.Parameter(torch.zeros(n_nodes, n_nodes, n_lags))
            if n_nodes is not None else None
        )
        if forecast_aligned:
            self.input_value = nn.Linear(n_features, hidden, bias=False)
        self.encoder = nn.GRU(n_features, hidden, batch_first=True)
        self.climate_mlp = nn.Sequential(nn.Linear(8*n_climate, hidden), nn.ReLU(), nn.Linear(hidden, hidden))
        self.edge_mlp = nn.Sequential(nn.Linear(n_edge_features, hidden), nn.ReLU(), nn.Linear(hidden, hidden))
        self.lag_emb = nn.Embedding(n_lags, hidden)
        self.scorer = nn.Sequential(nn.Linear(5*hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))
        self.value = nn.Linear(hidden, hidden)
        # Null is a zero message, with a learned destination-dependent score.
        self.null = nn.Parameter(torch.zeros(hidden))
        self.head = nn.Sequential(nn.Linear(2*hidden+n_calendar_future, hidden), nn.ReLU(), nn.Linear(hidden, len(horizons)))
        self.last_null_mass = None

    def lagged_states(self, z: torch.Tensor) -> torch.Tensor:
        b,t,n,h = z.shape
        bins = []
        for lag in range(self.n_lags):
            end = t-5*lag
            start = end-5
            bins.append(z[:,start:end].mean(1) if start >= 0 else z.new_zeros(b,n,h))
        return torch.stack(bins, dim=1)

    def graph(self, h, z_lag, e, s, candidate_mask, lag_mask=None):
        b,n,d = h.shape
        if s.ndim == 3:
            s = s.unsqueeze(0)
        edge = self.edge_mlp(s)
        # Split the first affine layer into five additive projections.
        # Exactly equivalent to concatenation, without a [B,N,N,L,5D] allocation.
        first = self.scorer[0]
        wi,wj,we,ws,wl = first.weight.split(d, dim=1)
        linear = torch.nn.functional.linear
        destination = linear(h, wi, first.bias)
        source = linear(h, wj) + linear(e, we)
        edge_scores = linear(edge, ws)
        lag = linear(self.lag_emb.weight, wl)
        dst, src = candidate_mask.to(device=h.device, dtype=torch.bool).nonzero(as_tuple=True)
        base = destination[:, dst] + source[:, src] + edge_scores[:, dst, src]
        # Score only allowed edges. Scatter back to the public dense layout.
        def score(edge_state, lag_state):
            return self.scorer[2](self.scorer[1](edge_state[:, :, None, :] + lag_state)).squeeze(-1)

        if dst.numel() * self.n_lags > n * n:
            from torch.utils.checkpoint import checkpoint

            scores = torch.cat([
                checkpoint(score, base, lag_bin, use_reentrant=False)
                if self.training and torch.is_grad_enabled() else score(base, lag_bin)
                for lag_bin in lag.split(1)
            ], dim=-1)
        else:
            scores = score(base, lag)
        logits = scores.new_full((b, n, n, self.n_lags), float("-inf"))
        if self.edge_lag_bias is not None:
            scores = scores + self.edge_lag_bias[dst, src].to(scores.dtype)
        logits[:, dst, src, :] = scores
        valid = candidate_mask.to(device=h.device,dtype=torch.bool)[None,:,:,None]
        if lag_mask is not None:
            valid = valid & lag_mask[None,None,None,:]
        flat = logits.masked_fill(~valid,float('-inf')).flatten(2)
        if self.null_option:
            null_logit = (h*self.null).sum(-1,keepdim=True) / d**0.5
            probs = torch.softmax(torch.cat([flat,null_logit],dim=-1),dim=-1)
            self.last_null_mass = probs[...,-1]
            a = probs[...,:-1].reshape(b,n,n,self.n_lags)
        else:
            if not torch.isfinite(flat).any(-1).all():
                raise ValueError('Every destination needs a valid candidate/lag without null')
            a = torch.softmax(flat,dim=-1).reshape(b,n,n,self.n_lags)
            self.last_null_mass = a.new_zeros(b,n)
        return a

    def forward(self, x, c, s, candidate_mask, cal_future):
        b,t,n,f = x.shape
        z, hn = self.encoder(x.transpose(1,2).reshape(b*n,t,f))
        h = hn[-1].reshape(b,n,-1)
        z = z.reshape(b,n,t,-1).transpose(1,2)
        z_lag = self.lagged_states(z)
        # c must contain only climate information available at forecast origin.
        # Represent each five-step bin by its mean; newest bin first.
        climate = []
        for l in range(8):
            end = t-5*l
            climate.append(c[:,end-5:end].mean(1) if end>=5 else c.new_zeros(b,n,c.shape[-1]))
        e = self.climate_mlp(torch.cat(climate,dim=-1))
        if self.no_climate:
            e = torch.zeros_like(e)
        lag_mask = (torch.arange(self.n_lags,device=x.device)+1)*5 <= t
        a = self.graph(h,z_lag,e,s,candidate_mask,lag_mask)
        k = len(self.horizons)
        if self.forecast_aligned:
            # The target observation is h-1 steps after the decision. Use
            # observed source states only, with the latest state as a proxy
            # when a short lag points beyond the decision.
            offsets = torch.tensor(self.horizons, device=x.device)[:, None] - 1
            delays = 5 * (torch.arange(self.n_lags, device=x.device) + 1)
            indices = (t - 1 + offsets - delays).clamp(0, t - 1)
            values = self.value(z[:, indices]) + self.input_value(x[:, indices])
            messages = torch.einsum('bijl,bkljd->bkid', a, values)
        else:
            messages = torch.einsum('bijl,bljd->bid', a, self.value(z_lag))
            messages = messages[:, None].expand(-1, k, -1, -1)
        hm = torch.cat([h[:, None].expand(-1, k, -1, -1), messages], dim=-1)
        cal = cal_future[:,:,None,:].expand(-1,-1,n,-1)
        outputs = self.head(torch.cat([hm,cal],dim=-1))
        yhat = outputs.diagonal(dim1=1,dim2=3).transpose(1,2).contiguous()
        return yhat,a

    def entropy_regularizer(self, a):
        p = a.float()
        entropy = -(p*p.clamp_min(1e-12).log()).sum(dim=(-1,-2))
        # Include null probability so low real-edge mass alone is not mistaken for low entropy.
        if self.null_option:
            q = (1-p.sum(dim=(-1,-2))).clamp(0,1)
            entropy = entropy-q*q.clamp_min(1e-12).log()
        return entropy.mean()


def ablation_variant(**kwargs):
    no_climate = kwargs.pop('no_climate',False)
    no_lag = kwargs.pop('no_lag',False)
    if no_lag:
        kwargs['n_lags'] = 1
    model = ClimateConditionedLagGraph(**kwargs)
    model.no_climate = no_climate
    return model


def run(panel, cfg, origin, seed):
    """RAWIT standard experiment registry entry point."""
    from renaro.models.module1_training import run_registered
    return run_registered(panel, cfg, origin, seed)
