# week2

这个目录包含一套用于“多模型分镜生成 + Judge 评分”的脚本流程。

## 快速开始

1. 配置 `/.env`
2. 运行 `python3 call_llm.py`
3. 在终端里选择要对比的模型
4. 运行 `python3 judge_llm.py`
5. 查看 `runs/` 目录里的 `judge.ranking.md`

## 文件说明

- [`call_llm.py`](/Users/kun/Desktop/week2/call_llm.py)
  - 负责调用多个文本模型生成分镜结果
  - 会把每个模型的输出保存到 `runs/` 目录

- [`judge_llm.py`](/Users/kun/Desktop/week2/judge_llm.py)
  - 负责读取某一轮生成结果
  - 调用 judge 模型对各版本分镜做评分和排序

- [`分镜评定标准.md`](/Users/kun/Desktop/week2/分镜评定标准.md)
  - 分镜评估标准说明
  - judge prompt 参考文档

## 环境配置

只需要在同目录准备 `/.env`，保留接口相关配置即可：

```env
API_KEY=你的APIKey
API_URL=https://api.qnaigc.com/v1/chat/completions
SSL_INSECURE=1
```

说明：

- `API_KEY` 是必需的
- `API_URL` 默认就是上面的地址
- `SSL_INSECURE=1` 是本地临时绕过证书校验用的，如果你的环境证书正常，也可以去掉
- 不需要在 `.env` 里写模型列表，脚本会在运行时让你选择

## 运行生成脚本

直接运行：

```bash
python3 call_llm.py
```

脚本会在终端里让你选择本轮要跑的模型。

如果你想只跑单个模型，也可以直接传参：

```bash
python3 call_llm.py --model openai/gpt-5.4-nano
```

如果你想手动指定多个模型：

```bash
python3 call_llm.py --models minimax/minimax-m2.5,doubao-seed-2.0-pro
```

如果不传 `--prompt`，脚本会默认使用内置的西部牛仔分镜提示词。

## 运行 Judge

在生成结果后，再运行：

```bash
python3 judge_llm.py
```

脚本会默认找 `runs/` 目录下最新的一轮结果。

如果你想指定某一轮结果：

```bash
python3 judge_llm.py --run-dir runs/run_20260325_153012
```

如果你想手动指定 judge 模型：

```bash
python3 judge_llm.py --judge-model gpt-5.2
```

## 输出目录

每次运行生成脚本后，都会在 `runs/` 下生成一个新的目录，例如：

```text
runs/run_20260325_153012
```

常见输出文件包括：

- `summary.json`
- `summary.md`
- 各模型单独结果的 `*.json`
- `judge.json`
- `judge.parsed.json`
- `judge.md`
- `judge.ranking.md`

## 推荐流程

1. 运行 `call_llm.py`
2. 在终端里选择要对比的模型
3. 生成完成后运行 `judge_llm.py`
4. 查看 `judge.ranking.md` 和 `judge.parsed.json`

## 注意事项

- 这个流程默认是“运行时选模型”，不需要把模型列表写死在 `.env`
- 如果你在 PyCharm 里运行，确保 Run Console 能接收输入
- 如果某个模型报错，不影响其他模型继续跑
