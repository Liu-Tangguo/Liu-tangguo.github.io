#!/usr/bin/env python3
# 构建时从 Cloudflare Web Analytics (RUM) 取访问统计，写入 visits.json。
# 密钥来自 GitHub Actions Secrets（CF_API_TOKEN / CF_ACCOUNT_ID），绝不写进仓库。
# 取不到时：保留旧数据；为便于排查，把「脱敏后的错误摘要」写进 visits.json。
import datetime
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = 'https://api.cloudflare.com/client/v4/graphql'
SINCE = '2026-09-26T00:00:00Z'   # 接入统计的前一天，作为统计起点


def scrub(s, n=200):
    s = re.sub(r'[0-9a-fA-F]{24,}', '***REDACTED***', str(s))
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:n]


def gql(token, payload):
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode('utf-8'))




def refresh_note():
    """从工作流里读 cron，换算成北京时间——让「几点刷新」只有一处事实来源"""
    try:
        wf = (ROOT / '.github' / 'workflows' / 'build-posts.yml').read_text(encoding='utf-8')
        m = re.search(r'cron:\s*["\']?([^\s"\']+)\s+([^\s"\']+)', wf)
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


def build_query(account, site_tag, with_visits):
    sel = 'count' + (' sum { visits }' if with_visits else '')
    filt = 'datetime_geq: "%s"' % SINCE
    if site_tag:
        filt = 'siteTag: "%s", ' % site_tag + filt
    q = ('query { viewer { accounts(filter: { accountTag: "%s" }) { '
         'rumPageloadEventsAdaptiveGroups(limit: 1, filter: { %s }) { %s } } } }' % (account, filt, sel))
    return {'query': q}


def first_row(data):
    try:
        accts = ((data.get('data') or {}).get('viewer') or {}).get('accounts') or []
        groups = (accts[0] or {}).get('rumPageloadEventsAdaptiveGroups') or []
        return groups[0] if groups else {}
    except Exception:
        return {}


def main():
    out = ROOT / 'visits.json'
    token = (os.environ.get('CF_API_TOKEN') or '').strip()
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
    result = None
    for with_visits in (True, False):
        try:
            data = gql(token, build_query(account, site_tag, with_visits))
        except Exception as e:
            msg = scrub(e)
            print('visits: 请求失败 -> %s' % msg)
            out.write_text(json.dumps({'error': msg, 'refresh': refresh_note(), 'updatedAt': now}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            return
        if data.get('errors'):
            msg = scrub(data['errors'])
            print('visits: GraphQL 报错 -> %s' % msg)
            if with_visits:
                print('visits: 退化为只查访问量（pageviews）')
                continue
            out.write_text(json.dumps({'error': msg, 'refresh': refresh_note(), 'updatedAt': now}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            return
        row = first_row(data)
        uv = None
        if with_visits and isinstance(row.get('sum'), dict):
            uv = int(row['sum'].get('visits') or 0)
        pv = int(row.get('count') or 0)
        probe = None
        if pv == 0:
            try:
                d2 = gql(token, build_query(account, None, False))
                if not d2.get('errors'):
                    probe = int(first_row(d2).get('count') or 0)
                    print('visits: 诊断为 0，账号级（不带 siteTag）计数 = %s' % probe)
            except Exception as e:
                print('visits: 诊断查询失败 %s' % scrub(e))
        result = {'pageviews': pv, 'visits': uv, 'since': SINCE[:10], 'refresh': refresh_note(),
                  'probeAccountPageviews': probe, 'updatedAt': now}
        break
    if not result:
        print('visits: 未取到数据，保留旧文件')
        return
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('visits: 访问量 %s 次 / 独立访客 %s' % (result['pageviews'], result['visits']))


if __name__ == '__main__':
    main()