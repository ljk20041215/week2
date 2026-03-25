#!/usr/bin/env python3
import argparse
import json
import os
import sys
import ssl
import time
from datetime import datetime
from pathlib import Path
from urllib import error, request


DEFAULT_URL = "https://api.qnaigc.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v3.2-251201"
DEFAULT_CERT_FILE = "/usr/local/etc/openssl@3/cert.pem"
AVAILABLE_MODELS = [
    "minimax/minimax-m2.5",
    "doubao-seed-2.0-pro",
    "claude-4.6-opus",
    "openai/gpt-5.4-nano",
]
DEFAULT_SCENE_PROMPT = """你是一个专业的导演，接下来这段剧本需要分镜后输入到ai视频生成模型中。外景 西部荒凉小镇街道 黄昏
风卷着沙尘掠过空无一人的主街。
残破的木招牌在风里吱呀作响。街道两侧的酒馆、马厩和杂货铺全都紧闭门窗，仿佛整个小镇都屏住了呼吸。
两个牛仔站在街道中央，背对背。
牛仔A神情冷静，手垂在枪套旁，指尖微微蜷起。
牛仔B额角渗汗，下颌绷紧，呼吸急促，却强撑着不肯示弱。
远处，一只铁皮桶被风吹得滚过街面，发出空洞的撞击声。
短暂的寂静后，一个低沉的声音响起。
裁决者（画外音）
一步，一步走。
五步之后，三秒。
三秒之后，生死由枪决定。
两人同时迈步。
靴跟踩进黄沙里，发出沉闷的声响。
牛仔B的喉结滚动了一下。
牛仔A的眼神依旧平静。
风更大了。
第五步落下，两人同时停住。
空气像凝固了一样。
一滴汗顺着牛仔B的太阳穴滑落。
牛仔A的右手手指轻轻一动。
三秒结束。
牛仔A猛然转身，动作快得几乎只剩下一道残影——拔枪、抬腕、瞄准，一气呵成。
与此同时，牛仔B才刚慌忙转身，手中的枪甚至还没来得及完全拔出枪套。
砰！
枪声炸裂，惊起屋檐上的乌鸦。
牛仔B手中的左轮枪被子弹精准击中。巨大的冲击让他五指瞬间失力，手枪旋转着飞入尘土。
牛仔B踉跄后退，捂住被震麻的手，满脸惊愕地看着牛仔A。
牛仔A稳稳举枪，枪口正对牛仔B的眉心，手臂没有一丝颤抖。
风吹起他的衣角。
牛仔A
回去练练。
等你手不抖了，再来找我。
牛仔B喘着粗气，盯着地上的枪，却不敢再动。
牛仔A缓缓压低枪口，没有继续开枪。
牛仔A
捡命走吧。
下一次，不会只是打飞你的枪。
牛仔B脸色发白，咬紧牙关，最终没有再反抗。
他后退一步，又一步，狼狈地转身离开。
牛仔A站在风沙里，收枪入套。
远处，夕阳把他的影子拉得很长。
切黑。上面的是给每一个分镜模型的提示词"""


def parse_models(models_value: str | None, single_model: str | None) -> list[str]:
    if models_value:
        models = [item.strip() for item in models_value.split(",")]
        models = [item for item in models if item]
        if models:
            return models

    if single_model:
        return [single_model]

    return [DEFAULT_MODEL]


def prompt_for_models(default_models: list[str]) -> list[str]:
    print("请选择要运行的模型（输入编号，多个用逗号分隔，直接回车使用默认）:")
    for index, model in enumerate(AVAILABLE_MODELS, start=1):
        marker = " [默认]" if model in default_models else ""
        print(f"  {index}. {model}{marker}")

    raw = input("选择: ").strip()
    if not raw:
        return default_models

    selected = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(AVAILABLE_MODELS):
                selected.append(AVAILABLE_MODELS[idx - 1])
            continue
        if token in AVAILABLE_MODELS:
            selected.append(token)

    deduped = []
    for model in selected:
        if model not in deduped:
            deduped.append(model)
    return deduped or default_models


def resolve_models(models_value: str | None, single_model: str | None) -> list[str]:
    if models_value:
        return parse_models(models_value, single_model)

    if single_model and single_model != DEFAULT_MODEL:
        return [single_model]

    default_models = [AVAILABLE_MODELS[0]]
    try:
        return prompt_for_models(default_models)
    except EOFError:
        return default_models


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_payload(system_prompt: str, user_prompt: str, model: str, stream: bool) -> dict:
    return {
        "stream": stream,
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }


def extract_answer(data: dict) -> str | None:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None

    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content

    text = first_choice.get("text")
    if isinstance(text, str):
        return text

    return None


def call_model(
    api_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    stream: bool,
    context: ssl.SSLContext | None,
    timeout: int,
    retries: int = 1,
) -> tuple[str | None, str | None]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = build_payload(system_prompt, user_prompt, model, stream)

    req = request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    last_error = None
    for attempt in range(retries + 1):
        try:
            with request.urlopen(req, timeout=timeout, context=context) as resp:
                raw_body = resp.read().decode("utf-8")
            break
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            error_message = f"HTTP {exc.code} {exc.reason}"
            if body:
                error_message = f"{error_message}\n{body}"
            return None, error_message
        except ssl.SSLError as exc:
            return None, f"TLS certificate verification error: {exc}"
        except (error.URLError, ConnectionResetError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            if attempt >= retries:
                return None, last_error
            time.sleep(1.0 * (attempt + 1))
    else:
        return None, last_error or "Unknown network error"

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        return None, f"Response is not valid JSON:\n{raw_body}"

    answer = extract_answer(data)
    if answer is None:
        return None, json.dumps(data, ensure_ascii=False, indent=2)

    return answer, None


def build_ssl_context(insecure: bool) -> ssl.SSLContext | None:
    if insecure:
        return ssl._create_unverified_context()

    cert_file = os.getenv("SSL_CERT_FILE")
    if cert_file and Path(cert_file).exists():
        return ssl.create_default_context(cafile=cert_file)

    if Path(DEFAULT_CERT_FILE).exists():
        return ssl.create_default_context(cafile=DEFAULT_CERT_FILE)

    return ssl.create_default_context()


def sanitize_filename(name: str) -> str:
    safe = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_", "."}:
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe)


def ensure_run_dir(base_dir: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(base_dir) / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_run_outputs(run_dir: Path, prompt: str, system_prompt: str, results: list[dict]) -> None:
    payload = {
        "prompt": prompt,
        "system_prompt": system_prompt,
        "results": results,
    }
    (run_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = ["# LLM Run Summary", ""]
    md_lines.append("## Prompt")
    md_lines.append("```text")
    md_lines.append(prompt)
    md_lines.append("```")
    md_lines.append("")
    md_lines.append("## Results")
    for item in results:
        md_lines.append(f"### {item['model']}")
        md_lines.append(f"- status: {'ok' if not item['error'] else 'error'}")
        if item.get("elapsed") is not None:
            md_lines.append(f"- elapsed: {item['elapsed']:.1f}s")
        if item["error"]:
            md_lines.append(f"- error: {item['error']}")
        else:
            md_lines.append("```text")
            md_lines.append(item["answer"] or "")
            md_lines.append("```")
        md_lines.append("")

    (run_dir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")

    for item in results:
        model_file = run_dir / f"{sanitize_filename(item['model'])}.json"
        model_file.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    load_env_file()

    parser = argparse.ArgumentParser(description="Call an LLM chat completions API.")
    parser.add_argument("--api-key", default=os.getenv("API_KEY"), help="API key, or set API_KEY env var.")
    parser.add_argument(
        "--url",
        default=os.getenv("API_URL", DEFAULT_URL),
        help=f"API endpoint, default: {os.getenv('API_URL', DEFAULT_URL)}",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("MODEL", DEFAULT_MODEL),
        help=f"Model name, default: {os.getenv('MODEL', DEFAULT_MODEL)}",
    )
    parser.add_argument(
        "--models",
        default=os.getenv("MODELS"),
        help="Comma-separated model list. If set, the prompt will be sent to each model.",
    )
    parser.add_argument("--system", default="You are a helpful assistant.", help="System prompt.")
    parser.add_argument(
        "--prompt",
        default=None,
        help="User prompt. If omitted, the built-in western duel prompt will be used.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Ask for a prompt in the terminal instead of using the built-in prompt.",
    )
    parser.add_argument("--stream", action="store_true", help="Enable streaming flag in request payload.")
    parser.add_argument("--raw", action="store_true", help="Print full JSON response instead of extracted answer.")
    parser.add_argument("--insecure", action="store_true", help="Skip TLS certificate verification.")
    parser.add_argument("--timeout", type=int, default=120, help="Per-model request timeout in seconds.")
    parser.add_argument("--save-dir", default=os.getenv("OUTPUT_DIR", "runs"), help="Directory to save run outputs.")
    args = parser.parse_args()

    if not args.api_key:
        print("Missing API key. Pass --api-key or set API_KEY env var.", file=sys.stderr)
        return 1

    if args.prompt is None:
        try:
            if args.interactive:
                print("请输入要发送给模型的内容:", end=" ", flush=True)
                args.prompt = input().strip()
            else:
                args.prompt = DEFAULT_SCENE_PROMPT
        except EOFError:
            args.prompt = ""

    if not args.prompt:
        print("No prompt provided.", file=sys.stderr)
        return 1

    models = resolve_models(args.models, args.model)
    context = build_ssl_context(args.insecure or os.getenv("SSL_INSECURE") == "1")
    results = []
    total = len(models)
    run_dir = ensure_run_dir(args.save_dir)

    for index, model_name in enumerate(models, start=1):
        print(f"[{index}/{total}] Calling {model_name} ...", flush=True)
        start_ts = time.time()
        answer, error_message = call_model(
            api_url=args.url,
            api_key=args.api_key,
            model=model_name,
            system_prompt=args.system,
            user_prompt=args.prompt,
            stream=args.stream,
            context=context,
            timeout=args.timeout,
        )
        elapsed = time.time() - start_ts
        if error_message:
            print(f"[{index}/{total}] {model_name} failed after {elapsed:.1f}s", flush=True)
        else:
            print(f"[{index}/{total}] {model_name} finished in {elapsed:.1f}s", flush=True)
        results.append(
            {
                "model": model_name,
                "answer": answer,
                "error": error_message,
                "elapsed": elapsed,
            }
        )

    if args.raw:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        write_run_outputs(run_dir, args.prompt, args.system, results)
        print(f"Saved run outputs to: {run_dir}")
        return 0

    for item in results:
        print(f"\n=== {item['model']} ===")
        if item["error"]:
            print(f"[ERROR] {item['error']}")
            continue
        print(item["answer"])

    write_run_outputs(run_dir, args.prompt, args.system, results)
    print(f"\nSaved run outputs to: {run_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
