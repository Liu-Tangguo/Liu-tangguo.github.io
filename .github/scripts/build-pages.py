#!/usr/bin/env python3
# 为每篇文章生成静态页 p/<slug>/index.html：
#   - 正文在构建时就渲染进 HTML（社交平台爬虫不执行 JS，必须预渲染）
#   - 带 og:*/twitter:* 分享标签与 canonical、JSON-LD
#   - 模板取自 .github/scripts/template-post.html
# 同时把 post.html 写成跳转页，保证旧链接 post.html?post=<slug> 仍然可用。
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).resolve().parent / "template-post.html"
SITE_NAME = "Tangguo的Blog"
SITE_URL = "https://liu-tangguo.github.io"


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def md_inline(s):
    s = esc(s)
    parts = s.split("`")
    out = parts[0]
    for i in range(1, len(parts)):
        out += ("<code>" + parts[i] + "</code>") if i % 2 == 1 else parts[i]
    s = out
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    return s


def md_to_html(md):
    out, buf, mode, code, in_code = [], [], "", [], False

    def flush():
        nonlocal buf, mode
        if mode == "quote" and buf:
            out.append("<blockquote>" + "<br>".join(buf) + "</blockquote>")
        elif mode in ("ul", "ol") and buf:
            items = "".join("<li>" + x + "</li>" for x in buf)
            out.append("<%s>%s</%s>" % (mode, items, mode))
        elif buf:
            out.append("<p>" + "<br>".join(buf) + "</p>")
        buf = []
        mode = ""

    for raw in str(md or "").replace("\r\n", "\n").split("\n"):
        t = raw.strip()
        if t.startswith("```"):
            if in_code:
                out.append("<pre><code>" + esc("\n".join(code)) + "</code></pre>")
                code, in_code = [], False
            else:
                flush()
                in_code = True
            continue
        if in_code:
            code.append(raw)
            continue
        if not t:
            flush()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", t)
        if m:
            flush()
            lv = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lv, md_inline(m.group(2)), lv))
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", t):
            flush()
            out.append("<hr>")
            continue
        if t.startswith(">"):
            if mode != "quote":
                flush()
                mode = "quote"
            buf.append(md_inline(t.lstrip("> ").strip()))
            continue
        m = re.match(r"^[-*+]\s+(.*)$", t)
        if m:
            if mode != "ul":
                flush()
                mode = "ul"
            buf.append(md_inline(m.group(1)))
            continue
        m = re.match(r"^\d+[.)]\s+(.*)$", t)
        if m:
            if mode != "ol":
                flush()
                mode = "ol"
            buf.append(md_inline(m.group(1)))
            continue
        if mode in ("quote", "ul", "ol"):
            flush()
        buf.append(md_inline(t))
    flush()
    return "\n".join(out)


def excerpt(post, limit=110):
    t = re.sub(r"[#>*_`\[\]()!]", "", str(post.get("body") or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:limit] + "…") if len(t) > limit else t


def og_image(slug):
    per = ROOT / "media" / "og" / (slug + ".png")
    return SITE_URL + ("/media/og/%s.png" % slug if per.exists() else "/media/og-default.png")


def head_block(post):
    title = post.get("title") or post.get("slug")
    desc = excerpt(post) or SITE_NAME
    url = "%s/p/%s/" % (SITE_URL, post.get("slug"))
    img = og_image(post.get("slug"))
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(post.get("date") or ""))
    published = ("%s-%s-%sT00:00:00+08:00" % m.groups()) if m else ""
    ld = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": desc,
        "image": img,
        "url": url,
        "datePublished": published,
        "author": {"@type": "Person", "name": "Tangguo"},
        "publisher": {"@type": "Organization", "name": SITE_NAME},
    }
    return """<title>%s · %s</title>
<meta name="description" content="%s">
<link rel="canonical" href="%s">
<meta property="og:type" content="article">
<meta property="og:site_name" content="%s">
<meta property="og:title" content="%s">
<meta property="og:description" content="%s">
<meta property="og:url" content="%s">
<meta property="og:image" content="%s">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="%s">
<meta name="twitter:description" content="%s">
<meta name="twitter:image" content="%s">
<script type="application/ld+json">%s</script>""" % (
        esc(title), SITE_NAME, esc(desc), url, SITE_NAME, esc(title), esc(desc), url, img,
        esc(title), esc(desc), img, json.dumps(ld, ensure_ascii=False))


def article_block(post):
    return ('<div class="article-header">'
            '<h1 class="article-title">' + esc(post.get("title") or "无标题") + '</h1>'
            '<div class="article-meta"><span>日期：' + esc(post.get("date") or "未知") + '</span>'
            '<span>分类：' + esc(post.get("category") or "未分类") + '</span></div>'
            '</div>'
            '<div class="article-body">' + md_to_html(post.get("body") or "") + '</div>'
            '<div class="article-footer"><a class="back-button" href="/index.html">← 返回首页</a></div>')


def main():
    posts = json.loads((ROOT / "posts.json").read_text(encoding="utf-8"))
    tpl = TEMPLATE.read_text(encoding="utf-8")
    made = []
    for post in posts:
        slug = post.get("slug")
        if not slug:
            continue
        page = tpl
        page = page.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<base href="/">', 1)
        page = page.replace("<title>文章详情 · Tangguo的Blog</title>", head_block(post), 1)
        page = page.replace('<div class="message">正在读取文章，请稍候……</div>', article_block(post), 1)
        out_dir = ROOT / "p" / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(page, encoding="utf-8")
        made.append(slug)
    print("static pages: %d" % len(made))
    for s in made:
        print("  p/%s/" % s)


if __name__ == "__main__":
    main()
