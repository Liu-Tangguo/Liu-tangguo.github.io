# Tangguo的Blog

一个**零依赖的纯静态个人博客**：内容用 Markdown 写，GitHub Actions 自动编译成 JSON 数据，前端原生 JavaScript 消费，GitHub Pages 托管。

**线上地址**：<https://liu-tangguo.github.io/>

---

## 这是什么

没有框架、没有 npm、没有构建工具、没有 CDN。整个站就是几个 HTML 文件 + 原生 JS + 几个由内容生成的 JSON。

写文章只需要在后台填一个表单，或者往 `content/` 里丢一个 Markdown 文件，剩下的交给 CI。

## 特性

- **零外部依赖**：页面只加载本仓库的文件；字体走系统字体栈，不下载任何字体
- **可视化后台**：用 [Pages CMS](https://app.pagescms.org/liu-tangguo/liu-tangguo.github.io/main) 管理内容，像写文档一样写 Markdown
- **四类内容平等**：文章、站内公告、最新动态、项目记录都能在后台编辑
- **数据驱动**：分类、标签数、累计字数、文章列表、本站最近更新日期全部由内容实时算出，不写死
- **全文搜索**：标题 + 正文 + 分类，命中处高亮并显示正文上下文片段
- **动效克制**：滚动揭示与过渡，并尊重系统的「减少动态效果」设置
- **可验证**：每次改动都跑 DOM id 审计、语法检查、无头渲染、窄屏溢出测量

## 目录结构

```
.
├── index.html                     首页
├── post.html                      文章页（post.html?post=<slug>）
├── .pages.yml                     后台栏目配置
├── content/
│   ├── posts/                     文章
│   ├── notices/                   站内公告
│   ├── updates/                   最新动态
│   ├── projects/                  项目记录
│   └── site/site.md               站点设置（「关于本站」）
├── media/                         图片与 LOGO
├── .github/
│   ├── workflows/build-posts.yml  自动构建流程
│   └── scripts/build-data.py      数据生成脚本
├── posts.json                      ┐
├── notices.json                    │ 由脚本生成，
├── updates.json                    │ 请勿手动修改
├── projects.json                   │
└── site.json                       ┘
```

## 写作方式

### 一、用后台（推荐）

打开 <https://app.pagescms.org/liu-tangguo/liu-tangguo.github.io/main>，用 GitHub 账号登录，然后：

| 栏目 | 内容源 | 字段 |
| --- | --- | --- |
| 文章 | `content/posts/` | 标题、日期、分类、封面图、正文 |
| 通知公告 | `content/notices/` | 类型、标题、日期、说明 |
| 最新动态 | `content/updates/` | 日期、一句话动态 |
| 项目记录 | `content/projects/` | 项目名、状态、技术栈、最近更新、链接 |
| 站点设置 | `content/site/` | 「关于本站」标题与正文 |

保存即提交，稍等一两分钟线上就会更新。

### 二、直接写文件

在 `content/` 对应目录下新建一个 `.md` 文件即可。**文件名（去掉 `.md`）就是这篇文章的唯一 slug**，也是链接里的 `?post=` 参数，建议用 `日期-时间` 形式，例如 `2026-09-28-143000.md`。

各类型的前置数据长这样：

```markdown
---
title: 文章标题
date: 2026-09-28
category: 随笔
cover: /media/xxx.jpg
---

正文……
```

```markdown
---            # 项目记录：updated 填 auto 会跟随本站最近更新日期
name: 某项目
status: 持续维护
stack: Python
updated: auto
link: https://example.com
---
```

## 数据是怎么来的

```
content/*.md  ──►  .github/scripts/build-data.py  ──►  五个 JSON  ──►  浏览器 fetch
                        （GitHub Actions 自动执行）
```

任何对 `content/**` 或页面文件的推送都会触发 `.github/workflows/build-posts.yml`：它调用 `build-data.py` 重新生成 `posts.json`、`notices.json`、`updates.json`、`projects.json`、`site.json`，把结果提交回仓库，再交给 GitHub Pages 发布。

几个刻意的设计：

- 脚本是**幂等**的：数据只由内容决定，不含构建时间戳或提交哈希，所以没有内容变化时不会产生多余提交
- `site.json` 里的站点更新日期取的是**内容里最新的日期**，而不是构建时间
- 项目记录里的 `updated: auto` 会被替换成这个日期

## 本地预览

因为页面要 `fetch` JSON，必须走 HTTP，直接双击 `index.html`（`file://`）会因为浏览器限制读不到数据：

```bash
python3 -m http.server 8000
# 然后打开 http://localhost:8000
```

改完内容想立刻看到效果，可以顺手跑一下构建脚本：

```bash
python3 .github/scripts/build-data.py
```

## 部署

推送到 `main` 即可。GitHub Actions 重建数据 → GitHub Pages 发布，通常一两分钟生效。

注意 Pages 的 HTML 与 JSON 都带 `cache-control: max-age=600` 的 CDN 缓存，刚发完看不到变化时，等几分钟或换个查询串再试。

## 技术选择

- **纯原生**：不引入框架，是因为这个站的交互量很小，框架带来的构建链和依赖维护成本远大于收益
- **数据与页面分离**：内容编译成 JSON 后，页面只负责渲染，改版不需要动内容
- **系统字体**：省掉字体下载，首屏更快，也更贴合原本的编辑感排版
- **可访问性**：动效遵循 `prefers-reduced-motion`，正文与背景对比度保持在可读范围

## 关于

本站由作者与 AI 助手（OpenClaw × DeepSeek）协作搭建，建站过程写在《本站第一篇文章》里。

文章内容版权归作者所有。
