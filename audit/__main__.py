"""CLI: uv run --group audit python -m audit --models qwen2.5:72b,gpt-4o"""
from __future__ import annotations

import argparse
import datetime
from pathlib import Path

from audit.checks import build_checks
from audit.jury import run_jury
from audit.models import available_models, load_model_configs, make_client
from audit.report import render, _flagged

_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default="",
                    help="comma-separated model names (default: all available)")
    ap.add_argument("--vault-root", type=Path, default=_ROOT)
    ap.add_argument("--models-config", type=Path, default=_ROOT / "audit" / "models.yaml")
    args = ap.parse_args()

    only = [m.strip() for m in args.models.split(",") if m.strip()] or None
    configs = load_model_configs(args.models_config)
    if only:
        config_names = {c["name"] for c in configs}
        for name in only:
            if name not in config_names:
                print(f"warning: --models '{name}' matches no entry in models.yaml")
    clients = {}
    for cfg, ok in available_models(configs, only):
        if not ok:
            print(f"skip {cfg['name']}: {cfg.get('api_key_env')} not set")
            continue
        clients[cfg["name"]] = make_client(cfg)
    if not clients:
        raise SystemExit("no available models — check keys / --models filter")

    items = build_checks(args.vault_root)
    print(f"{len(items)} checks × {len(clients)} models: {', '.join(clients)}")
    results = run_jury(items, clients)

    date = datetime.date.today().isoformat()
    out = args.vault_root / "audit" / "reports" / f"{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(results, list(clients), date))
    flagged = sum(1 for _i, v in results if _flagged(v))
    print(f"wrote {out} — {flagged} rows flagged")


if __name__ == "__main__":
    main()
