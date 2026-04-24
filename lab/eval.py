import argparse
import sys
from pathlib import Path

from lab.report import SYSTEMS as REPORT_ORDER
from lab.report import markdown_table, table_matches


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(prog="python -m lab.eval")
    parser.add_argument("--split", choices=("dev", "check", "long"), default="dev")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--systems", default=",".join(REPORT_ORDER))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)
    if args.split == "check":
        root = Path(__file__).resolve().parents[1]
        report = __import__("json").loads((root / "reports" / "dev.json").read_text(encoding="utf-8"))
        readme = (root / "README.md").read_text(encoding="utf-8")
        problems = table_matches(readme, report)
        print(markdown_table(report))
        if problems:
            for problem in problems:
                print(problem)
            raise SystemExit(1)
        print("table ok")
        return
    from lab.run import run_dev

    systems = tuple(part.strip() for part in args.systems.split(",") if part.strip())
    unknown = [name for name in systems if name not in REPORT_ORDER]
    if unknown:
        raise SystemExit(f"неизвестные системы: {', '.join(unknown)}")
    if args.split == "long":
        from lab.long_tasks import LONG_TASKS

        root = Path(__file__).resolve().parents[1]
        run_dev(
            base_url=args.base_url,
            model=args.model,
            systems=systems,
            limit=args.limit,
            resume=args.resume,
            tasks=LONG_TASKS,
            report_path=root / "reports" / "long.json",
            failures_name="long_failures.jsonl",
        )
        return
    run_dev(base_url=args.base_url, model=args.model, systems=systems, limit=args.limit, resume=args.resume)


if __name__ == "__main__":
    main()
