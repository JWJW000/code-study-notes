# CodeStudy Notes

GitHub/本地代码仓库学习笔记生成器：扫描代码仓库，识别语言、配置、入口、目录结构和阅读路线，输出 Markdown 学习笔记。

## Features

- 本地仓库静态分析
- 语言分布统计
- 入口文件和配置文件识别
- Mermaid 模块图
- Markdown 学习笔记输出
- Web UI 使用 [`nexu-io/open-design`](https://github.com/nexu-io/open-design) 的 Vercel design system token：`open-design/vercel-tokens.css`
- Docker Compose 一键部署

## Local Run

```bash
python docs/tests/smoke_test.py
python -m code_study_notes analyze . --out ./out
python -m code_study_notes web --host 127.0.0.1 --port 8765 --out ./out
```

## Docker 一键部署

```bash
mkdir -p workspace out
# 把要分析的代码放到 ./workspace，容器内路径是 /workspace
docker compose up -d --build
```

访问：

```text
http://localhost:8765
```

在页面输入：

```text
/workspace
```

停止：

```bash
docker compose down
```
