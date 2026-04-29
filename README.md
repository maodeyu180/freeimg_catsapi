# freeimg_catsapi · 喵的公益生图

一个极简的免费 AI 生图 / 生视频站点，通过反向代理 [`ldc_gen_image`](https://catsapi.com)
（CatsAPI）的 API 实现——后端用一个内部账号的 API Key 调用上游，所有登录用户共享 **全局 2 并发** 的生成能力。

## 特点

- **只支持 LinuxDo OAuth 登录**（要求信任等级 ≥ 1）
- 图片模型：`Nano Banana 2`、`Nano Banana Pro`、`GPT Image 2`、`Grok Imagine Image`
- 视频模型：`Grok Imagine Video`
- **全局 2 并发** + **每用户同时只能 1 个活跃任务**（排队/运行中），带排队位次
- 每用户每日配额（默认 图片 20 张 / 视频 3 条，自然日按 `Asia/Shanghai` 重置）
- 画廊：作品默认私有，可选公开发布；他人作品支持「一键同款」
- 管理员白名单（按 LinuxDo 数字 ID），可封禁用户 / 调整配额 / 强制取消任务
- 蓝色主题极简 UI

## 目录结构

```
freeimg_catsapi/
├── backend/            # FastAPI + SQLite
│   ├── app/
│   ├── .env.example
│   └── requirements.txt
├── frontend/           # Vue 3 + Vite + Tailwind v4
│   ├── src/
│   └── package.json
├── run.py              # 一键启动脚本（同时起后端 + 前端）
└── README.md
```

## 快速开始

### 前置要求
- Python 3.11+
- Node.js 18+
- 一个可用的 `ldc_gen_image` / CatsAPI 上游服务（默认连 `http://127.0.0.1:8000`，
  生产可换成 `https://catsapi.com`），并已为内部账号生成 API Key

### 启动

```bash
cd freeimg_catsapi
python run.py
```

首次运行会自动：
1. 创建 `backend/.venv` 并安装依赖
2. 若 `backend/.env` 不存在则从 `.env.example` 拷贝
3. 在 `frontend/` 执行 `npm install`
4. 启动后端 (8100) 和前端 (5174)

访问：http://localhost:5174

也可以分开启动：

```bash
python run.py --backend-only
python run.py --frontend-only
```

### 配置（`backend/.env`）

| 变量 | 说明 |
|---|---|
| `LINUXDO_CLIENT_ID` | **新注册** 一个 LinuxDo OAuth 应用（redirect_uri 指向本项目）|
| `LINUXDO_CLIENT_SECRET` | LinuxDo 应用密钥 |
| `LINUXDO_REDIRECT_URI` | 默认 `http://localhost:5174/auth/callback` |
| `CATSAPI_URL` | 上游地址，默认 `http://127.0.0.1:8000`，生产可填 `https://catsapi.com` |
| `CATSAPI_KEY` | 在上游管理后台为内部账号生成的 API Key |
| `JWT_SECRET` | JWT 签名密钥（请改成随机字符串）|
| `JWT_EXPIRE_DAYS` | JWT 有效期（天），默认 `7` |
| `MIN_TRUST_LEVEL` | 登录最低信任等级，默认 `1` |
| `ADMIN_LINUXDO_IDS` | 管理员 LinuxDo 数字 ID 白名单，逗号分隔 |
| `MAX_CONCURRENT_TASKS` | 全局同时运行任务数，默认 `2` |
| `DAILY_IMAGE_LIMIT` | 每用户每日图片配额，默认 `20` |
| `DAILY_VIDEO_LIMIT` | 每用户每日视频配额，默认 `3` |
| `QUOTA_TIMEZONE` | 配额自然日时区，默认 `Asia/Shanghai` |
| `WORKER_POLL_INTERVAL_SECONDS` | 调度器轮询间隔（秒），默认 `3` |
| `TASK_TIMEOUT_MINUTES` | 单任务超时（分钟），默认 `15` |

> 你需要在上游管理后台给内部账号配置足够的猫币以及
> `max_concurrent_tasks >= MAX_CONCURRENT_TASKS`，否则会触发上游限流。

## 参数限制

| 模型 | 锁定限制 |
|---|---|
| Nano Banana 2 | 分辨率仅 `1K` / `2K`；宽高比精简到 6 种（`1:1`/`16:9`/`9:16`/`4:3`/`3:4`/`2:3`） |
| Nano Banana Pro | 同上；单次最多生成 2 张 |
| GPT Image 2 | `quality` 锁定 `auto`；`size` 开放 8 档（1024/1536/2048 系列） |
| Grok Imagine Image | 纯文生图；宽高比 11 种 |
| Grok Imagine Video | 时长 `5` / `6` / `7` 秒；分辨率仅 `480p`；宽高比 3 种；纯文生视频 |

每个图片模型最多上传 **2 张参考图**（单张 ≤ 5MB），视频不支持参考图。

所有模型的 `rewritePrompt`（上游的 AI 改写）均强制关闭，保持用户 prompt 原样。

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/auth/login` | 获取 LinuxDo 登录 URL |
| POST | `/api/auth/callback` | OAuth 回调 |
| GET | `/api/auth/me` | 当前用户信息（含今日配额）|
| GET | `/api/models` | 支持的模型与参数定义 |
| POST | `/api/tasks` | 提交任务（每用户同时 1 个）|
| GET | `/api/tasks` | 我的任务列表 |
| GET | `/api/tasks/{id}` | 任务详情 |
| POST | `/api/tasks/{id}/cancel` | 取消排队中的任务 |
| GET | `/api/gallery/mine` | 我的作品 |
| GET | `/api/gallery/public` | 公开画廊 |
| PUT | `/api/gallery/{id}/publish` | 发布 / 取消发布 |
| DELETE | `/api/gallery/{id}` | 删除作品 |
| GET | `/api/gallery/{id}/remix` | 一键同款（返回参数，前端灌表单）|
| GET | `/api/admin/users` 👑 | 用户列表（支持搜索）|
| PUT | `/api/admin/users/{id}` 👑 | 封禁 / 调整配额 |
| GET | `/api/admin/tasks` 👑 | 所有任务列表（支持按 `user_id` 过滤）|
| POST | `/api/admin/tasks/{id}/force-cancel` 👑 | 强制取消 |

## 并发与队列

- 后端自带一个 asyncio worker，按 `WORKER_POLL_INTERVAL_SECONDS`（默认 3s）轮询调度
- 任何时刻全局最多 `MAX_CONCURRENT_TASKS=2` 个任务正在调用上游
- 任务提交后进入 `queued`，被调度时变 `running`，完成 / 失败 / 取消后进入终态
- 运行中任务已调用上游，**无法中断**；`queued` 状态可随时取消
- 上游报"并发已达上限"时进入 10 秒短冷却，避免雪崩重试
- 任务超时后会被标记为 `failed`（默认 15 分钟）

## 管理后台

- `/admin` 路由仅 `ADMIN_LINUXDO_IDS` 白名单内的 LinuxDo 账号可见
- **用户**标签：搜索 / 改配额 / 封禁解封；点击行可查看该用户的任务列表
- **任务**标签：浏览所有任务，对 `queued` / `running` 中的任务可强制取消

## 许可

MIT
