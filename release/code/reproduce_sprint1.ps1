[CmdletBinding()]
param(
    [switch]$SkipDataset,
    [switch]$SkipRQ0,
    [switch]$SkipModels,
    [switch]$SkipAblation,
    [switch]$SkipRobustness,
    [switch]$SkipHoldout,
    [switch]$SkipTests,
    [switch]$PlanOnly
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root
$env:PYTHONPATH = (Join-Path $Root "src")

function Invoke-Step {
    param([string]$Command)
    if ($PlanOnly) {
        Write-Host "[plan] $Command"
        return
    }
    Write-Host "[run ] $Command" -ForegroundColor Cyan
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Command"
    }
}

Write-Host "RENARO RAWIT — Sprint 1 reproducible pipeline"
Write-Host "repo: $Root"
Write-Host "PYTHONPATH: $env:PYTHONPATH"

Invoke-Step "python scripts\check_env.py"

if (-not $SkipDataset) {
    if (Test-Path "data\processed\dataset_v1\VERSION") {
        Write-Host "[skip] data\processed\dataset_v1 sudah ada (pakai -SkipDataset untuk melewati cek ini)"
    } else {
        Invoke-Step "python scripts\make_dataset.py --config configs\data\v1.yaml"
    }
}

if (-not $SkipRQ0) {
    $registry = "experiments\registry.csv"
    $backup = "experiments\registry.csv.rq0-backup"
    if (Test-Path $registry) {
        Copy-Item $registry $backup -Force
        Write-Host "[info] registry dibackup ke $backup (RQ0 menulis ulang registry)"
    }
    try {
        Invoke-Step "python scripts\run_rq0.py"
    } finally {
        if (Test-Path $backup) {
            Move-Item $backup $registry -Force
            Write-Host "[info] registry asli dikembalikan"
        }
    }
}

if (-not $SkipModels) {
    $models = "seasonal_naive,naive_last,lgbm_a,lgbm_c,gwn,mtgnn,latent_regime,lag_graph,module1,module23"
    Invoke-Step "python scripts\run_gate2.py --models $models --origins O1,O2,O3 --seeds 0,1,2,3,4"
}

if (-not $SkipAblation) {
    $variants = @("full", "no_climate", "no_lag", "no_gate", "no_calendar")
    $origins = @("O1", "O2", "O3")
    $seeds = @(0, 1, 2, 3, 4)
    foreach ($variant in $variants) {
        foreach ($origin in $origins) {
            foreach ($seed in $seeds) {
                $run = "experiments\runs\ablation_${variant}_${origin}_s${seed}"
                if (Test-Path $run) {
                    Write-Host "[skip] $run sudah ada"
                } else {
                    Invoke-Step "python scripts\run_ablation.py --variant $variant --origin $origin --seed $seed"
                }
            }
        }
    }
    Invoke-Step "python scripts\aggregate_ablation.py"
}

if (-not $SkipRobustness) {
    if (Test-Path "reports\robustness\robustness_val.csv") {
        Write-Host "[skip] reports\robustness\robustness_val.csv sudah ada (pakai -SkipRobustness untuk melewati cek ini)"
    } else {
        Invoke-Step "python scripts\robustness.py --mode both"
    }
}

if (-not $SkipHoldout) {
    $sealed = $env:RENARO_SEALED_DIR
    if (-not $sealed) {
        Write-Host "[skip] RENARO_SEALED_DIR belum diset; holdout tidak dijalankan"
    } elseif (-not (Test-Path (Join-Path $sealed "HOLDOUT_UNSEALED"))) {
        Write-Host "[skip] HOLDOUT_UNSEALED tidak ada; holdout tetap tersegel"
    } elseif (Test-Path "reports\holdout\predictions\predict_log.json") {
        Write-Host "[skip] prediksi holdout sudah ada; tidak dijalankan ulang"
    } else {
        $holdoutPath = Join-Path $sealed "holdout_v1\panel_v1"
        $predictCmd = 'python scripts\predict.py --manifest frozen\manifest.yaml --context data\processed\dataset_v1 --holdout "{0}" --out reports\holdout\predictions' -f $holdoutPath
        Invoke-Step $predictCmd
    }
}

if (-not $SkipTests) {
    Invoke-Step "python -m pytest -q"
}

Write-Host "SELESAI. Ringkasan: reports\rq0, reports\h5, reports\ablation, reports\robustness, reports\holdout" -ForegroundColor Green
