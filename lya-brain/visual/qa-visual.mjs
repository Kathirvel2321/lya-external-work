// qa-visual.mjs — drive the brain visual and assert the motion actually happens.
// Run: node "C:\Program Files\nodejs\node.exe" <browser.mjs> <url> --script ./qa-visual.mjs
export default async function run(page, ui) {
  const results = {};

  // ── content assertions (structure must match the research docs) ──
  results.structure = await page.evaluate(() => ({
    layers: document.querySelectorAll('.layer').length,          // expect 8  (L0..L7)
    steps:  document.querySelectorAll('.step').length,           // expect 10 (thinking loop)
    nodes:  document.querySelectorAll('.node').length,           // expect 8  (token path)
    tables: document.querySelectorAll('table').length,           // expect 2 (write rules 4x5, tiers 3x3)
    registers: document.querySelectorAll('.reg').length,         // expect 3  (saved/belief/refusal)
    zones: document.querySelectorAll('.z').length,               // expect 3  (A/B/C)
    waapi: typeof Element.prototype.animate === 'function',
    tailwindTag: !!document.querySelector('script[src*="tailwindcss"]'),
    motionFlag: !!window.__motion,
  }));

  // ── the layer cycle must actually move through L0 -> L7 ──
  const seenLayers = new Set();
  for (let i = 0; i < 14; i++) {
    const cur = await page.evaluate(() =>
      document.querySelector('.layer.hot')?.getAttribute('data-id') || null);
    if (cur) seenLayers.add(cur);
    await page.waitForTimeout(420);
  }
  results.layersAnimated = [...seenLayers].sort();
  results.layersCycleWorks = seenLayers.size >= 4;

  // ── click "Run a query" and confirm the loop steps light up ──
  await page.evaluate(() => document.getElementById('playLoop').click());
  const seenSteps = new Set();
  for (let i = 0; i < 26; i++) {
    const idx = await page.evaluate(() => {
      const el = document.querySelector('.step.hot');
      return el ? el.getAttribute('data-i') : null;
    });
    if (idx !== null) seenSteps.add(idx);
    await page.waitForTimeout(320);
  }
  results.loopStepsSeen = [...seenSteps].map(Number).sort((a, b) => a - b);
  results.loopAnimates = seenSteps.size >= 4;

  // ── click "Send a query" and confirm the token travels the rail ──
  await page.evaluate(() => document.getElementById('playPath').click());
  const seenNodes = new Set();
  for (let i = 0; i < 34; i++) {
    const id = await page.evaluate(() =>
      document.querySelector('.node.on')?.getAttribute('data-id') || null);
    if (id) seenNodes.add(id);
    await page.waitForTimeout(300);
  }
  results.nodesSeen = [...seenNodes];
  results.pathAnimates = seenNodes.size >= 4;

  // ── live animation count is the objective proof of "motion" ──
  results.liveAnimations = await page.evaluate(() => document.getAnimations().length);

  // ── the honest-claim text must be present (this page must not oversell) ──
  const body = await page.evaluate(() => document.body.innerText);
  results.honestyChecks = {
    saysProposal: /PROPOSAL/.test(body),
    saysNotWired: /not wired into the app/i.test(body),
    refusesUnhackable: /Unhackable.*does not exist/i.test(body),
    hasCompromiseClause: /COMPROMISE\s*≠\s*DISCLOSURE/.test(body),
    listsW1: /W-1/.test(body),
    listsW2: /W-2/.test(body),
    namesMeasuredHardware: /i3-1315U/.test(body) && /7\.71/.test(body),
  };
  results.allHonest = Object.values(results.honestyChecks).every(Boolean);

  return results;
}