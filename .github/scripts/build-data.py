#!/usr/bin/env python3
# 从 content/ 下的 Markdown 生成站点数据文件：
# posts.json / notices.json / updates.json / projects.json / site.json
#
# 设计要点：
# - 只输出由内容决定的结果，不放构建时间戳/提交哈希，避免机器人每次空提交。
# - site.json 的 updatedAt 取所有内容（文章/公告/动态）里最新的一天，
#   与作者在 CMS 里填写的日期一致；完全没有内容时才退回提交日期。
import datetime
import json
import re
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def git(args, default=""):
    try:
        return subprocess.check_output(["git"] + args, cwd=str(ROOT), text=True).strip()
    except Exception:
        return default


def parse_front_matter(text):
    fm, body = {}, text
    if text.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
        if m:
            body = m.group(2).strip()
            for line in m.group(1).splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip().strip("\"'")
                if k:
                    fm[k] = v
    return fm, body


def load(folder, keep):
    out = []
    d = ROOT / "content" / folder
    if not d.exists():
        return out
    for f in sorted(d.glob("*.md")):
        if f.name.lower() == "readme.md":
            continue
        fm, body = parse_front_matter(f.read_text(encoding="utf-8"))
        item = {"slug": f.stem, "filename": f.name}
        for k in keep:
            item[k] = fm.get(k, "")
        item["body"] = body
        out.append(item)
    return out


def write_json(name, data):
    (ROOT / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("  %-16s %s" % (name, len(data) if isinstance(data, list) else "1 object"))


# ---------- 读取内容 ----------
posts = load("posts", ["title", "date", "category", "cover"])
for p in posts:
    p["title"] = p["title"] or p["slug"]
    p["category"] = p["category"] or "未分类"
posts.sort(key=lambda x: (x["date"], x["slug"]), reverse=True)

notices = load("notices", ["kind", "title", "date"])
for n in notices:
    n["kind"] = n["kind"] or "公告"
    n["title"] = n["title"] or n["slug"]
notices.sort(key=lambda x: (x["date"], x["slug"]), reverse=True)

updates = load("updates", ["date", "text"])
for u in updates:
    u["text"] = u["text"] or u["slug"]
updates.sort(key=lambda x: (x["date"], x["slug"]), reverse=True)

# ---------- 站点设置（content/site 下只应有一个文件） ----------
settings = load("site", ["aboutHeading"])
about = settings[0] if settings else {}
if len(settings) > 1:
    print("  ! content/site 下有 %d 个文件，只用第一个：%s" % (len(settings), settings[0]["filename"]))

# ---------- 站点信息 ----------
content_dates = [x.get("date", "") for x in (posts + notices + updates)]
content_dates = [d for d in content_dates if d]
site_updated = max(content_dates) if content_dates else (
    git(["log", "-1", "--format=%cs"]) or datetime.date.today().isoformat()
)

site = {
    "updatedAt": site_updated,
    "posts": len(posts),
    "aboutHeading": about.get("aboutHeading", "") or "关于本站",
    "aboutBody": about.get("body", "") or "",
    "cfToken": (about.get("cfToken", "") or "").strip(),
}

# ---------- 项目记录（updated 填 auto 时取本站更新时间） ----------
projects = load("projects", ["name", "status", "stack", "updated", "link"])
for p in projects:
    p["name"] = p["name"] or p["slug"]
    if p["updated"] == "auto":
        p["updated"] = site["updatedAt"]
projects.sort(key=lambda x: (x["updated"], x["name"]), reverse=True)

# ---------- GitHub 活跃（构建时抓取；失败则保留上一份，不影响构建） ----------
def fetch_contributions(user):
    url = "https://github-contributions-api.jogruber.de/v4/%s?y=last" % user
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "blog-build"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        days = [{"d": x.get("date"), "c": int(x.get("count") or 0), "l": int(x.get("level") or 0)}
                for x in data.get("contributions", []) if x.get("date")]
        if not days:
            print("  ! 贡献数据为空，保留旧文件")
            return None
        total = (data.get("total") or {}).get("lastYear")
        if total is None:
            total = sum(x["c"] for x in days)
        return {"user": user, "total": int(total), "days": days}
    except Exception as e:
        print("  ! 贡献数据抓取失败（保留旧文件）：%s" % e)
        return None


# ---------- 输出 ----------
print("build-data:")
write_json("posts.json", posts)
write_json("notices.json", notices)
write_json("updates.json", updates)
write_json("projects.json", projects)
write_json("site.json", site)
gh_user = (about.get("githubUser") or "Liu-Tangguo").strip()
contrib = fetch_contributions(gh_user)
if contrib:
    write_json("contributions.json", contrib)
else:
    print("  contributions.json 保持原样")
print("  posts=%d notices=%d updates=%d projects=%d updatedAt=%s" % (
    len(posts), len(notices), len(updates), len(projects), site_updated))
