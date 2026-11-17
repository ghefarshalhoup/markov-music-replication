# Listening test app

This app runs the listening test described in [`reports/listening_test_plan.md`](../reports/listening_test_plan.md). It runs entirely on this laptop and needs no internet.

**Parts:**
- **Frontend:** React, Vite, Animate.css and mo.js, all bundled in `dist/`. The Inter font is included.
- **Server:** `serve.py`, which uses only Python's standard library. It serves the app and stores every answer in SQLite.

## Before the first session (once)

Python 3.11+ is needed. Node is needed only to rebuild the page.

```bash
cd listening_test
npm install        # only if node_modules is missing
npm run build      # makes dist/
```

## Each testing day

```bash
python listening_test/serve.py
```

Then open **http://127.0.0.1:8765** in Chrome or Edge.

**Always use the same browser and exactly this address.** The browser keeps its backup copy per address, and `localhost:8765` counts as a different address.

1. **Set up the session.** On the *New session* screen:
   - the participant ID (P01, P02 …) is assigned automatically;
   - the group alternates on its own, and you can override it;
   - the name is optional;
   - switch on *Pilot* for practice runs.
2. **Hand over the laptop** after pressing *Start experiment*.
3. **When the laptop comes back**, press **Ctrl + Shift + L** to open the dashboard, then *Start next participant*.

## Where the data goes

| File | Contents |
|---|---|
| `results/listening/listening.sqlite` | **Main record.** Sessions and every answer; no names. |
| `results/listening/names.sqlite` | Optional names, linked only by participant ID |
| `results/listening/trials_log.jsonl` | Append-only copy of each answer as it arrived |
| Browser storage (IndexedDB) | Backup copy and refresh recovery |

**How an answer is saved.** When the participant presses *Next*:
1. The answer is written to the browser's backup.
2. It is sent to the server, which stores it in SQLite.
3. It is marked as sent.

**If the server is briefly unreachable,** answers wait in the browser and are sent automatically later. The dashboard shows anything still waiting.

**Rules the server enforces:**
- Each answer is stored under (session, position), so a retry can never create a duplicate or change an answer.
- The clip order is drawn and saved once, at the start of a session. After a refresh, the participant continues at the first unanswered clip, in the same order. A clip that was half-played starts again.
- Conditions are never sent to the browser. They are joined in from `results/listening/clip_key.json` only when exporting.

**Exports** (dashboard, or the addresses below while the server runs):

| Address | Contents |
|---|---|
| `/api/export/answers.csv` | One row per clip heard, with condition, clip number and attention-check label. Pilots are marked `pilot = 1`. |
| `/api/export/sessions.csv` | One row per session, with its seed and full clip order |
| `/api/export/names.csv` | ID and name only; keep this private |

**Backup.** Copy the `results/listening/` folder to a USB stick after each testing day. Never put `names.sqlite` in a public repository.

## A trial run that doesn't touch the real data

```bash
python listening_test/serve.py --data some/other/folder
```

## Replacing the audio

1. Run `python -I scripts/make_listening_clips.py`. It rewrites `public/clips/*.mp3`, `clips.json` and `results/listening/clip_key.json` together.
2. Run `npm run build` again.

Do this before the first real participant, never in the middle of the study.
