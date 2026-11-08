/**
 * Invite secrets of report-chat rooms — kept ONLY on this device.
 *
 * The secret in the invite link is the chat's encryption key material
 * (see shared/lib/e2ee.ts). The server never sees it after joining, so a
 * room opened here is joinable again only while this storage keeps the
 * secret. Cleared storage ⇒ the room needs a fresh invite link — that is
 * the honest cost of end-to-end encryption, stated in the UI.
 */

const STORAGE_KEY = "smena.chat.keys";

type KeyMap = Record<string, string>;

function loadKeys(): KeyMap {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return {};
    const out: KeyMap = {};
    for (const [roomId, secret] of Object.entries(parsed)) {
      if (typeof secret === "string") out[roomId] = secret;
    }
    return out;
  } catch {
    return {};
  }
}

function storeKeys(keys: KeyMap): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(keys));
  } catch {
    // Private mode: chats still work in this session, just not re-joinable.
  }
}

export function getChatKey(roomId: string): string | null {
  return loadKeys()[roomId] ?? null;
}

export function listChatKeys(): KeyMap {
  return loadKeys();
}

export function saveChatKey(roomId: string, inviteSecret: string): void {
  const keys = loadKeys();
  keys[roomId] = inviteSecret;
  storeKeys(keys);
}
