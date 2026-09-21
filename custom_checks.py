"""
Hlubší (custom) testy pro konkrétní appky, kde obecný smoke-test nestačí.

Pozn.: Selektory tlačítek jsou napsané jako seznam "kandidátů" (více
možných způsobů, jak tlačítko najít), protože skript nemohl být odsud
naživo otestovaný proti reálným webům (viz README - "Proč to nebylo
otestované naživo"). Když poprvé spustíš workflow na GitHub Actions,
zkontroluj v reportu pole "custom" u RelaxPlayeru a WEBZENithu - pokud
tam bude "tested: false", uprav selektor podle skutečného HTML dané
stránky (stačí pravým tlačítkem -> Prozkoumat na tlačítku ve webu a
zjistit jeho id/class/text).
"""

# Vloží se do KAŽDÉ stránky ještě před tím, než se spustí její vlastní JS.
# "Obalí" AudioContext tak, aby si skript pamatoval všechny vytvořené
# instance - díky tomu jde po kliknutí na Play ověřit, jestli se zvuk
# opravdu spustil (AudioContext.state === "running"), bez znalosti
# vnitřní implementace stránky.
AUDIO_HOOK_INIT_SCRIPT = """
(() => {
  window.__testAudioContexts = [];
  const Orig = window.AudioContext || window.webkitAudioContext;
  if (Orig) {
    const Wrapped = function(...args) {
      const inst = new Orig(...args);
      window.__testAudioContexts.push(inst);
      return inst;
    };
    Wrapped.prototype = Orig.prototype;
    window.AudioContext = Wrapped;
    window.webkitAudioContext = Wrapped;
  }
})();
"""

PLAY_BUTTON_CANDIDATES = [
    "button:has-text('Play')",
    "button:has-text('play')",
    "button:has-text('Přehrát')",
    "button:has-text('Start')",
    "[aria-label*='play' i]",
    "#play", "#playBtn", "#play-btn", "#startBtn",
    ".play-button", ".play-btn", ".playBtn",
    "button[class*='play' i]",
    "[id*='play' i]",
    "button[id*='start' i]",
]

GENERATE_BUTTON_CANDIDATES = [
    "button:has-text('Generate')",
    "button:has-text('generate')",
    "button:has-text('Create')",
    "button:has-text('Build')",
    "button:has-text('Vygenerovat')",
    "button:has-text('Vytvořit')",
    "button:has-text('Sestavit')",
    "[id*='generat' i]",
    "[class*='generat' i]",
    "button[type='submit']",
]


async def _click_first_match(page, selectors, timeout=3000):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                await loc.click(timeout=timeout)
                return sel
        except Exception:
            continue
    return None


async def check_relaxplayer(page, context):
    """Reálně klikne na Play a ověří, že se spustilo přehrávání (AudioContext running)."""
    clicked = await _click_first_match(page, PLAY_BUTTON_CANDIDATES)
    if not clicked:
        return {
            "tested": False,
            "reason": "Play tlačítko nenalezeno žádným z kandidátních selektorů - "
                      "uprav PLAY_BUTTON_CANDIDATES v custom_checks.py podle skutečného HTML.",
        }
    await page.wait_for_timeout(3000)
    audio_states = await page.evaluate(
        "() => window.__testAudioContexts ? window.__testAudioContexts.map(c => c.state) : []"
    )
    playing = any(s == "running" for s in audio_states)
    return {
        "tested": True,
        "clicked_selector": clicked,
        "audio_context_states": audio_states,
        "success_heuristic": playing,
        "note": None if playing else (
            "Tlačítko se podařilo kliknout, ale žádný AudioContext nemá stav 'running'. "
            "Možné důvody: web používá <audio> element místo Web Audio API (v tom případě "
            "uprav tuhle funkci, ať místo AudioContextu kontroluje audio.paused===false), "
            "nebo přehrávání vyžaduje druhé kliknutí kvůli autoplay policy prohlížeče."
        ),
    }


async def check_webzenith_generator(page, context):
    """Vyplní generátor dummy daty, klikne na generování a ověří, že vznikl výstup."""
    inputs = page.locator("input[type='text'], input:not([type]), textarea")
    count = await inputs.count()
    filled = 0
    for i in range(min(count, 6)):
        el = inputs.nth(i)
        try:
            if await el.is_visible():
                await el.fill(f"Test Site {i + 1}")
                filled += 1
        except Exception:
            continue

    node_count_before = await page.evaluate("() => document.querySelectorAll('*').length")
    clicked = await _click_first_match(page, GENERATE_BUTTON_CANDIDATES)
    if not clicked:
        return {
            "tested": False,
            "inputs_filled": filled,
            "reason": "Generovací tlačítko nenalezeno - uprav GENERATE_BUTTON_CANDIDATES "
                      "v custom_checks.py podle skutečného HTML.",
        }
    await page.wait_for_timeout(3000)
    node_count_after = await page.evaluate("() => document.querySelectorAll('*').length")
    has_preview = await page.evaluate(
        "() => !!document.querySelector('iframe, a[download], a[href^=\"blob:\"]')"
    )
    dom_delta = node_count_after - node_count_before
    success = has_preview or dom_delta > 5
    return {
        "tested": True,
        "inputs_filled": filled,
        "clicked_selector": clicked,
        "dom_node_delta": dom_delta,
        "preview_or_download_detected": has_preview,
        "success_heuristic": success,
        "note": None if success else (
            "Kliknutí proběhlo, ale nenašel jsem náhled/iframe/odkaz ke stažení ani výraznou "
            "změnu stránky. Zkontroluj ručně, jestli generování funguje - heuristika může "
            "u specifického UI selhat."
        ),
    }


CUSTOM_MODULES = {
    "relaxplayer": check_relaxplayer,
    "webzenith_generator": check_webzenith_generator,
}
