// Makes the TV app's spoken lines (ADR 0040): ElevenLabs v4, voice Maisie, through OpenRouter. Run it on a machine
// that has OPENROUTER_API_KEY in its environment (ours runs it in a container that already holds the key, so the key
// never leaves that machine; only the audio comes back):
//
//   OUT=/tmp/colors-voice-out node tv/voice/generate.mjs
//   python tv/voice/prepare.py /tmp/colors-voice-out     (trims, levels, writes app/src/main/res/raw/voice_*.mp3)
//
// TAKES=3 by default; IDS=a,b makes only those lines. DRY=1 lists the requests and makes nothing.
// The lines never contain a child's name (ADR 0034): nothing about the boys goes to the voice service.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const HERE = new URL('.', import.meta.url).pathname;
const KEY = process.env.OPENROUTER_API_KEY;
const DRY = process.env.DRY === '1';
const TAKES = Number(process.env.TAKES ?? 3);
const IDS = process.env.IDS ? process.env.IDS.split(',') : null;
const MODEL = 'elevenlabs/eleven-v4';
const MAISIE = 'QtY3JBOUKEB5xzrRfOKc'; // the kids app's narrator since Matilda's retirement (2026-12-31)
const OUT = process.env.OUT ?? `${HERE}out`; // the container user may not write where the script was copied

const lines = JSON.parse(readFileSync(`${HERE}lines.json`, 'utf8')).lines.filter((l) => !IDS || IDS.includes(l.id));
console.log(`${lines.length} lines x ${TAKES} takes = ${lines.length * TAKES} requests`);
if (DRY) { for (const l of lines) console.log(`  ${l.id}: ${l.say}`); process.exit(0); }
if (!KEY) { console.error('no key'); process.exit(1); }
mkdirSync(OUT, { recursive: true });

async function speak(body) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const r = await fetch('https://openrouter.ai/api/v1/audio/speech', {
      method: 'POST', headers: { Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: AbortSignal.timeout(120000),
    });
    if (r.ok) return Buffer.from(await r.arrayBuffer());
    const text = (await r.text()).slice(0, 300);
    if (r.status === 429 || r.status === 402 || r.status >= 500) { await new Promise((s) => setTimeout(s, 4000 * (attempt + 1))); continue; }
    throw new Error(`${r.status} ${text}`);
  }
  throw new Error('gave up after retries');
}

const manifest = { model: MODEL, voice: 'maisie', voiceId: MAISIE, clips: [], errors: [] };
for (const l of lines) {
  for (let take = 1; take <= TAKES; take++) {
    const file = `${l.id}-${take}.mp3`;
    try {
      writeFileSync(`${OUT}/${file}`, await speak({ model: MODEL, voice: MAISIE, input: l.say, response_format: 'mp3' }));
      manifest.clips.push({ id: l.id, take, file, input: l.say });
      console.log(`  ${file}`);
    } catch (e) { manifest.errors.push(`${file}: ${e.message}`); console.error(`  ${file}: ${e.message}`); }
  }
}
writeFileSync(`${OUT}/manifest.json`, JSON.stringify(manifest, null, 2));
console.log(`clips ${manifest.clips.length}, errors ${manifest.errors.length}`);
