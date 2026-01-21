SoulSearch（Text-to-Image Prompt Search）——“新鲜会话”的偏好探索与提示词迭代工具
1. 项目概述
SoulSearch 是一个用于 text-to-image 模型的交互式 prompt 搜索工具：每次运行从零开始，不加载历史偏好。用户对生成图像打分/选择偏好，系统将“prompt + 反馈”回灌给 LLM，让 LLM 产生下一轮更符合当前会话偏好的 prompt，迭代多轮以快速逼近用户想要的效果。

与你们已有经验一致的闭环：

LLM 提供 prompt 候选
文生图 API 出图
人类打分/选择/写偏好
LLM 基于会话记录生成下一轮 prompt（更贴合偏好，同时保持一定探索）
关键差异点：

不需要加载前次状态，每次 fresh start（避免被旧偏好锁死）
但可选提供“导出本次会话日志”以便复盘
2. 目标与非目标
2.1 目标
快速收敛到“本次会话用户偏好”
UI 极简：看图 → 打分/选最喜欢 → 下一轮
维持探索：不要只沿一条路越走越窄（避免局部最优）
prompt 去重：同一会话内避免反复给高度相似 prompt
2.2 非目标
不建立跨会话长期用户画像（你们明确不要）
不做复杂的 RLHF 训练管线（只做在线迭代搜索）
3. 用户角色与工作流
3.1 角色
User（偏好提供者）：对图片进行评分、选择、给简短反馈
3.2 单次会话流程（Session）
用户打开网页 / → 选择基础设置（可选）

模型、图片尺寸、采样步数、张数 K（如 K=4）
初始描述（可选输入一个“起始 prompt”）
系统生成第一轮 prompts（1~M 个；建议 M=1 或 2）

对每个 prompt 生成 K 张图

用户对每张图评分（1-5）或“选出最喜欢的一张”

用户可输入偏好文本（例如：更写实/更柔光/不要文字/更干净背景）

系统将本轮记录喂给 LLM，生成下一轮 prompt

重复 5~20 轮，直到满意

可选：导出会话 JSON（用于分享/复现）

4. 系统架构
后端：Python（FastAPI/Flask）
前端：HTML + 少量 JS
端口：8000
会话存储：内存（Python dict）或临时文件（/tmp/session_xxx.json）
图片缓存：data/sessions/<session_id>/iter_<n>/img_<k>.png
若页面刷新导致会话丢失是可接受的（你们说“fresh start”优先）。但建议提供一个“导出 session”按钮。

5. 数据模型（会话日志）
5.1 Session JSON（可导出）
{
  "session_id": "SES_20260120_001",
  "created_at": "2026-01-20T11:00:00Z",
  "image_model": {
    "provider": "YourImageVendor",
    "model": "txt2img-abc",
    "size": "1024x1024",
    "steps": 30
  },
  "llm_model": {
    "provider": "YourLLMVendor",
    "model": "gpt-xxx"
  },
  "iterations": [
    {
      "iter": 1,
      "prompt": "a minimalistic studio portrait ...",
      "images": [
        {"path": "data/sessions/.../img_1.png", "rating": 4},
        {"path": "data/sessions/.../img_2.png", "rating": 2}
      ],
      "user_note": "更写实一点，背景更干净，不要夸张光晕"
    }
  ]
}
6. LLM 迭代策略（核心能力利用）
6.1 LLM 需要做的事
从反馈中抽取偏好约束：写实/风格/构图/色调/主体/背景/镜头/材质等

生成下一轮 prompt：

70%：沿最优图的方向做小步改进（exploitation）
30%：做结构化探索（exploration），例如替换镜头、光线、背景、风格，但保持关键偏好不变
会话内 prompt 去重：

对历史 prompts 做 embedding 相似度
若新 prompt 与历史 max_sim > 0.92，要求 LLM 改写再出
6.2 Prompt 模板（建议结构化输出）
输入给 LLM：

最近 N 轮记录（prompt + 评分摘要 + user_note）
当前最优图片对应的 prompt
“本轮需要生成 X 个候选 prompt”：例如 3 个（1 个 exploitation + 2 个 exploration） 输出（JSON）：
{
  "next_prompts": [
    {
      "type": "exploit",
      "prompt": "...",
      "rationale": "基于用户想要更写实、背景干净..."
    },
    {
      "type": "explore",
      "prompt": "...",
      "rationale": "在保持写实的前提下探索不同镜头..."
    }
  ],
  "negative_prompt": "text, watermark, blurry, low quality"
}
7. Web UI 规格
7.1 页面
/ 会话首页

参数选择：模型、尺寸、每轮张数 K、steps、seed（可选）
输入：起始 prompt（可选）
按钮：Start Session
/session/<session_id> 主交互页（迭代循环）

展示当前迭代 prompt
图片网格（K 张或 M×K 张）
每张图：评分控件（1-5）+ “Best” 单选
文本框：用户偏好补充
按钮：Next Iteration（提交反馈并生成下一轮）
侧栏：历史最佳图（best-so-far）与其 prompt（方便用户对齐目标）
按钮：Export Session JSON
7.2 交互细节
支持两种反馈模式（可二选一或同时）

评分制：每张 1-5 分
锦标赛/选择制：选最喜欢一张（更快）
若用户不想打分，可只点“Best + 一句偏好”，LLM 也能迭代

8. 后端接口（示例）
POST /api/session/start

body：模型参数 + optional 初始 prompt
return：session_id
POST /api/session/<id>/iterate

body：本轮评分/选择 + user_note

server：

写入 session log
调 LLM 生成下一轮 prompt(s)
调文生图 API 生成图片
return：下一轮图片路径 + prompt

GET /api/session/<id>/export

return：session JSON 下载
9. 配置与运行
LLM_API_KEY
IMAGE_API_KEY
PORT=8000
DATA_DIR=./data
启动：uvicorn app:app --port 8000

10. 验收标准（MVP）
每次启动为“新会话”，不加载历史偏好（除非用户导入导出文件，导入可作为后续功能）
能完成至少 10 轮：出图 → 打分/选择 → 下一轮 prompt
prompt 会随反馈发生可解释变化（UI 能看到 prompt 与 rationale）
会话可导出 JSON，并包含每轮 prompt、图片路径、评分、用户备注
会话内 prompt 去重生效（不会连续多轮几乎同 prompt）
给 gemini-cli / codex 的实现指令建议（可直接复制贴过去）
你可以把下面这段作为“总任务”贴给编码模型（然后把上面任一 spec 附上）：

实现一个 Python + HTML 的本地 Web App（FastAPI 优先），端口 8000
对外部 LLM/TTS/文生图均用可替换的 client 封装（先写 mock，再接真实 API）
数据格式严格按 spec 的 JSONL / Session JSON
UI 按 spec 的页面与交互实现
提供最小可运行 demo：不接真实 API 也能跑通（mock 生成假音频/假图片），接入 key 后可切换真实调用
如果你希望我再进一步“工程化到可直接开工”的程度，我也可以在不问你额外问题的前提下，给出：

两个项目的目录结构（monorepo / 两个子项目）
FastAPI 路由与 Pydantic model 清单
LLM prompts 的版本管理方式（prompt_id + 模板文件）
去重向量索引的落地实现（FAISS/SQLite）与增量更新策略
---
class LLMService:
    def __init__(self):
        self.token = load_hf_token()
        self.client = None
        if self.token:
            # 使用强大的指令微调模型 Qwen2.5-72B-Instruct
            self.client = InferenceClient(api_key=self.token, model="Qwen/Qwen2.5-72B-Instruct")
---
结合上面 Qwen3-TTS-Voice-Design 和 Qwen/Qwen2.5-72B-Instruct 的调用方式，在 SoulSearch 基础上改出一个 VoiceSearch 来。也要是完整的能交给 codex/gemini-cli 的 SPEC。没有 mock 直接能跑。要想下哪些东西是可以通过 LLM 修改的（修改后送给  Qwen3-TTS-Voice-Design 产 wav 再由人评价）。
