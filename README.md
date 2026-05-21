# CodeStudy Notes

GitHub/本地代码仓库学习笔记生成器：扫描代码仓库，识别语言、配置、入口、目录结构和阅读路线，输出 Markdown 学习笔记。

## Run

```bash
python docs/tests/smoke_test.py
python -m code_study_notes analyze . --out ./out
python -m code_study_notes web --host 127.0.0.1 --port 8765 --out ./out
```

## Features

- 本地仓库静态分析
- 语言分布统计
- 入口文件和配置文件识别
- Mermaid 模块图
- Markdown 学习笔记输出
- 简易 Web UI
