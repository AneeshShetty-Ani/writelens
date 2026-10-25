"""Listen to your text: the browser's own speech synthesis reads it aloud a sentence at a time and
highlights the sentence being read. Nothing is sent to the WriteLens server."""

import html
import json
import math

import streamlit as st

MAX_HEIGHT = 340
CONTROLS_HEIGHT = 70  # the button row and gaps above the text box
LINE_HEIGHT = 28
CHARS_PER_LINE = 110  # a rough guess for the text box's width

PLAYER = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  body { margin: 0; font-family: Inter, system-ui, sans-serif; color: #F9FAFB; background: transparent; }
  .bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; }
  button, select { font: inherit; font-size: 14px; border-radius: 10px; padding: 6px 14px; cursor: pointer;
    border: 1px solid rgba(255,255,255,.15); background: rgba(30,41,59,.9); color: #F9FAFB; }
  button.main { background: #06B6D4; border-color: #06B6D4; color: #0B1220; font-weight: 700; }
  button:focus-visible, select:focus-visible { outline: 2px solid #22D3EE; outline-offset: 2px; }
  .note { color: #94A3B8; font-size: 13px; }
  .text { max-height: %(text_height)dpx; overflow-y: auto; line-height: 1.75; padding: 12px 16px; border-radius: 12px;
    background: rgba(30,41,59,.7); border: 1px solid rgba(255,255,255,.1); }
  .s { cursor: pointer; border-radius: 4px; padding: 1px 0; }
  .s:hover { background: rgba(6,182,212,.12); }
  .s.now { background: rgba(6,182,212,.35); color: #fff; }
</style></head><body>
<div class="bar">
  <button class="main" id="play">▶ Play</button>
  <button id="pause">❚❚ Pause</button>
  <button id="stop">■ Stop</button>
  <label class="note" for="rate">Speed</label>
  <select id="rate"><option value="0.8">Slow</option><option value="1" selected>Normal</option>
    <option value="1.25">Fast</option></select>
  <span class="note" id="status">Click any sentence to start from there.</span>
</div>
<div class="text" id="text">%(sentences_html)s</div>
<script>
const S = %(sentences_json)s;
const synth = window.speechSynthesis;
const status = document.getElementById("status");
const spans = Array.from(document.querySelectorAll(".s"));
let i = 0, playing = false, run = 0;

function voice() {
  const en = synth.getVoices().filter(v => /^en/i.test(v.lang));
  // voices on the device first: some browsers' online voices send the text to their maker
  return en.find(v => v.localService) || en[0] || null;
}
function mark(n) {
  spans.forEach((s, k) => s.classList.toggle("now", k === n));
  if (spans[n]) spans[n].scrollIntoView({block: "nearest", behavior: "smooth"});
}
function speak() {
  if (i >= S.length) { stop(); status.textContent = "Finished."; return; }
  mark(i);
  const id = ++run, u = new SpeechSynthesisUtterance(S[i]);
  u.rate = parseFloat(document.getElementById("rate").value);
  const v = voice(); if (v) { u.voice = v; u.lang = v.lang; }
  u.onend = () => { if (playing && id === run) { i++; speak(); } };
  synth.speak(u);
  status.textContent = "Reading sentence " + (i + 1) + " of " + S.length + ".";
}
function start(from) { run++; synth.cancel(); i = from; playing = true; speak(); }
function stop() { playing = false; run++; synth.cancel(); i = 0; mark(-1); status.textContent = "Stopped."; }

if (!("speechSynthesis" in window)) {
  document.querySelector(".bar").innerHTML = '<span class="note">This browser can\\'t read text aloud. Try Chrome, Edge or Safari.</span>';
} else {
  document.getElementById("play").onclick = () => {
    if (playing && synth.paused) { synth.resume(); status.textContent = "Reading..."; }
    else if (!playing) start(i);
  };
  document.getElementById("pause").onclick = () => { if (playing) { synth.pause(); status.textContent = "Paused."; } };
  document.getElementById("stop").onclick = stop;
  spans.forEach((s, k) => { s.onclick = () => start(k); });
  synth.getVoices();
}
</script></body></html>"""


def player_height(sentences: list[str]) -> int:
    """Tall enough for a short text, scrolling inside for a long one."""
    lines = math.ceil(sum(len(s) + 1 for s in sentences) / CHARS_PER_LINE) or 1
    return min(MAX_HEIGHT, CONTROLS_HEIGHT + 30 + lines * LINE_HEIGHT)


def listen_html(sentences: list[str]) -> str:
    # "</" is escaped so a sentence containing "</script>" can't close the script tag
    data = json.dumps(sentences).replace("</", "<\\/")
    spans = " ".join(f'<span class="s">{html.escape(s)}</span>' for s in sentences)
    return PLAYER % {"sentences_json": data, "sentences_html": spans, "text_height": MAX_HEIGHT - CONTROLS_HEIGHT}


def render_listen(sentences: list[str]) -> None:
    # st.iframe runs the page's script; the writer's text in it is escaped by listen_html()
    st.iframe(listen_html(sentences), height=player_height(sentences), alt="Read-aloud player")
