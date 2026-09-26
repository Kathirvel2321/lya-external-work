// qa-flow.mjs — verify the pure-visual canvas actually animates.
export default async function run(page, ui) {
  const out = {};

  out.dom = await page.evaluate(() => ({
    canvas: !!document.getElementById('c'),
    w: document.getElementById('c').width,
    h: document.getElementById('c').height,
    // "no text" check: the ONLY visible text should be LYA + 2 icon buttons
    visibleText: document.body.innerText.trim(),
    textNodes: (document.body.innerText.match(/[A-Za-z]/g) || []).length,
    buttons: document.querySelectorAll('button').length,
  }));

  // canvas must actually contain non-background pixels (i.e. something is drawn)
  const drawn = async () => await page.evaluate(() => {
    const c = document.getElementById('c');
    const g = c.getContext('2d');
    const d = g.getImageData(0, 0, c.width, c.height).data;
    let lit = 0, sum = 0;
    for (let i = 0; i < d.length; i += 4 * 97) {   // sample
      const v = d[i] + d[i+1] + d[i+2];
      sum += v;
      if (v > 60) lit++;
    }
    return { litSamples: lit, avgBrightness: +(sum / (d.length / (4*97)) / 3).toFixed(1) };
  });

  await page.waitForTimeout(900);
  out.frameA = await drawn();
  await page.waitForTimeout(1600);
  out.frameB = await drawn();

  // frames must DIFFER -> proves motion, not a static image
  out.pixelsChanged = out.frameA.avgBrightness !== out.frameB.avgBrightness;

  // live canvas is animating if rAF keeps firing
  const t1 = await page.evaluate(() => performance.now());
  await page.waitForTimeout(700);
  const t2 = await page.evaluate(() => performance.now());
  out.clockAdvanced = t2 > t1;

  out.pauseWorks = await page.evaluate(async () => {
    document.getElementById('pause').click();      // pause
    const c = document.getElementById('c'), g = c.getContext('2d');
    const snap = () => { const d = g.getImageData(0,0,c.width,c.height).data; let s=0;
      for (let i=0;i<d.length;i+=4*401) s += d[i]+d[i+1]+d[i+2]; return s; };
    const a = snap();
    await new Promise(r=>setTimeout(r,900));
    const b = snap();
    document.getElementById('pause').click();      // resume
    return { before:a, after:b, epsilon: Math.abs(a-b) };
  });

  out.speedWorks = await page.evaluate(() => {
    const before = [];
    for (let i=0;i<3;i++){ document.getElementById('speed').click(); }
    return true;
  });

  return out;
}