// IndexedDB: the browser's backup copy. The SQLite database behind serve.py is the main record.
// Every trial is written here first (synced: false), then sent to the server, then marked synced.
// If the server is unreachable, unsynced trials wait here and are sent on the next attempt.

const DB_NAME = 'listening-test';
const VERSION = 1;
let opening = null;

function open() {
  if (!opening) {
    opening = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains('sessions')) db.createObjectStore('sessions', { keyPath: 'session_id' });
        if (!db.objectStoreNames.contains('trials')) {
          const trials = db.createObjectStore('trials', { keyPath: ['session_id', 'trial_index'] });
          trials.createIndex('by_session', 'session_id');
        }
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => { opening = null; reject(req.error); };
    });
  }
  return opening;
}

async function run(store, mode, fn) {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store, mode);
    let result;
    const req = fn(tx.objectStore(store));
    if (req) req.onsuccess = () => { result = req.result; };
    tx.oncomplete = () => resolve(result);       // resolve only once the write is durable
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

export const storage = {
  saveSession: (session) => run('sessions', 'readwrite', (s) => s.put(session)),
  getSession: (id) => run('sessions', 'readonly', (s) => s.get(id)),
  allSessions: () => run('sessions', 'readonly', (s) => s.getAll()),

  // A trial already stored keeps its original answers: a retry can never overwrite them.
  async saveTrial(trial) {
    const existing = await run('trials', 'readonly', (s) => s.get([trial.session_id, trial.trial_index]));
    if (existing) return existing;
    await run('trials', 'readwrite', (s) => s.put(trial));
    return trial;
  },
  async markSynced(sessionId, index) {
    const t = await run('trials', 'readonly', (s) => s.get([sessionId, index]));
    if (t && !t.synced) await run('trials', 'readwrite', (s) => s.put({ ...t, synced: true }));
  },
  async markRejected(sessionId, index, reason) {
    const t = await run('trials', 'readonly', (s) => s.get([sessionId, index]));
    if (t) await run('trials', 'readwrite', (s) => s.put({ ...t, rejected: reason }));
  },
  getTrials: (sessionId) => run('trials', 'readonly', (s) => s.index('by_session').getAll(sessionId)),
  allTrials: () => run('trials', 'readonly', (s) => s.getAll()),

  setActive: (id) => run('meta', 'readwrite', (s) => s.put({ key: 'active', value: id })),
  async getActive() {
    const row = await run('meta', 'readonly', (s) => s.get('active'));
    return row ? row.value : null;
  },
  clearActive: () => run('meta', 'readwrite', (s) => s.delete('active')),
};
