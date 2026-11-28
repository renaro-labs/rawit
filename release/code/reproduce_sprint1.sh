#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/src"

SKIP_DATASET=0
SKIP_RQ0=0
SKIP_MODELS=0
SKIP_ABLATION=0
SKIP_ROBUSTNESS=0
SKIP_HOLDOUT=0
SKIP_TESTS=0
PLAN_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --skip-dataset) SKIP_DATASET=1 ;;
    --skip-rq0) SKIP_RQ0=1 ;;
    --skip-models) SKIP_MODELS=1 ;;
    --skip-ablation) SKIP_ABLATION=1 ;;
    --skip-robustness) SKIP_ROBUSTNESS=1 ;;
    --skip-holdout) SKIP_HOLDOUT=1 ;;
    --skip-tests) SKIP_TESTS=1 ;;
    --plan-only) PLAN_ONLY=1 ;;
    *) echo "unknown option: $arg"; exit 2 ;;
  esac
done

run() {
  if [ "$PLAN_ONLY" -eq 1 ]; then
    echo "[plan] $*"
  else
    echo "[run ] $*"
    "$@"
  fi
}

echo "RENARO RAWIT — Sprint 1 reproducible pipeline"
echo "repo: $ROOT"
echo "PYTHONPATH: $PYTHONPATH"

run python scripts/check_env.py

if [ "$SKIP_DATASET" -eq 0 ]; then
  if [ -f "data/processed/dataset_v1/VERSION" ]; then
    echo "[skip] data/processed/dataset_v1 sudah ada"
  else
    run python scripts/make_dataset.py --config configs/data/v1.yaml
  fi
fi

if [ "$SKIP_RQ0" -eq 0 ]; then
  registry="experiments/registry.csv"
  backup="experiments/registry.csv.rq0-backup"
  if [ -f "$registry" ]; then
    cp "$registry" "$backup"
    echo "[info] registry dibackup ke $backup (RQ0 menulis ulang registry)"
  fi
  trap 'if [ -f "$backup" ]; then mv "$backup" "$registry"; fi' EXIT
  run python scripts/run_rq0.py
  if [ -f "$backup" ]; then
    mv "$backup" "$registry"
    echo "[info] registry asli dikembalikan"
  fi
  trap - EXIT
fi

if [ "$SKIP_MODELS" -eq 0 ]; then
  MODELS="seasonal_naive,naive_last,lgbm_a,lgbm_c,gwn,mtgnn,latent_regime,lag_graph,module1,module23"
  run python scripts/run_gate2.py --models "$MODELS" --origins O1,O2,O3 --seeds 0,1,2,3,4
fi

if [ "$SKIP_ABLATION" -eq 0 ]; then
  for variant in full no_climate no_lag no_gate no_calendar; do
    for origin in O1 O2 O3; do
      for seed in 0 1 2 3 4; do
        run_dir="experiments/runs/ablation_${variant}_${origin}_s${seed}"
        if [ -d "$run_dir" ]; then
          echo "[skip] $run_dir sudah ada"
        else
          run python scripts/run_ablation.py --variant "$variant" --origin "$origin" --seed "$seed"
        fi
      done
    done
  done
  run python scripts/aggregate_ablation.py
fi

if [ "$SKIP_ROBUSTNESS" -eq 0 ]; then
  if [ -f "reports/robustness/robustness_val.csv" ]; then
    echo "[skip] reports/robustness/robustness_val.csv sudah ada"
  else
    run python scripts/robustness.py --mode both
  fi
fi

if [ "$SKIP_HOLDOUT" -eq 0 ]; then
  sealed="${RENARO_SEALED_DIR:-}"
  if [ -z "$sealed" ]; then
    echo "[skip] RENARO_SEALED_DIR belum diset; holdout tidak dijalankan"
  elif [ ! -f "$sealed/HOLDOUT_UNSEALED" ]; then
    echo "[skip] HOLDOUT_UNSEALED tidak ada; holdout tetap tersegel"
  elif [ -f "reports/holdout/predictions/predict_log.json" ]; then
    echo "[skip] prediksi holdout sudah ada; tidak dijalankan ulang"
  else
    run python scripts/predict.py --manifest frozen/manifest.yaml \
      --context data/processed/dataset_v1 \
      --holdout "$sealed/holdout_v1/panel_v1" \
      --out reports/holdout/predictions
  fi
fi

if [ "$SKIP_TESTS" -eq 0 ]; then
  run python -m pytest -q
fi

echo "SELESAI. Ringkasan: reports/rq0, reports/h5, reports/ablation, reports/robustness, reports/holdout"
