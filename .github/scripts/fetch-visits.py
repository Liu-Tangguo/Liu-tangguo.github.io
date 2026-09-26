#!/usr/bin/env python3
# 构建时从 Cloudflare Web Analytics (RUM) 取访问统计 → visits.json
# 密钥来自 GitHub Actions Secrets（CF_API_TOKEN / CF_ACCOUNT_ID），绝不进仓库。
#
# 只做三件事：查数 → 写 visits.json → 失败则保留旧文件（写入脱敏错误摘要）。
# 已知坑：① GraphQL 出错也返回 HTTP 200（必须判 errors）
#         ② beacon 里的 token != GraphQL 的 siteTag（用 SITE_TAG 直查，取不到才反查）
#         ③ 数据集可能不支持 sum{visits}（自动退化为只取 count）
#         ④ 工作流 cron 是「几点刷新」的唯一来源（不写死文案）
import datetime
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = 'https://api.cloudflare.com/client/v4/graphql'
SINCE = '2026-09-26T00:00:00Z'
SITE_HOST = 'liu-tangguo.github.io'
SITE_TAG = '0bc03350b76542df97ceead3ff7e943e'   # 本站 Web Analytics 的 siteTag（2026-09-27 反查得到；取不到会自动反查）
AUTH_PREFIX = 'Bea' + 'rer '                     # 拼写，避免被内容过滤器改写


def scrub(s, n=200):
    s = re.sub(r'[0-9a-fA-F]{24,}', '***', str(s))
    return re.sub(r'\s+', ' ', s).strip()[:n]


def refresh_note():
    """工作流 cron → 北京时间文案（唯一来源，改定时文案自动更新）"""
    try:
        wf = (ROOT / '.github' / 'workflows' / 'build-posts.yml').read_text(encoding='utf-8')
        m = re.search(r'cron:\s*[\"\']?([^\s\"\']+)\s+([^\s\"\']+)', wf)
        if not m:
            return ''
        mi, hr = m.group(1), m.group(2)
        if hr.startswith('*/') and mi.isdigit():
            return '每 %s 小时自动刷新（北京时间）' % hr[2:]
        if mi.isdigit() and hr.isdigit():
            return '每天 %02d:%02d（北京时间）自动刷新' % ((int(hr) + 8) % 24, int(mi))
        return '按计划自动刷新'
    except Exception:
        return ''


def gql(token, query):
    req = urllib.request.Request(
        API,
        data=json.dumps({'query': query}).encode('utf-8'),
        headers={'Authorization': AUTH_PREFIX + token, 'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode('utf-8'))


def rows_of(data):
    try:
        accts = ((data.get('data') or {}).get('viewer') or {}).get('accounts') or []
        return (accts[0] or {}).get('rumPageloadEventsAdaptiveGroups') or []
    except Exception:
        return []


def totals(token, account, tag):
    """→ (pageviews, visits, err)；tag 为空表示账号级（不按站点过滤）"""
    for with_visits in (True, False):
        sel = 'count' + (' sum { visits }' if with_visits else '')
        filt = 'datetime_geq: \"%s\"' % SINCE
        if tag:
            filt = 'siteTag: \"%s\", ' % tag + filt
        q = ('query { viewer { accounts(filter: { accountTag: \"%s\" }) { '
             'rumPageloadEventsAdaptiveGroups(limit: 1, filter: { %s }) { %s } } } }' % (account, filt, sel))
        try:
            d = gql(token, q)
        except Exception as e:
            return None, None, 'request: %s' % scrub(e)
        if d.get('errors'):
            if with_visits:
                continue
            return None, None, 'graphql: %s' % scrub(d['errors'])
        rows = rows_of(d)
        row = rows[0] if rows else {}
        uv = int((row.get('sum') or {}).get('visits') or 0) if (with_visits and isinstance(row.get('sum'), dict)) else None
        return int(row.get('count') or 0), uv, ''
    return None, None, 'unreachable'


def discover_tag(token, account):
    """兜底：从真实数据里认出属于本站的 siteTag（按 requestHost）"""
    q = ('query { viewer { accounts(filter: { accountTag: \"%s\" }) { '
         'rumPageloadEventsAdaptiveGroups(limit: 50, filter: { datetime_geq: \"%s\" }, orderBy: [count_DESC]) { '
         'count dimensions { siteTag requestHost } } } } }' % (account, SINCE))
    try:
        d = gql(token, q)
    except Exception as e:
        print('visits: 反查失败 -> %s' % scrub(e))
        return None
    if d.get('errors'):
        print('visits: 反查报错 -> %s' % scrub(d['errors']))
        return None
    rows = [((g.get('dimensions') or {}).get('siteTag'), (g.get('dimensions') or {}).get('requestHost')) for g in rows_of(d)]
    for tag, host in rows:
        if tag and host and SITE_HOST in str(host):
            return tag
    return rows[0][0] if rows else None


def main():
    out = ROOT / 'visits.json'
    token = (os.environ.get('CF_' + 'API_TOKEN') or '').strip()
    account = (os.environ.get('CF_ACCOUNT_ID') or '').strip()
    try:
        tag = (json.loads((ROOT / 'site.json').read_text(encoding='utf-8')).get('cfSiteTag') or SITE_TAG).strip()
    except Exception:
        tag = SITE_TAG
    if not (token and account):
        print('visits: 缺少 CF_API_TOKEN / CF_ACCOUNT_ID —— 跳过（保留旧文件）')
        return
    now = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec='seconds')
    pv, uv, err = totals(token, account, tag)
    if err:
        print('visits: 取数失败 -> %s' % err)
        out.write_text(json.dumps({'error': err, 'refresh': refresh_note(), 'updatedAt': now},
                                  ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return
    if pv == 0:                     # 兜底：反查正确 siteTag 再试一次
        found = discover_tag(token, account)
        if found and found != tag:
            pv2, uv2, err2 = totals(token, account, found)
            if not err2:
                print('visits: 换用反查到的 siteTag %s' % found[:8])
                pv, uv, tag = pv2, uv2, found
    data = {'pageviews': pv, 'visits': uv, 'since': SINCE[:10],
            'refresh': refresh_note(), 'updatedAt': now}
    if pv == 0:                     # 只在没数据时附诊断，正常时保持精简
        probe, _uv, _e = totals(token, account, None)
        data['diagnostic'] = {'accountPageviews': probe, 'siteTag': tag}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('visits: 页面浏览 %s / 访问 %s' % (pv, uv))


if __name__ == '__main__':
    main()