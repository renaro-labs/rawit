import torch
from renaro.models.module1 import ClimateConditionedLagGraph

def main():
    torch.manual_seed(42)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    b,t,n = (32 if device.type=='cuda' else 2),60,34
    model = ClimateConditionedLagGraph(10,4).to(device)
    x = torch.randn(b,t,n,10,device=device)
    c = torch.randn(b,t,n,4,device=device)
    s = torch.randn(b,n,n,4,device=device)
    mask = torch.ones(n,n,dtype=torch.bool,device=device)
    mask[:,0] = False
    cal = torch.randn(b,3,4,device=device)
    if device.type=='cuda':
        torch.cuda.reset_peak_memory_stats()
    y,a = model(x,c,s,mask,cal)
    assert y.shape == (b,3,n)
    assert a.shape == (b,n,n,8)
    assert torch.isfinite(y).all() and torch.isfinite(a).all()
    assert (a[:,:,0,:]==0).all()
    assert torch.allclose(a.sum((-1,-2))+model.last_null_mass,torch.ones(b,n,device=device),atol=1e-5)
    z = torch.arange(1,61,device=device,dtype=torch.float32).reshape(1,60,1,1)
    assert torch.allclose(model.lagged_states(z).flatten(),torch.arange(58,18,-5,device=device,dtype=torch.float32))
    loss = y.square().mean()+1e-4*model.entropy_regularizer(a)
    loss.backward()
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
    print('Shapes, masking, normalization, lag order, backward: PASS')
    print('Entropy:',model.entropy_regularizer(a).item())
    if device.type=='cuda':
        print('Peak allocated bytes (forward + backward):',torch.cuda.max_memory_allocated())
    else:
        print('GPU memory DoD: NOT TESTED (CPU only)')

if __name__=='__main__':
    main()
