# Code Study Notes

Code Study Notes 是一个本地 Web/CLI 工具，用静态分析帮你快速读懂 GitHub 或本地代码仓库，并生成可交付的 Markdown 学习笔记。

它当前不依赖真实 LLM，重点放在可解释、可离线运行的 MVP：目录扫描、语言识别、依赖/配置文件解析、入口文件识别、阅读路线和报告生成。

## 功能

- 忽略 `.git`、`node_modules`、`venv`、`dist`、`build`、`__pycache__` 等常见噪声目录。
- 统计 Python、JavaScript、TypeScript、Java、Go、Markdown、YAML、JSON 等语言分布。
- 识别 `package.json`、`requirements.txt`、`pyproject.toml`、`pom.xml`、`go.mod`、`Dockerfile`、`docker-compose.yml` 等关键配置。
- 识别 `main.py`、`app.py`、`server.js`、`src/main/java`、`cmd/*`、Docker `CMD/ENTRYPOINT` 等可能入口。
- 生成阅读路线、Mermaid 模块关系图、可运行命令猜测和后续问题清单。
- 提供 CLI 和本地 Web UI，Web UI 可以查看最近一次报告。

## 运行方式

在仓库根目录运行 CLI：

```bash
python -m code_study_notes analyze . --out ./out
```

生成结果：

```text
./out/study-notes.md
```

启动本地 Web UI：

```bash
python -m code_study_notes web --host 127.0.0.1 --port 8765 --out ./out
```

浏览器打开：

```text
http://127.0.0.1:8765
```

## 测试

运行 smoke test：

```bash
python code-study-notes/tests/smoke_test.py
```

测试会临时创建一个小型 Python/Node 风格仓库，验证核心分析函数、入口识别、配置识别和 Markdown 报告生成。

## 示例输出

查看：

```text
code-study-notes/examples/sample-report.md
```

## 面试讲法

这个项目适合讲成“面向代码学习场景的静态分析 MVP”：

1. 输入是任意本地仓库路径，输出是结构化学习笔记，而不是聊天式回答。
2. 核心能力先用确定性规则完成，包括目录树、语言分布、配置摘要、入口识别和运行命令猜测。
3. Web 和 CLI 共用同一套分析函数，方便测试，也方便未来接入真实 LLM。
4. 后续可以扩展 AST 分析、调用图、测试覆盖摘要、GitHub URL clone、向量检索和 LLM 总结。

项目取舍：先把可运行、可验证、可离线的链路做完整，再把 LLM 放到报告润色或问答层，而不是让核心功能依赖外部服务。

