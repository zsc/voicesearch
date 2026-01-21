下面是一份**可直接交给 codex / gemini-cli 开工**、且**不带 mock、拿到 HF token 就能跑通**的 **VoiceSearch（Voice Design Prompt Search）** SPEC。它是在你 SoulSearch（T2I）闭环基础上，把“prompt”换成 **voice description / instruct**，把“出图”换成 **Qwen3-TTS-Voice-Design 产 wav**，再由人类评分迭代。

> 核心依赖与可行性依据

* `gradio_client.Client(..., hf_token=...)` 可把任意 Gradio Space 当远程 API 调用，并且默认会使用本地保存的 HF token（如已登录/保存）。([gradio.app][1])
* `huggingface_hub.InferenceClient` 支持 `api_key`/`token` 鉴权（`api_key` 是 `token` 的别名），并提供 OpenAI 兼容的 chat completion 调用接口（`client.chat.completions.create`）。([Hugging Face][2])
* Voice Design 的“可控维度”主要来自**自然语言 voice_prompt/voice description**（例如 timbre、情绪、语速、口音、风格等），官方 API 文档强调 voice_prompt 的写法与约束（中/英、长度等）。([阿里云][3])

---

# VoiceSearch（Text-to-Voice Prompt Search）SPEC（可直接实现）

## 1. 项目概述

VoiceSearch 是一个**交互式 voice description（instruct）搜索工具**：每次会话 fresh start，不加载历史偏好。用户听每轮生成的多个 wav 并评分/选最喜欢，系统将“instruct + 反馈”回灌给 LLM，让 LLM 生成下一轮更符合当下偏好的 instruct，迭代多轮快速收敛到用户想要的声音风格。

闭环：

1. LLM 生成 instruct 候选（voice description）
2. 调用 **HF Space：`Qwen/Qwen3-TTS-Voice-Design`** 产 wav
3. 人类评分/选 best/写偏好
4. LLM 基于会话记录生成下一轮 instruct（带 exploitation + exploration）
5. 去重：会话内避免相似 instruct 反复出现（embedding 相似度阈值）

---

## 2. 目标与非目标

### 2.1 目标

* 快速收敛到“本次会话用户偏好”的声音（timbre/情绪/语速/口音/风格/清晰度等）
* UI 极简：**听音频 → 打分/Best → 下一轮**
* 保持探索：避免只沿一条路越走越窄
* instruct 去重：同会话内避免高度相似 instruct

### 2.2 非目标

* 不建立跨会话长期用户画像（fresh start）
* 不做 RLHF 训练管线（只做在线迭代搜索）
* 不要求自动客观指标（MOS 等），以人类偏好为主（可选后续加）

---

## 3. 可被 LLM 修改的“搜索空间”

> 你要“想下哪些东西可以被 LLM 修改，然后送给 Qwen3-TTS-Voice-Design 产 wav”。这里给一套**可控维度清单 + 约束策略**。

### 3.1 默认可变（LLM 每轮主要优化）

**instruct（voice description）**：描述“怎么说”，包含：

* 人设/声线：性别、年龄段、音色明暗、磁性/清亮、鼻音/气声、沙哑度、厚度
* 情绪与能量：开心/冷静/严肃/温柔/俏皮/疲惫/愤怒/悲伤、能量高低
* 语速与节奏：快慢、停顿频率、句尾拖音/利落
* 口音与发音倾向：普通话/播音腔/轻微方言口音/英音美音等（与语言匹配）
* 表达风格：新闻播报、纪录片旁白、客服、动漫角色、ASMR、舞台主持、播客聊天等
* 音频呈现偏好（尽量以描述表达）：更清晰、更近讲、少混响、更干净背景

> 文档层面的限制/建议：voice_prompt/描述建议中英、长度上限、要具体不模糊等（我们沿用这个写法原则给 instruct）。([阿里云][3])

### 3.2 可选可变（由用户开关控制）

* **preview_text（合成文本）**：默认锁定为同一句“测试脚本”，保证可比性；用户可解锁让 LLM 也提出“标点/停顿优化版本”（只改标点、分句，不改语义），用于控制韵律。
* **语言**：用户选择 zh/en/…（与合成文本一致）；Voice design 相关 API 文档列了支持语言（zh/en/de/…）。([阿里云][3])

### 3.3 不允许 LLM 修改（除非用户明确允许）

* 不生成受版权约束的“模仿某个在世名人/特定配音演员”的请求（可以让用户用“像 XX 类型”的抽象描述，但避免明确指名模仿真实公众人物声线）
* 不改动系统安全/合规策略（例如不要输出违法内容）

---

## 4. 系统架构（无 mock，直接跑）

* 后端：Python FastAPI（端口 8000）
* 前端：HTML + 少量 JS（fetch API）
* 会话存储：内存 dict（fresh start）；同时写临时文件 `/tmp/voicesearch_<session_id>.json` 方便导出
* 音频缓存：`data/sessions/<session_id>/iter_<n>/cand_<m>.wav`
* LLM：`huggingface_hub.InferenceClient` 调用 `Qwen/Qwen2.5-72B-Instruct`（HF token 鉴权）([Hugging Face][2])
* TTS：`gradio_client.Client("Qwen/Qwen3-TTS-Voice-Design", hf_token=HF_TOKEN)` 调用 Space API ([gradio.app][1])

  * 说明：gradio_client 默认会使用本地保存的 token；这里显式传入也行。([gradio.app][1])

---

## 5. 目录结构（建议）

```
voicesearch/
  app.py
  requirements.txt
  core/
    config.py
    models.py              # Pydantic: Session/Iteration/Candidate/Feedback
    storage.py             # In-memory + file snapshot
    llm_service.py         # Qwen2.5-72B-Instruct via InferenceClient
    tts_service.py         # Qwen3-TTS-Voice-Design via gradio_client
    dedup.py               # embedding + cosine sim
    prompt_templates/
      next_instruct_v1.txt # LLM system+user template（版本化）
  web/
    templates/
      index.html
      session.html
    static/
      main.js
      style.css
  data/                    # runtime created
```

---

## 6. 数据模型（会话日志，可导出）

### 6.1 Session JSON（导出）

```json
{
  "session_id": "VS_20260121_001",
  "created_at": "2026-01-21T19:00:00Z",
  "tts_space": {"repo": "Qwen/Qwen3-TTS-Voice-Design"},
  "llm_model": {"repo": "Qwen/Qwen2.5-72B-Instruct"},
  "settings": {
    "language": "zh",
    "preview_text": "你好，这是一个语音风格搜索测试。请保持自然清晰。",
    "candidates_per_iter": 3,
    "lock_text": true,
    "max_iters": 20,
    "dedup_threshold": 0.92
  },
  "iterations": [
    {
      "iter": 1,
      "candidates": [
        {
          "cand_id": "1a",
          "type": "exploit",
          "instruct": "温柔的年轻女性，普通话清晰...",
          "rationale": "基于用户要更温柔、更写实的说话方式",
          "audio_path": "data/sessions/.../iter_1/cand_1a.wav",
          "rating": 4,
          "is_best": true
        }
      ],
      "user_note": "更自然一点，少一点播音腔，语速慢一点"
    }
  ]
}
```

---

## 7. LLM 迭代策略（核心）

### 7.1 每轮 LLM 要做什么

输入：最近 N 轮（建议 N=4~6）记录摘要 + 当前 best 候选 + 用户 note + “候选数 M”
输出：结构化 JSON：

* `next_candidates`: M 个（默认 1 exploit + 2 explore）
* `global_negative`: 可选（例如避免“机器人、噪声、混响、过度戏剧化”等），用于 instruct 内显式约束（VoiceSearch 没有单独 negative_prompt 通道时，就把它合并到 instruct 末尾的 “Avoid:” 段落）

### 7.2 Exploit / Explore 比例

* 70% exploit：沿 best 的方向小步改（只改 1~3 个维度：语速/情绪/音色/口音/风格）
* 30% explore：结构化探索（换镜头类比到语音就是：换“角色设定/表达风格/能量层级/近讲程度”之一，但保持已确认偏好不变）

### 7.3 会话内去重（重要）

* 对历史所有 instruct 计算 embedding（建议 sentence-transformers 本地模型）
* 新 instruct 与历史 max cosine sim > 0.92 则视为重复：

  * 优先在 LLM 端改写：要求它保持语义但改动至少 2 个可控维度（并显式说明改了什么）
  * 服务端二次检查，仍超阈值则自动要求 LLM 重新生成（最多重试 2 次）

---

## 8. 关键实现细节（直接可写代码）

### 8.1 HF Token 获取

* 优先读取环境变量 `HF_TOKEN`
* 否则读取 `~/.huggingface/token`
* 同一 token 同时用于：

  * `InferenceClient(..., api_key=HF_TOKEN)`（或 token=HF_TOKEN，二者等价）([Hugging Face][2])
  * `gradio_client.Client(..., hf_token=HF_TOKEN)`([gradio.app][1])

### 8.2 LLM 调用方式（Qwen2.5-72B-Instruct）

使用 `huggingface_hub.InferenceClient` 的 chat completion（OpenAI 兼容别名）([Hugging Face][2])

* `client = InferenceClient(api_key=HF_TOKEN)`
* `client.chat.completions.create(model="Qwen/Qwen2.5-72B-Instruct", messages=[...], max_tokens=..., temperature=...)`

> 注意：HF 侧也建议对 Instruct 模型使用 Chat Completions 以正确套 chat template（避免手搓模板）。([Hugging Face][4])

### 8.3 TTS Space 调用方式（Qwen3-TTS-Voice-Design）

* `client = gradio_client.Client("Qwen/Qwen3-TTS-Voice-Design", hf_token=HF_TOKEN)`([gradio.app][1])
* `client.view_api()` 获取端点名与参数（实现时可在启动日志打印一次，便于排错）
* 每个 candidate 调用一次 `predict(preview_text, instruct, api_name=...)`
* 将返回的音频保存为 wav（gradio_client 通常会把文件下载到本地 temp dir，或直接给出路径/二进制；实现时兼容两种）

---

## 9. Web UI 规格

### 9.1 页面

#### `/` 会话首页

* 选择/输入：

  * language（默认 zh）
  * preview_text（默认一句短文本，建议 1~2 句，<= 80 字）
  * candidates_per_iter M（默认 3）
  * max_iters（默认 20）
  * lock_text（默认 true）
  * dedup_threshold（默认 0.92）
* Start Session 按钮

#### `/session/<session_id>` 主交互页

* 展示当前 iter 编号
* 展示本轮 M 个候选：

  * 每个候选卡片：`instruct`（可折叠）、`rationale`（一行）、音频播放器 `<audio controls src="...">`
  * 评分控件：1-5
  * “Best” 单选（必须选一个 best；若用户不想打分，允许只选 best）
* 用户备注输入框（可选）：例如“更自然、更口语、少气声…”
* Next Iteration 按钮
* 侧栏：

  * best-so-far 音频播放器 + best instruct（折叠）
  * Export Session JSON 按钮

---

## 10. 后端接口（FastAPI）

### 10.1 `POST /api/session/start`

body：

```json
{
  "language": "zh",
  "preview_text": "...",
  "candidates_per_iter": 3,
  "lock_text": true,
  "max_iters": 20,
  "dedup_threshold": 0.92
}
```

return：

```json
{"session_id":"VS_...","redirect_url":"/session/VS_..."}
```

server 行为：

* 创建 session 结构
* 立刻生成 iter=1 的 candidates（调用 LLM → 调 TTS → 存 wav）
* 返回 session_id

### 10.2 `POST /api/session/<id>/iterate`

body：

```json
{
  "iter": 1,
  "ratings": {"1a":4,"1b":2,"1c":3},
  "best_id": "1a",
  "user_note": "更自然一点..."
}
```

return：

```json
{
  "iter": 2,
  "candidates": [
    {"cand_id":"2a","type":"exploit","instruct":"...","rationale":"...","audio_url":"/data/.../cand_2a.wav"}
  ],
  "best_so_far": {"cand_id":"1a","audio_url":"...","instruct":"..."}
}
```

server 行为：

* 写入上一轮评分/备注
* 更新 best-so-far
* 调 LLM 生成下一轮 candidates（含去重约束）
* 调 TTS 生成 wav，落盘
* 返回下一轮数据

### 10.3 `GET /api/session/<id>/export`

* 返回 Session JSON（`application/json` 下载）

### 10.4 静态资源与音频

* `GET /data/.../*.wav`：用 `StaticFiles(directory="data")` 挂载即可

---

## 11. LLM Prompt 模板（建议 v1）

**System（固定）**

* 你是 voice design prompt engineer
* 目标：生成“voice description/instruct”，用于 TTS 生成声音
* 要求：给出 M 个候选（1 exploit + (M-1) explore），每个写 rationale
* 遵守：语言一致（中/英），避免模糊词（“好听”），要具体（音色/情绪/语速/口音/风格等）([阿里云][3])
* 输出必须是严格 JSON（不带 markdown）

**User（动态）**

* settings（language、preview_text、是否 lock_text）
* history 摘要（最近 N 轮：候选 instruct、评分、best、user_note）
* best_so_far instruct
* 去重要求：与历史 max_sim <= threshold，否则改写

**LLM 输出 JSON：**

```json
{
  "next_candidates": [
    {"type":"exploit","instruct":"...","rationale":"..."},
    {"type":"explore","instruct":"...","rationale":"..."}
  ],
  "global_avoid": ["robotic","echo","excessive reverb","background noise"]
}
```

> 注意：`global_avoid` 在服务端合并进每条 instruct 末尾，例如：
> `Avoid: robotic tone, background noise, excessive reverb.`

---

## 12. 去重实现（建议本地 embedding）

* 依赖：`sentence-transformers` + 一个小模型（如 all-MiniLM-L6-v2）
* 每条 instruct 生成向量，存 session 内存里（list）
* cosine 相似度阈值默认 0.92
* 性能：每轮候选很少（<=5），线性扫即可

---

## 13. 配置与运行

### 13.1 环境变量

* `HF_TOKEN`（可选；不设则读 `~/.huggingface/token`）
* `PORT=8000`
* `DATA_DIR=./data`

### 13.2 requirements.txt（建议）

* fastapi, uvicorn, jinja2
* huggingface_hub
* gradio_client
* sentence-transformers, numpy
* soundfile（保存/转换 wav 的兜底）

### 13.3 启动

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

---

# 给 codex / gemini-cli 的“总任务指令”（可复制粘贴）

> 你可以把这一段直接贴给编码模型（再把本 SPEC 一起附上）

实现一个 Python + HTML 的本地 Web App（FastAPI），端口 8000，名为 VoiceSearch：

1. 每次 Start Session 新建 fresh 会话，不加载历史偏好；会话在内存中维护，并持续落盘到 /tmp 与 data/sessions 目录，支持导出 Session JSON
2. LLM 使用 huggingface_hub.InferenceClient，通过 chat completion 调用 Qwen/Qwen2.5-72B-Instruct（使用 HF_TOKEN 或 ~/.huggingface/token；api_key 与 token 等价）([Hugging Face][2])
3. TTS 使用 gradio_client.Client 调用 Hugging Face Space：Qwen/Qwen3-TTS-Voice-Design，传 hf_token（或默认本地 token）([gradio.app][1])
4. 每轮生成 M 个 instruct 候选（默认 M=3：1 exploit + 2 explore），对每个 instruct 调用 Space 合成 preview_text 音频并保存 wav 到 data/sessions/<session_id>/iter_<n>/cand_<id>.wav
5. UI：/ 首页参数；/session/<id> 页面展示音频播放器、评分 1-5、Best 单选、用户备注、Next Iteration、best-so-far、导出按钮
6. 去重：用 sentence-transformers 做 embedding，相似度阈值默认 0.92；若新 instruct 与历史重复则要求 LLM 改写并重试（最多 2 次）
7. 不要 mock：必须在提供 HF_TOKEN 后可直接跑通端到端（LLM + Space TTS）
8. 交付：完整目录结构、requirements.txt、可直接运行的 app.py、LLM prompt 模板文件、清晰 README（如何设置 token、如何启动、常见报错排查：Space 限流/队列等）

---

[1]: https://www.gradio.app/docs/python-client/client "Gradio Python Client -  Class Docs"
[2]: https://huggingface.co/docs/huggingface_hub/en/package_reference/inference_client "Inference"
[3]: https://www.alibabacloud.com/help/en/model-studio/qwen-tts-voice-design "
 Qwen-TTS voice design API reference - Alibaba Cloud Model Studio - Alibaba Cloud Documentation Center

"
[4]: https://huggingface.co/Qwen/Qwen2.5-72B-Instruct/discussions/28?utm_source=chatgpt.com "Qwen/Qwen2.5-72B-Instruct · Inference API Body Structure"

