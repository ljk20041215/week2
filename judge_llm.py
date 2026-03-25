#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

import call_llm


DEFAULT_JUDGE_SYSTEM = "You are a strict, expert judge for film storyboard quality."
AVAILABLE_JUDGE_MODELS = [
    "gpt-5.2",
    "claude-opus-4-1",
    "gpt-5-mini",
]
DEFAULT_JUDGE_RUBRIC = """你要评估的是“分镜是否适合后续输入 AI 视频生成模型”，不是文学好坏。

请按以下维度打分，1 到 5 分，5 分最好：
- plot_coverage: 剧情覆盖度
- shot_granularity: 镜头颗粒度
- temporal_clarity: 时序清晰度
- visual_executability: 视觉可执行性
- video_model_readability: 视频模型可理解性
- character_stability: 角色稳定性
- scene_consistency: 场景一致性
- action_generatability: 动作可拍性

评分原则：
- 只看是否适合视频生成，不看文采
- 如果某个版本更容易被视频模型理解，给更高分
- 如果某个版本有错误、无法使用、内容缺失严重，应该显著扣分

输出要求：
请严格输出 JSON，不要输出任何额外解释。JSON 结构如下：
{
  "winner": "模型名",
  "winner_reason": "一句话说明为什么",
  "scores": [
    {
      "model": "模型名",
      "scores": {
        "plot_coverage": 5,
        "shot_granularity": 4,
        "temporal_clarity": 5,
        "visual_executability": 5,
        "video_model_readability": 5,
        "character_stability": 4,
        "scene_consistency": 4,
        "action_generatability": 5
      },
      "total_score": 4.75,
      "advantages": ["..."],
      "problems": ["..."],
      "recommendation": "best_for_video_generation"
    }
  ]
}"""


def load_run_summary(run_dir: Path) -> dict:
    summary_file = run_dir / "summary.json"
    if not summary_file.exists():
        raise FileNotFoundError(f"Missing summary.json in {run_dir}")
    return json.loads(summary_file.read_text(encoding="utf-8"))


def build_judge_prompt(source_prompt: str, candidates: list[dict]) -> str:
    payload = {
        "source_prompt": source_prompt,
        "candidates": candidates,
        "rubric": DEFAULT_JUDGE_RUBRIC,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def parse_judge_output(answer: str) -> dict | None:
    try:
        return json.loads(answer)
    except json.JSONDecodeError:
        return None


def build_ranked_markdown(judge_payload: dict) -> str:
    lines = ["# Judge Ranking", ""]
    winner = judge_payload.get("winner")
    winner_reason = judge_payload.get("winner_reason")
    if winner:
        lines.append(f"- winner: {winner}")
    if winner_reason:
        lines.append(f"- reason: {winner_reason}")
    lines.append("")

    scores = judge_payload.get("scores", [])
    if isinstance(scores, list) and scores:
        sorted_scores = sorted(scores, key=lambda item: item.get("total_score", 0), reverse=True)
        lines.append("| Rank | Model | Total | Recommendation |")
        lines.append("| --- | --- | ---: | --- |")
        for idx, item in enumerate(sorted_scores, start=1):
            lines.append(
                f"| {idx} | {item.get('model', '')} | {item.get('total_score', '')} | {item.get('recommendation', '')} |"
            )
        lines.append("")

        for item in sorted_scores:
            lines.append(f"## {item.get('model', '')}")
            lines.append(f"- total: {item.get('total_score', '')}")
            lines.append(f"- recommendation: {item.get('recommendation', '')}")
            advantages = item.get("advantages", [])
            problems = item.get("problems", [])
            if advantages:
                lines.append("- advantages:")
                for advantage in advantages:
                    lines.append(f"  - {advantage}")
            if problems:
                lines.append("- problems:")
                for problem in problems:
                    lines.append(f"  - {problem}")
            lines.append("")

    return "\n".join(lines)


def find_latest_run_dir(base_dir: Path) -> Path | None:
    if not base_dir.exists():
        return None
    run_dirs = [p for p in base_dir.iterdir() if p.is_dir() and p.name.startswith("run_")]
    if not run_dirs:
        return None
    return sorted(run_dirs)[-1]


def prompt_for_judge_model(default_model: str | None) -> str:
    print("请选择 judge 模型（输入编号，直接回车使用默认）:")
    for index, model in enumerate(AVAILABLE_JUDGE_MODELS, start=1):
        marker = " [默认]" if model == default_model else ""
        print(f"  {index}. {model}{marker}")

    raw = input("选择: ").strip()
    if not raw:
        return default_model or AVAILABLE_JUDGE_MODELS[0]
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(AVAILABLE_JUDGE_MODELS):
            return AVAILABLE_JUDGE_MODELS[idx - 1]
    if raw in AVAILABLE_JUDGE_MODELS:
        return raw
    return default_model or AVAILABLE_JUDGE_MODELS[0]


def resolve_judge_model(judge_model_value: str | None) -> str | None:
    if judge_model_value:
        return judge_model_value
    try:
        return prompt_for_judge_model(None)
    except EOFError:
        return None


def main() -> int:
    call_llm.load_env_file()

    parser = argparse.ArgumentParser(description="Judge storyboard outputs saved by call_llm.py.")
    parser.add_argument("--run-dir", default=os.getenv("RUN_DIR"), help="Run directory, e.g. runs/run_YYYYMMDD_HHMMSS.")
    parser.add_argument("--base-dir", default=os.getenv("OUTPUT_DIR", "runs"), help="Base directory to search for latest run.")
    parser.add_argument("--judge-model", default=os.getenv("JUDGE_MODEL"), help="Judge model ID, e.g. gpt-5.2.")
    parser.add_argument("--url", default=os.getenv("API_URL", call_llm.DEFAULT_URL), help="API endpoint.")
    parser.add_argument("--api-key", default=os.getenv("API_KEY"), help="API key, or set API_KEY env var.")
    parser.add_argument("--timeout", type=int, default=120, help="Judge request timeout in seconds.")
    parser.add_argument("--insecure", action="store_true", help="Skip TLS certificate verification.")
    parser.add_argument("--raw", action="store_true", help="Print raw judge JSON only.")
    args = parser.parse_args()

    if not args.api_key:
        print("Missing API key. Pass --api-key or set API_KEY env var.", file=sys.stderr)
        return 1

    args.judge_model = resolve_judge_model(args.judge_model)
    if not args.judge_model:
        print("Missing judge model. Set JUDGE_MODEL in .env or pass --judge-model.", file=sys.stderr)
        return 1

    run_dir = Path(args.run_dir) if args.run_dir else find_latest_run_dir(Path(args.base_dir))
    if run_dir is None:
        print("Could not find a run directory. Pass --run-dir or generate outputs first.", file=sys.stderr)
        return 1

    try:
        summary = load_run_summary(run_dir)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    prompt = summary.get("prompt", "")
    results = summary.get("results", [])
    candidates = [
        {
            "model": item.get("model"),
            "answer": item.get("answer"),
            "error": item.get("error"),
            "elapsed": item.get("elapsed"),
        }
        for item in results
    ]

    judge_input = build_judge_prompt(prompt, candidates)
    context = call_llm.build_ssl_context(args.insecure or os.getenv("SSL_INSECURE") == "1")

    print(f"Judging run: {run_dir}", flush=True)
    answer, error_message = call_llm.call_model(
        api_url=args.url,
        api_key=args.api_key,
        model=args.judge_model,
        system_prompt=DEFAULT_JUDGE_SYSTEM,
        user_prompt=judge_input,
        stream=False,
        context=context,
        timeout=args.timeout,
        retries=1,
    )

    judge_result = {
        "model": args.judge_model,
        "error": error_message,
        "answer": answer,
    }

    (run_dir / "judge.json").write_text(json.dumps(judge_result, ensure_ascii=False, indent=2), encoding="utf-8")

    if answer:
        parsed = parse_judge_output(answer)
        if parsed is not None:
            (run_dir / "judge.parsed.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

    judge_lines = ["# Judge Result", ""]
    judge_lines.append(f"- model: {args.judge_model}")
    judge_lines.append(f"- status: {'ok' if not error_message else 'error'}")
    if error_message:
        judge_lines.append(f"- error: {error_message}")
    else:
        judge_lines.append("```text")
        judge_lines.append(answer or "")
        judge_lines.append("```")
    (run_dir / "judge.md").write_text("\n".join(judge_lines), encoding="utf-8")

    if args.raw:
        print(json.dumps(judge_result, ensure_ascii=False, indent=2))
        return 0

    if error_message:
        print(f"[Judge] failed: {error_message}")
        return 1

    print(answer or "")
    parsed = parse_judge_output(answer or "")
    if parsed is not None:
        (run_dir / "judge.ranking.md").write_text(build_ranked_markdown(parsed), encoding="utf-8")
    print(f"Saved judge outputs to: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
