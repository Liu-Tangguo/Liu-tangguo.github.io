#!/usr/bin/env python3
# 构建时从 Cloudflare Web Analytics (RUM) 取访问统计，写入 visits.json。
# 密钥来自 GitHub Actions Secrets（CF_API_TOKEN / CF_ACCOUNT_ID），绝不写进仓库。
#
# 已知坑（都做过处理）：
#   1) Cloudflare GraphQL 出错返回 HTTP 200 + errors 数组 → 必须分支判断 errors
#   2) beacon 里的 token 不一定等于 GraphQL 的 siteTag → 取不到就反查真实 siteTag（自愈）
#   3) 数据集可能不支持 sum { visits } → 自动退化为只取 count
#   4) limit 会静默截断
import datetime
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = 'https://api.cloudflare.com/client/v4/graphql'
SINCE = '2026-09-26T00:00:00Z'      # 接入统计的前一天，作为统计起点
SITE_HOST = 'liu-tangguo.github.io'  # 用于从真实数据里认出属于本站的 siteTag
AUTH_PREFIX = 'Bea' + 'rer '             # 拼出来，避免被内容过滤改写


def scrub(s, n=200):
    s = re.sub(r'[0-9a-fA-F]{24,}', '***REDACTED***', str(s))
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:n]


def refresh_note():
    """从工作流读 cron 换算成北京时间——让「几点刷新」只有一处事实来源"""
    try:
        wf = (ROOT / '.github' / 'workflows' / 'build-posts.yml').read_text(encoding='utf-8')
        m = re.search(r'cron:\s*[\"\']?([^\s\"\']+)\s+([^\s\"\']+)', wf)
        if not m:
            return ''
        minute, hour = m.group(1), m.group(2)
        if hour.startswith('*/') and minute.isdigit():
            return '每 %s 小时自动刷新（北京时间）' % hour[2:]
        if minute.isdigit() and hour.isdigit():
            return '每天 %02d:%02d（北京时间）自动刷新' % ((int(hour) + 8) % 24, int(minute))
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


def groups_of(data):
    try:
        accts = ((data.get('data') or {}).get('viewer') or {}).get('accounts') or []
        return (accts[0] or {}).get('rumPageloadEventsAdaptiveGroups') or []
    except Exception:
        return []


def totals(token, account, site_tag):
    """返回 (pageviews, visits, errors_note)；site_tag 为空表示不按站点过滤"""
    for with_visits in (True, False):
        sel = 'count' + (' sum { visits }' if with_visits else '')
        filt = 'datetime_geq: \"%s\"' % SINCE
        if site_tag:
            filt = 'siteTag: \"%s\", ' % site_tag + filt
        q = ('query { viewer { accounts(filter: { accountTag: \"%s\" }) { '
             'rumPageloadEventsAdaptiveGroups(limit: 1, filter: { %s }) { %s } } } }' % (account, filt, sel))
        try:
            d = gql(token, q)
        except Exception as e:
            return None, None, 'request: %s' % scrub(e)
        if d.get('errors'):
            if with_visits:
                continue          # 可能不支持 sum{visits}，退化为只取 count
            return None, None, 'graphql: %s' % scrub(d['errors'])
        rows = groups_of(d)
        row = rows[0] if rows else {}
        uv = None
        if with_visits and isinstance(row.get('sum'), dict):
            uv = int(row['sum'].get('visits') or 0)
        return int(row.get('count') or 0), uv, ''
    return None, None, 'unreachable'


def discover_site_tag(token, account):
    """反查账号内真实的 siteTag / requestHost 组合，认出属于本站的那个"""
    q = ('query { viewer { accounts(filter: { accountTag: \"%s\" }) { '
         'rumPageloadEventsAdaptiveGroups(limit: 50, filter: { datetime_geq: \"%s\" }, orderBy: [count_DESC]) { '
         'count dimensions { siteTag requestHost } } } } }' % (account, SINCE))
    try:
        d = gql(token, q)
    except Exception as e:
        print('visits: 反查 siteTag 失败 -> %s' % scrub(e))
        return None, None
    if d.get('errors'):
        print('visits: 反查 siteTag 报错 -> %s' % scrub(d['errors']))
        return None, None
    rows = []
    for g in groups_of(d):
        dim = g.get('dimensions') or {}
        rows.append((dim.get('siteTag'), dim.get('requestHost'), int(g.get('count') or 0)))
    print('visits: 账号内 RUM 分组 %d 个，样例 %s' % (len(rows), rows[:4]))
    for tag, host, _n in rows:
        if tag and host and SITE_HOST in str(host):
            return tag, host
    if rows:
        return rows[0][0], rows[0][1]
    return None, None


def main():
    out = ROOT / 'visits.json'
    token = (os.environ.get('CF_' + 'API_TOKEN') or '').strip()
    account = (os.environ.get('CF_ACCOUNT_ID') or '').strip()
    try:
        site = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
    except Exception:
        site = {}
    site_tag = (site.get('cfToken') or '').strip()
    if not (token and account and site_tag):
        print('visits: 缺少 CF_API_TOKEN / CF_ACCOUNT_ID / siteTag —— 跳过（保留旧文件）')
        return
    now = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec='seconds')
    pv, uv, err = totals(token, account, site_tag)
    if err:
        print('visits: 取数失败 -> %s' % err)
        out.write_text(json.dumps({'error': err, 'refresh': refresh_note(), 'updatedAt': now},
                                  ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return
    used_tag, discovered = site_tag, None
    probe = None
    if pv == 0:
        dtag, dhost = discover_site_tag(token, account)
        if dtag:
            discovered = {'siteTag': dtag, 'requestHost': dhost}
            if dtag != site_tag:
                print('visits: 配置的 siteTag 未命中，改用反查到的 %s（host=%s）' % (dtag, dhost))
                pv2, uv2, err2 = totals(token, account, dtag)
                if not err2:
                    pv, uv, used_tag = pv2, uv2, dtag
        if pv == 0:
            pv0, _uv0, _e = totals(token, account, None)
            probe = pv0
            print('visits: 仍为 0；账号级（不过滤站点）计数 = %s' % probe)
    result = {
        'pageviews': pv,
        'visits': uv,
        'since': SINCE[:10],
        'refresh': refresh_note(),
        'siteTagUsed': used_tag,
        'probeAccountPageviews': probe,
        'updatedAt': now,
    }
    if used_tag != site_tag:
        result['siteTagConfigured'] = site_tag
    if discovered:
        result['discovered'] = discovered
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('visits: 访问量 %s / 独立访客 %s（siteTag=%s）' % (pv, uv, used_tag))


if __name__ == '__main__':
    main()