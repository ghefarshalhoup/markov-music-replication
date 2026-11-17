// Calls to the local Python server (serve.py). Network failures throw OfflineError,
// answers the server refuses throw RejectedError, so callers can tell "try again later" from "never".

export class OfflineError extends Error {}
export class RejectedError extends Error {}

async function call(method, url, body) {
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: 'no-store',
    });
  } catch (e) {
    throw new OfflineError('The local server cannot be reached.');
  }
  const data = await res.json().catch(() => ({}));
  if (res.status >= 500) throw new OfflineError(data.error || `Server error ${res.status}`);
  if (!res.ok) throw new RejectedError(data.error || `Request refused (${res.status})`);
  return data;
}

export const api = {
  state: () => call('GET', '/api/state'),
  createSession: (group, pilot, name) => call('POST', '/api/session', { group, pilot, name }),
  getSession: (id) => call('GET', `/api/session/${id}`),
  event: (id, type, value) => call('POST', `/api/session/${id}/event`, { type, value }),
  saveTrial: (id, trial) => call('POST', `/api/session/${id}/trial`, trial),
};

export const exportUrls = {
  answers: '/api/export/answers.csv',
  sessions: '/api/export/sessions.csv',
  names: '/api/export/names.csv',
};
