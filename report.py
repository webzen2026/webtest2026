"""Vygeneruje index.html - přehledný report ze zjištěných výsledků."""
import html
import json
from pathlib import Path

STATUS_LABEL = {"ok": "OK", "warn": "Pozor", "fail": "Nefunguje"}
STATUS_COLOR = {"ok": "#1a9c5b", "warn": "#c78a00", "fail": "#d1373f"}
STATUS_BG = {"ok": "#e9f9f0", "warn": "#fff6e0", "fail": "#fdecec"}

# SHA-256 hash hesla pro zámek reportu. Heslo samotné NIKDE v repu není -
# jen jeho hash, ze kterého se heslo prakticky nedá zpětně zjistit.
# Pozn.: jde o ochranu proti náhodnému kolemjdoucímu / vyhledávačům, ne o
# skutečné zabezpečení - stránka je HTML/JS na veřejném GitHub Pages, takže
# šikovný člověk se znalostí vývojářských nástrojů by kontrolu hesla mohl
# obejít. Pro opravdu citlivá data by musel být celý repozitář Private.
PASSWORD_HASH_SHA256 = "6e5775e13223bba980afa2bd3e7346458312298f4fdb6376b8a037208cf6cf23"


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def load_history(history_path: Path, limit=30):
    if not history_path.exists():
        return []
    lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    return entries[-limit:]


def render_history_strip(history):
    if not history:
        return "<p class='muted'>Zatím žádná historie běhů.</p>"
    dots = []
    for entry in history:
        s = entry["summary"]
        status = "fail" if s["fail"] > 0 else ("warn" if s["warn"] > 0 else "ok")
        date = entry["run_at"][:10]
        title = f"{date}: {s['ok']} OK, {s['warn']} pozor, {s['fail']} nefunguje"
        dots.append(
            f"<span class='dot' style='background:{STATUS_COLOR[status]}' title='{esc(title)}'></span>"
        )
    return "<div class='history-strip'>" + "".join(dots) + "</div>"


def render_site_card(r):
    status = r["overall"]
    notes = r.get("notes") or []
    notes_html = "".join(f"<li>{esc(n)}</li>" for n in notes)

    broken = r.get("broken_links") or []
    broken_html = ""
    if broken:
        items = "".join(
            f"<li><a href='{esc(b['href'])}' target='_blank' rel='noopener'>{esc(b.get('text') or b['href'])}</a>"
            f" &mdash; {esc(b.get('status', b.get('error', '?')))}</li>"
            for b in broken[:10]
        )
        broken_html = f"<details><summary>Rozbité odkazy ({len(broken)})</summary><ul>{items}</ul></details>"

    console_errors = r.get("console_errors") or []
    console_html = ""
    if console_errors:
        items = "".join(f"<li>{esc(e)}</li>" for e in console_errors[:10])
        console_html = f"<details><summary>Konzolové chyby ({len(console_errors)})</summary><ul>{items}</ul></details>"

    failed_resources = r.get("failed_resources") or []
    failed_resources_html = ""
    if failed_resources:
        items = "".join(
            f"<li><a href='{esc(fr['url'])}' target='_blank' rel='noopener'>{esc(fr['url'])}</a>"
            f" &mdash; status {esc(fr['status'])}</li>"
            for fr in failed_resources[:10]
        )
        failed_resources_html = (
            f"<details open><summary>Nedostupné zdroje na stránce ({len(failed_resources)})</summary>"
            f"<ul>{items}</ul>"
            f"<p class='muted'>Tohle jsou přesné adresy, které vracely chybu 4xx/5xx - ukáže se to, "
            f"i když stránka jinak vypadá a funguje normálně (chybějící soubor/obrázek/skript, "
            f"co appka třeba ani nepotřebuje, nebo blokace automatizovaného testu third-party službou).</p>"
            f"</details>"
        )

    pwa = r.get("pwa") or {}
    pwa_html = ""
    if pwa.get("manifest_url"):
        pwa_ok = "✅" if pwa.get("manifest_ok") else "⚠️"
        sw = pwa.get("service_worker_registrations") or []
        sw_txt = ", ".join(sw) if sw else "žádný aktivní service worker"
        pwa_html = (
            f"<details><summary>PWA {pwa_ok}</summary>"
            f"<p>Manifest: <a href='{esc(pwa['manifest_url'])}' target='_blank' rel='noopener'>"
            f"{esc(pwa['manifest_url'])}</a></p><p>Service worker: {esc(sw_txt)}</p></details>"
        )

    custom = r.get("custom")
    custom_html = ""
    if custom is not None:
        ok = custom.get("tested") and custom.get("success_heuristic", True)
        icon = "✅" if ok else ("❓" if not custom.get("tested") else "⚠️")
        reason = custom.get("reason") or custom.get("note") or ""
        custom_html = (
            f"<details open><summary>Hloubkový test appky {icon}</summary>"
            f"<pre>{esc(json.dumps(custom, indent=2, ensure_ascii=False))}</pre>"
            + (f"<p class='muted'>{esc(reason)}</p>" if reason else "")
            + "</details>"
        )

    seo = r.get("seo") or {}
    seo_html = ""
    if seo:
        indexable = seo.get("indexable")
        icon = "✅" if indexable else ("❓" if indexable is None else "⚠️")
        blocked = seo.get("blocked_reasons") or []
        blocked_html = "".join(f"<li>{esc(b)}</li>" for b in blocked)
        sitemap_txt = (
            "ano" if seo.get("sitemap_exists") else ("ne" if seo.get("sitemap_exists") is False else "?")
        )
        canonical_txt = ""
        if seo.get("canonical_url"):
            mismatch = " ⚠️ míří jinam než tahle URL" if seo.get("canonical_mismatch") else ""
            canonical_txt = f"<p>Canonical: {esc(seo['canonical_url'])}{mismatch}</p>"
        seo_html = (
            f"<details><summary>Indexovatelnost Googlem {icon}</summary>"
            + (f"<ul>{blocked_html}</ul>" if blocked_html else "<p class='muted'>Nic nebrání indexaci.</p>")
            + f"<p class='muted'>sitemap.xml: {sitemap_txt}"
            + (f" &middot; URL v sitemap: {'ano' if seo.get('url_listed_in_sitemap') else 'ne/nezjištěno'}"
               if seo.get("sitemap_exists") else "")
            + "</p>"
            + canonical_txt
            + "</details>"
        )

    interactive = r.get("interactive") or []
    clicked_ok = sum(1 for i in interactive if i.get("clicked"))
    interactive_html = ""
    if interactive:
        interactive_html = (
            f"<p class='muted'>Vyzkoušeno {clicked_ok}/{len(interactive)} interaktivních prvků "
            f"(tlačítka, formuláře - kromě donate/platba).</p>"
        )

    load_time = r.get("load_time_ms")
    load_time_txt = f"{load_time} ms" if load_time is not None else "-"

    return f"""
    <div class="card status-{status}">
      <div class="card-head">
        <span class="badge" style="background:{STATUS_BG[status]};color:{STATUS_COLOR[status]}">
          {STATUS_LABEL[status]}
        </span>
        <h3><a href="{esc(r['url'])}" target="_blank" rel="noopener">{esc(r['name'])}</a></h3>
      </div>
      <p class="muted">HTTP {esc(r.get('status_code')) or 'nedostupné'} &middot; načtení {load_time_txt}
        &middot; zkontrolováno odkazů: {esc(r.get('links_checked'))}</p>
      {"<ul class='notes'>" + notes_html + "</ul>" if notes_html else ""}
      {interactive_html}
      {custom_html}
      {pwa_html}
      {seo_html}
      {broken_html}
      {console_html}
      {failed_resources_html}
    </div>
    """


def render_report(payload, history_path: Path):
    results = payload["results"]
    summary = payload["summary"]
    run_at = payload["run_at"]
    history = load_history(history_path)

    order = {"fail": 0, "warn": 1, "ok": 2}
    results_sorted = sorted(results, key=lambda r: order.get(r["overall"], 3))

    cards_html = "\n".join(render_site_card(r) for r in results_sorted)
    history_html = render_history_strip(history)

    overall_status = "fail" if summary["fail"] else ("warn" if summary["warn"] else "ok")

    return f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kontrola webů - denní report</title>
<style>
  :root {{
    --bg: #f6f7f9; --card-bg: #ffffff; --text: #1a1c1e; --muted: #6b7280; --border: #e5e7eb;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #14161a; --card-bg: #1e2126; --text: #e8eaed; --muted: #9aa0a6; --border: #33373d; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 16px 60px; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  }}
  .container {{ max-width: 860px; margin: 0 auto; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .muted {{ color: var(--muted); font-size: 0.9rem; }}
  .summary {{
    display: flex; gap: 12px; margin: 20px 0; flex-wrap: wrap;
  }}
  .summary .pill {{
    padding: 10px 16px; border-radius: 10px; font-weight: 600; font-size: 0.95rem;
  }}
  .history-strip {{ display: flex; gap: 4px; flex-wrap: wrap; margin: 12px 0 24px; }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
  .card {{
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px;
    padding: 16px 18px; margin-bottom: 14px;
  }}
  .card-head {{ display: flex; align-items: center; gap: 10px; }}
  .card-head h3 {{ margin: 0; font-size: 1.05rem; }}
  .card-head a {{ color: var(--text); text-decoration: none; }}
  .card-head a:hover {{ text-decoration: underline; }}
  .badge {{
    display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 700;
  }}
  ul.notes {{ margin: 8px 0; padding-left: 18px; }}
  details {{ margin-top: 8px; }}
  summary {{ cursor: pointer; font-size: 0.88rem; }}
  pre {{
    background: var(--bg); border-radius: 8px; padding: 10px; overflow-x: auto; font-size: 0.78rem;
  }}
  a {{ color: #3468eb; }}
  footer {{ margin-top: 30px; }}
  .lock-screen {{
    position: fixed; inset: 0; display: flex; align-items: center; justify-content: center;
    background: var(--bg); z-index: 10; padding: 16px;
  }}
  .lock-box {{
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 14px;
    padding: 28px 24px; width: 100%; max-width: 320px; text-align: center;
  }}
  .lock-box h2 {{ margin: 0 0 16px; font-size: 1.1rem; }}
  .lock-box input {{
    width: 100%; padding: 10px 12px; border-radius: 8px; border: 1px solid var(--border);
    background: var(--bg); color: var(--text); font-size: 1rem; margin-bottom: 10px; box-sizing: border-box;
  }}
  .lock-box button {{
    width: 100%; padding: 10px 12px; border-radius: 8px; border: none; background: #3468eb;
    color: white; font-size: 1rem; font-weight: 600; cursor: pointer;
  }}
  .lock-box button:hover {{ background: #2c56c4; }}
  .pw-error {{ color: #d1373f; font-size: 0.85rem; margin-top: 10px; }}
  .pw-note {{ color: var(--muted); font-size: 0.78rem; margin-top: 14px; }}
  .add-site-box {{
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px;
    padding: 14px 18px; margin: 18px 0; margin-top: 0;
  }}
  .add-site-box summary {{ font-size: 0.95rem; font-weight: 600; }}
  .add-site-form {{ margin-top: 12px; display: flex; flex-direction: column; gap: 10px; }}
  .add-site-form label {{ display: flex; flex-direction: column; gap: 4px; font-size: 0.85rem; }}
  .add-site-form label.checkbox-label {{ flex-direction: row; align-items: center; gap: 8px; }}
  .add-site-form ol.howto {{ margin: 0; padding-left: 20px; font-size: 0.88rem; display: flex; flex-direction: column; gap: 6px; }}
  #moduleHint {{ font-size: 0.78rem; }}
  .add-site-form input[type=text], .add-site-form input[type=url], .add-site-form select {{
    padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border);
    background: var(--bg); color: var(--text); font-size: 0.9rem;
  }}
  .add-site-form code {{
    background: var(--bg); padding: 1px 5px; border-radius: 4px; font-size: 0.85em;
  }}
  .add-site-form button {{
    align-self: flex-start; padding: 8px 14px; border-radius: 8px; border: none;
    background: #3468eb; color: white; font-size: 0.88rem; font-weight: 600; cursor: pointer;
  }}
  .add-site-form button:hover {{ background: #2c56c4; }}
  #generateSiteOutputWrap {{ display: flex; flex-direction: column; gap: 8px; margin-top: 4px; }}
  #generateSiteOutput {{
    width: 100%; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border);
    background: var(--bg); color: var(--text); font-family: monospace; font-size: 0.82rem; resize: vertical;
  }}
</style>
</head>
<body>

<div class="lock-screen" id="lockScreen">
  <div class="lock-box">
    <h2>🔒 Report je zamčený</h2>
    <input type="password" id="pwInput" autocomplete="current-password" placeholder="Heslo" autofocus>
    <button id="pwSubmit" type="button">Odemknout</button>
    <p class="pw-error" id="pwError" style="display:none">Špatné heslo, zkus to znovu.</p>
    <p class="pw-error" id="pwUnsupported" style="display:none">
      Tenhle prohlížeč/kontext nepodporuje ověření hesla (potřeba HTTPS - zkus otevřít stránku
      přes https://, ne jako lokální soubor).
    </p>
    <p class="pw-note">Heslo si pamatuje jen tenhle prohlížeč na tomhle zařízení.</p>
  </div>
</div>

<div class="container" id="mainContent" style="display:none">
  <p class="muted" style="text-align:right; margin-bottom:0;">
    <a href="#" id="lockAgainLink">🔒 Zamknout report na tomhle zařízení</a>
  </p>
  <h1>Kontrola webů - denní report</h1>
  <p class="muted">Poslední běh: {esc(run_at)}</p>

  <div class="summary">
    <span class="pill" style="background:{STATUS_BG['ok']};color:{STATUS_COLOR['ok']}">✅ OK: {summary['ok']}</span>
    <span class="pill" style="background:{STATUS_BG['warn']};color:{STATUS_COLOR['warn']}">⚠️ Pozor: {summary['warn']}</span>
    <span class="pill" style="background:{STATUS_BG['fail']};color:{STATUS_COLOR['fail']}">❌ Nefunguje: {summary['fail']}</span>
  </div>

  <details class="add-site-box">
    <summary>➕ Přidat web do seznamu</summary>
    <div class="add-site-form">
      <p class="muted">Report je statická stránka bez serveru na pozadí, takže se sem nedá nic uložit
        přímo. Tenhle formulář si ale na pozadí stáhne tvůj aktuální <code>sites.json</code> z GitHubu,
        přidá do něj nový web a vygeneruje ti CELÝ nový soubor - stačí ho zkopírovat a na GitHubu
        přepsat celý starý obsah, žádné ruční vkládání na správné místo.</p>
      <p class="muted" id="sitesLoadStatus">⏳ Načítám aktuální sites.json z GitHubu...</p>

      <ol class="howto">
        <li>Vyplň dole URL, název a typ kontroly a klikni na <strong>Vygenerovat celý sites.json</strong>.</li>
        <li>Klikni na <strong>📋 Zkopírovat</strong>.</li>
        <li>Jdi na GitHub do repozitáře <code>webzen2026/webtest2026</code>, otevři soubor
          <code>sites.json</code> a klikni na tužku (Edit).</li>
        <li>V editoru označ úplně všechno (Ctrl+A / Cmd+A) a vlož místo toho zkopírovaný text
          (Ctrl+V / Cmd+V) - přepíšeš tak celý soubor najednou.</li>
        <li>Dole klikni <strong>Commit changes...</strong> a potvrď uložení.</li>
      </ol>
      <p class="muted">Hotovo - další běh kontroly (ruční přes "Run workflow" nebo příští naplánovaný)
        už poběží s novým webem v seznamu. V reportu se objeví až po tomhle dalším běhu, ne hned.</p>
      <p class="muted">⚠️ Pokud jsi <code>sites.json</code> upravil teď před chvílí (v posledních pár
        minutách) a chceš přidat další web hned potom, klikni nejdřív na "🔄 Obnovit aktuální seznam"
        dole - GitHub totiž soubory chvíli cachuje a bez obnovení bys mohl vygenerovat soubor bez té
        úplně poslední změny.</p>

      <label>URL stránky
        <input type="url" id="newSiteUrl" placeholder="https://synthlucida.com/...">
      </label>
      <label>Název (jak se zobrazí v reportu)
        <input type="text" id="newSiteName" placeholder="Např. Nová appka">
      </label>
      <label>Typ kontroly
        <select id="newSiteModule">
          <option value="generic">Obecná (generic) - pro většinu stránek</option>
          <option value="relaxplayer">RelaxPlayer - hloubkový test přehrávání zvuku</option>
          <option value="webzenith_generator">WEBZENith generátor - hloubkový test generátoru</option>
        </select>
        <span class="muted" id="moduleHint"></span>
      </label>
      <label class="checkbox-label">
        <input type="checkbox" id="newSiteSkip"> Vynechat z kontroly (přidá se do sites.json, ale bude se přeskakovat)
      </label>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button type="button" id="generateSiteBtn">Vygenerovat celý sites.json</button>
        <button type="button" id="refreshSitesBtn">🔄 Obnovit aktuální seznam</button>
      </div>
      <div id="generateSiteOutputWrap" style="display:none">
        <textarea id="generateSiteOutput" readonly rows="16"></textarea>
        <button type="button" id="copySiteBtn">📋 Zkopírovat</button>
      </div>
    </div>
  </details>

  <p class="muted">Historie posledních běhů (nejnovější vpravo):</p>
  {history_html}

  {cards_html}

  <footer class="muted">
    <p>Automaticky generováno skriptem check_sites.py přes GitHub Actions. Klikni na "Hloubkový test appky"
    nebo "Rozbité odkazy"/"Konzolové chyby" pro detail.</p>
  </footer>
</div>

<script>
(function() {{
  var PASSWORD_HASH = "{PASSWORD_HASH_SHA256}";
  var STORAGE_KEY = "webtest2026_unlocked_v1";

  var lockScreen = document.getElementById('lockScreen');
  var mainContent = document.getElementById('mainContent');
  var pwInput = document.getElementById('pwInput');
  var pwSubmit = document.getElementById('pwSubmit');
  var pwError = document.getElementById('pwError');
  var pwUnsupported = document.getElementById('pwUnsupported');

  function showContent() {{
    lockScreen.style.display = 'none';
    mainContent.style.display = 'block';
  }}

  function sha256Hex(text) {{
    var enc = new TextEncoder().encode(text);
    return crypto.subtle.digest('SHA-256', enc).then(function(buf) {{
      var bytes = Array.from(new Uint8Array(buf));
      return bytes.map(function(b) {{ return b.toString(16).padStart(2, '0'); }}).join('');
    }});
  }}

  if (!window.crypto || !window.crypto.subtle) {{
    pwUnsupported.style.display = 'block';
    pwSubmit.disabled = true;
  }} else {{
    var alreadyUnlocked = false;
    try {{ alreadyUnlocked = localStorage.getItem(STORAGE_KEY) === '1'; }} catch (e) {{}}

    if (alreadyUnlocked) {{
      showContent();
    }} else {{
      function attemptUnlock() {{
        pwError.style.display = 'none';
        sha256Hex(pwInput.value).then(function(hash) {{
          if (hash === PASSWORD_HASH) {{
            try {{ localStorage.setItem(STORAGE_KEY, '1'); }} catch (e) {{}}
            showContent();
          }} else {{
            pwError.style.display = 'block';
            pwInput.value = '';
            pwInput.focus();
          }}
        }});
      }}
      pwSubmit.addEventListener('click', attemptUnlock);
      pwInput.addEventListener('keydown', function(e) {{
        if (e.key === 'Enter') attemptUnlock();
      }});
    }}
  }}

  document.addEventListener('click', function(e) {{
    if (e.target && e.target.id === 'lockAgainLink') {{
      e.preventDefault();
      try {{ localStorage.removeItem(STORAGE_KEY); }} catch (err) {{}}
      location.reload();
    }}
  }});

  var MODULE_HINTS = {{
    generic: 'Zkontroluje dostupnost, rychlost, JS chyby, rozbité odkazy, PWA a proklikne tlačítka/formuláře (kromě donate/platba). Hodí se pro naprostou většinu stránek.',
    relaxplayer: 'Navíc k obecnému testu zkusí appku reálně přehrát zvuk (klikne na Play a ověří, že se spustí audio nebo běží časovač). Použij jen u appek s přehrávačem (RelaxPlayer, Ambient Flow apod.) - u jiných stránek by to jen zbytečně hlásilo "Pozor".',
    webzenith_generator: 'Navíc k obecnému testu vyplní vzorová data do formuláře a ověří, že se objeví v živém náhledu nebo jde stáhnout výsledek. Použij jen u WEBZENith generátoru.'
  }};
  var moduleSelect = document.getElementById('newSiteModule');
  var moduleHint = document.getElementById('moduleHint');
  function updateModuleHint() {{
    if (moduleSelect && moduleHint) {{
      moduleHint.textContent = MODULE_HINTS[moduleSelect.value] || '';
    }}
  }}
  if (moduleSelect) {{
    moduleSelect.addEventListener('change', updateModuleHint);
    updateModuleHint();
  }}

  // Adresa syrového (raw) sites.json - veřejné čtení z GitHubu, bez tokenu,
  // žádné zapisování. Slouží jen k tomu, aby formulář znal aktuální seznam
  // webů a mohl vygenerovat CELÝ nový soubor místo jednoho řádku k vkládání.
  var SITES_JSON_RAW_URL = 'https://raw.githubusercontent.com/webzen2026/webtest2026/main/sites.json';
  var currentSitesConfig = null;
  var loadStatusEl = document.getElementById('sitesLoadStatus');

  function formatSitesJson(cfg) {{
    var lines = ['{{'];
    if (cfg._comment !== undefined) {{
      lines.push('  "_comment": ' + JSON.stringify(cfg._comment) + ',');
    }}
    lines.push('  "sites": [');
    cfg.sites.forEach(function(s, i) {{
      var entry = '    {{ "url": ' + JSON.stringify(s.url) + ', "name": ' + JSON.stringify(s.name) +
        ', "module": ' + JSON.stringify(s.module);
      if (s.skip) entry += ', "skip": true';
      entry += ' }}';
      if (i < cfg.sites.length - 1) entry += ',';
      lines.push(entry);
    }});
    lines.push('  ],');
    lines.push('  "skip_link_keywords": ' + JSON.stringify(cfg.skip_link_keywords || []) + ',');
    lines.push('  "external_domains_skip_broken_link_check": ' +
      JSON.stringify(cfg.external_domains_skip_broken_link_check || []));
    lines.push('}}');
    return lines.join('\\n');
  }}

  function loadCurrentSites() {{
    if (loadStatusEl) loadStatusEl.textContent = '⏳ Načítám aktuální sites.json z GitHubu...';
    currentSitesConfig = null;
    fetch(SITES_JSON_RAW_URL + '?_=' + Date.now())
      .then(function(resp) {{
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        return resp.json();
      }})
      .then(function(cfg) {{
        currentSitesConfig = cfg;
        if (loadStatusEl) {{
          loadStatusEl.textContent = '✅ Aktuální seznam načten (' + (cfg.sites ? cfg.sites.length : 0) + ' webů).';
        }}
      }})
      .catch(function(err) {{
        if (loadStatusEl) {{
          loadStatusEl.textContent = '⚠️ Nepodařilo se stáhnout aktuální sites.json (' + err.message +
            '). Zkus "🔄 Obnovit aktuální seznam" - pokud to nepůjde ani napodruhé, přidej web ručně podle README.';
        }}
      }});
  }}
  loadCurrentSites();

  var refreshBtn = document.getElementById('refreshSitesBtn');
  if (refreshBtn) {{
    refreshBtn.addEventListener('click', loadCurrentSites);
  }}

  var genBtn = document.getElementById('generateSiteBtn');
  if (genBtn) {{
    genBtn.addEventListener('click', function() {{
      var url = document.getElementById('newSiteUrl').value.trim();
      var name = document.getElementById('newSiteName').value.trim();
      var mod = document.getElementById('newSiteModule').value;
      var skip = document.getElementById('newSiteSkip').checked;
      if (!url || !name) {{
        alert('Vyplň URL i název.');
        return;
      }}
      var out = document.getElementById('generateSiteOutput');
      if (!currentSitesConfig) {{
        alert('Aktuální seznam se ještě nepodařilo načíst - zkus chvíli počkat nebo klikni na "🔄 Obnovit aktuální seznam".');
        return;
      }}
      var dup = currentSitesConfig.sites.some(function(s) {{ return s.url === url; }});
      if (dup && !confirm('Tahle URL už v seznamu je - přidat ji i tak znovu?')) {{
        return;
      }}
      var newSite = {{ url: url, name: name, module: mod }};
      if (skip) newSite.skip = true;
      var newConfig = Object.assign({{}}, currentSitesConfig, {{
        sites: currentSitesConfig.sites.concat([newSite])
      }});
      out.value = formatSitesJson(newConfig);
      document.getElementById('generateSiteOutputWrap').style.display = 'flex';
      out.focus();
      out.select();
    }});
  }}

  var copyBtn = document.getElementById('copySiteBtn');
  if (copyBtn) {{
    copyBtn.addEventListener('click', function() {{
      var out = document.getElementById('generateSiteOutput');
      out.select();
      var copied = false;
      try {{
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(out.value);
          copied = true;
        }}
      }} catch (e) {{}}
      if (!copied) {{
        try {{ document.execCommand('copy'); }} catch (e2) {{}}
      }}
      copyBtn.textContent = '✅ Zkopírováno';
      setTimeout(function() {{ copyBtn.textContent = '📋 Zkopírovat'; }}, 1500);
    }});
  }}
}})();
</script>
</body>
</html>
"""
