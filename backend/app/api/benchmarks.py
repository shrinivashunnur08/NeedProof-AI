
from fastapi import APIRouter, Depends, Query, Response

from app.api.merchant_onboarding import local_only
from app.benchmarks.engine import run_benchmarks


router = APIRouter(
    prefix="/api/benchmarks",
    tags=["Benchmarking & Evaluation"],
    dependencies=[Depends(local_only)],
)


@router.get("/run")
def execute_benchmark(
    response: Response,
    seed: int = Query(default=42, ge=0, le=999999),
    basket_scenarios: int = Query(
        default=30, ge=1, le=80
    ),
    evidence_trials: int = Query(
        default=500, ge=10, le=2000
    ),
):
    response.headers["Cache-Control"] = "no-store"

    return run_benchmarks(
        seed=seed,
        basket_scenarios=basket_scenarios,
        evidence_trials=evidence_trials,
    )
