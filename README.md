# Tangguo的Blog

一个**零依赖的纯静态个人博客**：内容用 Markdown 写，GitHub Actions 自动编译成 JSON 数据，前端原生 JavaScript 消费，GitHub Pages 托管。

**线上地址**：<https://liu-tangguo.github.io/>

---

## 这是什么

没有前端框架、没有 npm、没有打包器、没有 CDN。整个站就是几个 HTML 文件 + 一份共用的原生 JS + 几个由内容生成的 JSON。

写文章只需要在后台填一个表单，或者往 `content/` 里丢一个 Markdown 文件，剩下的交给 CI。

## 特性

- **几乎零外部依赖**：页面只加载本仓库的文件；字体走系统字体栈，不下载任何字体。**例外只有三处**（见下方「隐私与外部请求」）
- **可视化后台**：用 [Pages CMS](https://app.pagescms.org/liu-tangguo/liu-tangguo.github.io/main) 管理内容，像写文档一样写 Markdown
- **四类内容平等**：文章、站内公告、最新动态、项目记录都能在后台编辑
- **数据驱动**：分类、标签数、累计字数、文章列表、本站最近更新日期全部由内容实时算出，不写死
- **全文搜索**：`search.html` 支持标题 + 正文 + 分类，命中处高亮并显示正文上下文片段
- **摸鱼导航**：首页的「摸鱼导航」区块从 `games.json` 读站点清单，一行一条（见下方）
- **动效克制**：滚动揭示与过渡，并尊重系统的「减少动态效果」设置

## 目录结构

```
.
├── index.html                     首页
├── post.html                      文章页（post.html?post=<slug>）
├── search.html                    搜索页（noindex）
├── 404.html                       自定义 404
├── robots.txt / sitemap.xml       SEO（sitemap 由构建脚本生成）
├── games.json                     摸鱼导航清单
├── assets/site.js                 全站共用脚本（主题 / 时钟 / 访问统计）
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
│   └── scripts/
│       ├── build-data.py          内容 → JSON
│       ├── build-pages.py         文章 → p/<slug>/index.html
│       └── fetch-visits.py        访问统计 → visits.json
├── p/<slug>/index.html            构建生成的文章静态页
├── posts.json                      ┐
├── notices.json                    │
├── updates.json                    │ 由脚本生成，
├── projects.json                   │ 请勿手动修改
├── site.json                       │
├── contributions.json              │
└── visits.json                     ┘
```

## 写作方式

### 一、用后台（推荐）

打开 <https://app.pagescms.org/liu-tangguo/liu-tangguo.github.io/main>，用 GitHub 账号登录，然后：

| 栏目 | 内容源 | 字段 |
| --- | --- | --- |
| 文章 | `content/posts/` | 标题、日期、分类、封面图、摘要（可选）、正文 |
| 通知公告 | `content/notices/` | 类型、标题、日期、说明 |
| 最新动态 | `content/updates/` | 日期、一句话动态 |
| 项目记录 | `content/projects/` | 项目名、状态、技术栈、最近更新、链接 |
| 站点设置 | `content/site/site.md` | 「关于本站」标题与正文、GitHub 用户名、统计令牌 |

保存即提交，稍等一两分钟线上就会更新。

### 二、直接写文件

在 `content/` 对应目录下新建一个 `.md` 文件即可。**文件名（去掉 `.md`）就是这篇文章的 slug**（链接为 `/p/<slug>/`），建议用 `日期-时间` 形式，例如 `2026-09-28-143000.md`。

```markdown
---
title: 文章标题
date: 2026-09-28
category: 随笔
cover: /media/xxx.jpg
summary: 一句话摘要（可选，用于分享卡片与搜索结果；留空自动截正文）
---

正文……
```

```markdown
---
# 项目记录：updated 填 auto 会跟随本站最近更新日期
name: 某项目
status: 持续维护
stack: Python
updated: auto
link: https://example.com
---
```

## 摸鱼导航（games.json）

首页「摸鱼导航」区块的清单就是这个文件，一行一个站点，改完推送即可：

```json
[
  { "name": "Neal.fun", "url": "https://neal.fun", "desc": "脑洞实验小游戏" }
]
```

`name` 是卡片标题，`url` 点开即玩，`desc` 一句话说明；增删条目不需要动 HTML。

## 数据是怎么来的

```
content/*.md  ──►  build-data.py  ──►  七个 JSON  ──►  浏览器 fetch
                    build-pages.py ──►  p/<slug>/ + sitemap.xml
                    fetch-visits.py ──►  visits.json（需 CF 密钥，失败保留旧文件）
                        （GitHub Actions 自动执行）
```

推送到 `main` 会触发 `.github/workflows/build-posts.yml`；此外每 3 小时定时跑一次（刷新访问统计）。构建结果有变化时才提交回仓库。

几个刻意的设计：

- 脚本是**幂等**的：数据只由内容决定，不含构建时间戳；没有内容变化时不会产生多余提交（`visits.json` 的数字变了才会更新时间）
- `site.json` 的站点更新日期取**内容里最新的日期**，不是构建时间
- 项目记录里的 `updated: auto` 会被替换成这个日期
- 文章页的分享图默认取 `media/og/<slug>.png`，没有则用 `media/og-default.png`

## 本地预览

页面要 `fetch` JSON，必须走 HTTP；直接双击 `index.html`（`file://`）读不到数据：

```bash
python3 -m http.server 8000
# 然后打开 http://localhost:8000
```

改完内容想立刻看到效果：

```bash
python3 .github/scripts/build-data.py
python3 .github/scripts/build-pages.py
```

## 部署

推送到 `main` 即可。GitHub Actions 重建数据 → GitHub Pages 发布，通常一两分钟生效。

Pages 的 HTML 与 JSON 都带 `cache-control: max-age=600` 的 CDN 缓存，刚发完看不到变化时，等几分钟或用无痕窗口再试。

## 隐私与外部请求

全站静态，**不收集**任何个人信息；只有以下三处在浏览器里发起跨站请求：

| 请求 | 用途 | 何时发生 |
| --- | --- | --- |
| `api.open-meteo.com` | 首页天气 | 每次打开首页 |
| `ipwho.is` | 按 IP 估算城市（只用于天气定位） | 每次打开首页 |
| `static.cloudflareinsights.com` | 匿名访问计数（无 Cookie） | 仅当站点设置里填了 `cfToken` |

构建期还会向 `github-contributions-api.jogruber.de` 取公开的 GitHub 贡献数据。

## 关于

本站由作者与 AI 助手协作搭建。

文章内容版权归作者所有。
