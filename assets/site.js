/* 全站共用脚本：主题切换 / 时钟与运行天数 / 访问统计
   首页、搜索页、文章页共用这一份，改一处三页生效。 */
(function () {
  'use strict';

  /* ---------- 主题：跟随系统 / 亮色 / 暗色 三态循环 ---------- */
  var KEY = 'oc-theme';
  function system() { return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; }
  function stored() {
    try {
      var v = localStorage.getItem(KEY);
      return (v === 'dark' || v === 'light') ? v : 'auto';
    } catch (e) { return 'auto'; }
  }
  function forced() {
    try {
      var v = new URLSearchParams(location.search).get('theme');
      return (v === 'dark' || v === 'light') ? v : null;
    } catch (e) { return null; }
  }
  function label(m) { return m === 'auto' ? '主题：跟随系统' : (m === 'dark' ? '主题：暗色' : '主题：亮色'); }
  function applyMode(mode) {
    var t = mode === 'auto' ? system() : mode;
    var root = document.documentElement;
    root.setAttribute('data-theme', t);
    root.style.colorScheme = t;
    var btn = document.getElementById('themebtn');
    if (btn) {
      btn.setAttribute('data-mode', mode);
      btn.title = label(mode);
      btn.setAttribute('aria-label', label(mode));
    }
  }
  function saveMode(mode) {
    try {
      if (mode === 'auto') localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, mode);
    } catch (e) {}
  }
  var force = forced();
  var mode = force || stored();
  applyMode(mode);
  var tbtn = document.getElementById('themebtn');
  if (tbtn) {
    tbtn.addEventListener('click', function () {
      if (force) { force = null; mode = stored(); return; }
      mode = mode === 'auto' ? 'light' : (mode === 'light' ? 'dark' : 'auto');
      saveMode(mode);
      applyMode(mode);
    });
  }
  try {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
      if (mode === 'auto') applyMode('auto');
    });
  } catch (e) {}

  /* ---------- 时钟 / 日期 / 运行天数 ---------- */
  var WD = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
  var START = new Date(2026, 8, 26); /* 建站日：2026-09-26 */
  function p2(v) { return v < 10 ? '0' + v : '' + v; }
  function dateStr(d) { return d.getFullYear() + '-' + p2(d.getMonth() + 1) + '-' + p2(d.getDate()); }
  function runDays() {
    var d = new Date();
    var a = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    return Math.max(0, Math.floor((a - START) / 86400000));
  }
  function isPlaceholder(el) { return !el.textContent || /获取|加载|…|^\s*$/.test(el.textContent); }
  function tick() {
    var d = new Date();
    var clock = document.getElementById('clock');
    if (clock) clock.textContent = p2(d.getHours()) + ':' + p2(d.getMinutes()) + ':' + p2(d.getSeconds());
    var today = document.getElementById('today');
    if (today && isPlaceholder(today)) today.textContent = dateStr(d) + ' ' + WD[d.getDay()];
    var fd = document.getElementById('footerDate') || document.getElementById('footer-date');
    if (fd) fd.textContent = dateStr(d);
    var days = runDays();
    var a = document.getElementById('runDays');
    if (a) a.textContent = String(days);
    var b = document.getElementById('runDaysSide');
    if (b) b.textContent = days + ' 天';
    var c = document.getElementById('runDaysFooter');
    if (c) c.textContent = String(days);
    var e = document.getElementById('run-days');
    if (e) e.textContent = String(days);
  }
  tick();
  setInterval(tick, 1000);

  /* ---------- 访问统计：站点设置里填了 Cloudflare 令牌才加载 ---------- */
  var BEACON = 'https://static.cloudflareinsights.com/beacon.min.js';
  function extract(raw) {
    var s = String(raw || '').trim();
    if (!s) return '';
    var m = s.match(/token["']?\s*[:=]\s*["']([^"']+)["']/i);
    if (m) return m[1].trim();
    m = s.match(/[0-9a-f]{16,64}/i);
    if (m) return m[0];
    return s.replace(/["'<>\s]/g, '');
  }
  function inject(token) {
    if (!token) return;
    if (document.querySelector('script[data-cf-beacon]')) return;
    var s = document.createElement('script');
    s.type = 'module';
    s.src = BEACON;
    s.setAttribute('data-cf-beacon', JSON.stringify({ token: token }));
    document.head.appendChild(s);
  }
  function siteData(fn) {
    if (window.OCReady) {
      window.OCReady.then(function (OC) { fn(OC.site || {}); }).catch(function () {});
      return;
    }
    fetch('site.json?_=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) { if (j) fn(j); })
      .catch(function () {});
  }
  function beacon() { siteData(function (site) { if (site && site.cfToken) inject(extract(site.cfToken)); }); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', beacon);
  else beacon();
})();
