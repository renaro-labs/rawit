"""Shared neural baseline training; log-level loss, level validation MAE."""
from __future__ import annotations
import copy
import random
import numpy as np
import torch


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def masked_log_mae(pred, y, mask):
    if pred.shape != y.shape or mask.shape != y.shape:
        raise ValueError('Prediction, target and mask shapes must match')
    mask = mask.bool()
    if not mask.any():
        raise ValueError('Empty target mask')
    target = y[mask].float()
    if not torch.isfinite(target).all() or (target <= 0).any():
        raise ValueError('Invalid observed target')
    return (pred[mask].float() - target.log()).abs().mean()


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
        pred = model(x, prior).float().exp()
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
        checkpoint=None):
    device = torch.device(device)
    if min(epochs, patience, lr, grad_clip) <= 0:
        raise ValueError('Training settings must be positive')
    model = model.to(device)
    prior = None if a_prior is None else torch.as_tensor(a_prior, dtype=torch.float32, device=device)
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
        for batch in train_loader:
            x = batch['X'].to(device)
            y = batch['y'].to(device)
            mask = batch['y_mask'].to(device).bool()
            n = mask.sum().item()
            if not n:
                continue
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=use_amp):
                pred = model(x, prior)
            loss = masked_log_mae(pred, y, mask)
            if not torch.isfinite(loss):
                raise FloatingPointError('Nonfinite training loss')
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            scaler.step(optimizer)
            scaler.update()
            total += loss.item() * n
            count += n
        if not count:
            raise ValueError('No valid training targets')
        val = evaluate(model, val_loader, device, prior)
        history.append({'epoch': epoch, 'train_log_mae': total/count, 'val_mae_rp': val})
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
