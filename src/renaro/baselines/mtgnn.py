"""Independent MTGNN-inspired lite baseline; output is log-price [B,H,N].
A[i,j] weights messages from j to i. Prior is intentionally ignored.
Kernel 2 with doubling dilations gives receptive field 2**n_layers.
"""
from __future__ import annotations
import torch
from torch import nn
from torch.nn import functional as F


class _MixHop(nn.Module):
    def __init__(self, hidden, depth=2, alpha=0.05):
        super().__init__()
        self.depth, self.alpha = depth, alpha
        self.proj = nn.Conv2d(hidden * (depth + 1), hidden, 1)

    def forward(self, x, a):
        h = x
        states = [x]
        for _ in range(self.depth):
            h = self.alpha * x + (1 - self.alpha) * torch.einsum('ij,bcjt->bcit', a, h)
            states.append(h)
        return self.proj(torch.cat(states, dim=1))


class _Block(nn.Module):
    def __init__(self, hidden, dilation, dropout):
        super().__init__()
        self.dilation = dilation
        self.filter = nn.Conv2d(hidden, hidden, (1, 2), dilation=(1, dilation))
        self.gate = nn.Conv2d(hidden, hidden, (1, 2), dilation=(1, dilation))
        self.forward_graph = _MixHop(hidden)
        self.reverse_graph = _MixHop(hidden)
        self.dropout = nn.Dropout(dropout)
        self.norm = nn.BatchNorm2d(hidden)
        self.skip = nn.Conv2d(hidden, hidden, 1)

    def forward(self, x, a, reverse):
        p = F.pad(x, (self.dilation, 0, 0, 0))
        z = self.dropout(torch.tanh(self.filter(p)) * torch.sigmoid(self.gate(p)))
        z = self.forward_graph(z, a) + self.reverse_graph(z, reverse)
        out = self.norm(x + z)
        return out, self.skip(out[..., -1:])


class MTGNNLite(nn.Module):
    def __init__(self, n_features: int, hidden: int = 32, n_layers: int = 4,
                 horizons: tuple[int, ...] = (5, 10, 20), dropout: float = 0.3,
                 *, n_nodes: int = 34, embedding_dim: int = 10, top_k: int = 10):
        super().__init__()
        if min(n_features, hidden, n_layers, n_nodes, embedding_dim) <= 0 or not horizons:
            raise ValueError('Invalid model dimensions')
        if not 1 <= top_k < n_nodes:
            raise ValueError('top_k must be between 1 and n_nodes-1')
        self.n_features, self.n_nodes = n_features, n_nodes
        self.horizons, self.top_k = tuple(horizons), top_k
        self.receptive_field = 2 ** n_layers
        self.E1 = nn.Parameter(torch.randn(n_nodes, embedding_dim) * 0.1)
        self.E2 = nn.Parameter(torch.randn(n_nodes, embedding_dim) * 0.1)
        self.lin1 = nn.Linear(embedding_dim, embedding_dim)
        self.lin2 = nn.Linear(embedding_dim, embedding_dim)
        self.input_proj = nn.Conv2d(n_features, hidden, 1)
        self.blocks = nn.ModuleList(_Block(hidden, 2**i, dropout) for i in range(n_layers))
        self.output_head = nn.Sequential(nn.ReLU(), nn.Conv2d(hidden, hidden, 1),
                                         nn.ReLU(), nn.Conv2d(hidden, len(horizons), 1))
        nn.init.zeros_(self.output_head[-1].bias)

    def learned_adjacency(self):
        u = torch.tanh(3 * self.lin1(self.E1))
        v = torch.tanh(3 * self.lin2(self.E2))
        scores = F.relu(torch.tanh(3 * (u @ v.T - v @ u.T)))
        scores = scores.masked_fill(torch.eye(self.n_nodes, device=scores.device, dtype=torch.bool), 0)
        values, indices = scores.topk(self.top_k, dim=-1)
        return torch.zeros_like(scores).scatter(-1, indices, values)

    @staticmethod
    def _normalize(a):
        a = a + torch.eye(a.shape[0], device=a.device, dtype=a.dtype)
        return a / a.sum(-1, keepdim=True)

    def forward(self, x: torch.Tensor, a_prior: torch.Tensor | None = None):
        if x.ndim != 4 or x.shape[2:] != (self.n_nodes, self.n_features) or x.shape[1] == 0:
            raise ValueError('X must have shape [B,T,N,F] with configured N,F')
        a = self.learned_adjacency()
        a, reverse = self._normalize(a), self._normalize(a.T)
        z = self.input_proj(x.permute(0, 3, 2, 1).contiguous())
        skip = None
        for block in self.blocks:
            z, s = block(z, a, reverse)
            skip = s if skip is None else skip + s
        return self.output_head(skip).squeeze(-1)
