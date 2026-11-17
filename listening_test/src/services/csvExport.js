// Export of the browser's backup copy. The main exports come from the server (with conditions);
// this one is for the rare case where the server copy is lost. It has no conditions and no names.

function cell(v) {
  const s = v === null || v === undefined ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv(header, rows) {
  return [header, ...rows].map((r) => r.map(cell).join(',')).join('\n') + '\n';
}

export function backupCsv(sessions, trials) {
  const byId = Object.fromEntries(sessions.map((s) => [s.session_id, s]));
  const header = ['participant_id', 'session_id', 'group', 'pilot', 'experience', 'presentation_order', 'clip_id',
    'liking', 'ending', 'attribution', 'replays', 'response_ms', 'answered_at', 'synced_to_server'];
  const rows = [...trials]
    .sort((a, b) => (a.session_id === b.session_id ? a.trial_index - b.trial_index : a.session_id < b.session_id ? -1 : 1))
    .map((t) => {
      const s = byId[t.session_id] || {};
      return [s.participant_id, t.session_id, s.group_no, s.pilot ? 1 : 0, s.experience, t.trial_index + 1, t.clip_id,
        t.liking, t.ending, t.attribution, t.replays, t.response_ms, t.answered_at, t.synced ? 1 : 0];
    });
  return toCsv(header, rows);
}

export function download(text, filename, type = 'text/csv;charset=utf-8') {
  const blob = new Blob([type.startsWith('text/csv') ? '﻿' + text : text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`;
}
