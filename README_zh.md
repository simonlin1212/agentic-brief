<p align="center"><a href="README.md">English</a> | <b>简体中文</b></p>

<h1 align="center">Agentic Brief</h1>

<p align="center">
  <b>每天自动读取财经新闻与视频，专门找共识、分歧和单源风险的晨间简报 Agent。</b><br>
  Google ADK · Gemini 3.5 · Vertex AI · Cloud Run · Firestore · Cloud Scheduler
</p>

<p align="center">
  <a href="#在线演示">在线演示</a> ·
  <a href="#工作方式">工作方式</a> ·
  <a href="#架构">架构</a> ·
  <a href="#本地运行">本地运行</a> ·
  <a href="CHANGELOG.md">更新记录</a>
</p>

---

## 在线演示

**公开简报：** [agentic-brief-web-qjv2kumm3q-as.a.run.app](https://agentic-brief-web-qjv2kumm3q-as.a.run.app/)

![Agentic Brief 看板](./assets/dashboard.png)

它不是聊天机器人。Cloud Scheduler 每天新加坡时间 07:00 主动触发私有 Cloud Run 运行器；两个互相看不到对方结果的 scout 分别读取新闻和财经视频，editor 再做交叉验证。最终结果写入 Firestore，由另一个只读的公开 Cloud Run 网页展示。

## 工作方式

1. **News Scout** 读取 CNBC、MarketWatch、Federal Reserve RSS，去重并筛选真正影响板块的事件。
2. **Video Scout** 通过 YouTube Data API 检索五个可信官方财经频道，再让 Gemini 3.5 直接读取一条 4–20 分钟视频的声音和画面。
3. 两个 scout 不共享状态，避免一个高声量信源污染另一路判断。
4. **Editor Agent** 输出 `TOP SIGNALS`、`CONTRADICTIONS`、`THIN ICE`、`WHAT CHANGED` 四部分。
5. 私有运行器负责模型调用和写库；公开网页只有读取权限，无法触发费用。

## 架构

![Agentic Brief 架构](./docs/architecture.svg)

Scheduler 使用 OIDC 身份调用私有运行器；匿名请求会被 Cloud Run IAM 拒绝。YouTube key 存在 Secret Manager，不进入镜像、代码或普通环境变量配置。

## 已验证

- 私有运行器对匿名 `POST /run` 返回 403。
- Scheduler 云端执行 69.6 秒完成并返回 201。
- Firestore 成功保存真实新闻、视频分析和 4,000+ 字符简报，无 stub URL。
- 公开网页与 `/api/latest` 返回 200。
- 桌面端与 390px 手机端真实浏览器测试通过，无横向溢出。
- 首次云端发布时整仓 40+ 项测试通过，总覆盖率 87%。

## 本地运行

```bash
git clone https://github.com/simonlin1212/agentic-brief.git
cd agentic-brief
uv sync --extra dev
cp .env.example .env
chmod 600 .env
gcloud auth application-default login
.venv/bin/python run_local.py
```

`.env` 需要填写 Vertex AI 项目、`global` 区域和受限的 YouTube Data API key。完整的云端部署命令见 [英文 README](README.md#deploy-to-google-cloud)。

## 测试

```bash
.venv/bin/ruff check .
.venv/bin/pytest --cov=agentic_brief --cov-report=term-missing
```

## 局限

- 当前只有新闻和 YouTube 两类信源，因此简报会把单源结论放入 `THIN ICE`，不会包装成广泛共识。
- YouTube 刻意限制在五个官方财经频道，牺牲覆盖面换取稳定性与可解释性。
- 这是研究自动化工具，不是个性化投资建议或交易系统。

## 更新记录

见 [CHANGELOG.md](CHANGELOG.md)。

## 免责声明

Agentic Brief 是实验性研究工具，输出可能不完整或错误，不构成任何建议、推荐或交易指令。

## 赞赏

如果这个项目有帮助，可以请作者喝杯咖啡。

<p align="center">
  <a href="https://buymeacoffee.com/simonlin1212"><img src="./assets/bmc-qr.png" width="180" alt="Buy Me a Coffee"></a>
</p>

## License

MIT，详见 [LICENSE](LICENSE)。

**作者：** Simon 林 · X [@linsizhen](https://x.com/linsizhen) · 邮箱：[simonlin0423@gmail.com](mailto:simonlin0423@gmail.com)
