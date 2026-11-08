import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type ApiReportRoom } from "../../shared/api/client";
import { useApiToken, useAuth } from "../../shared/hooks/auth";
import { Button } from "../../shared/ui/Button";
import { EmptyState } from "../../shared/ui/EmptyState";
import { Skeleton } from "../../shared/ui/Skeleton";
import { navigate } from "../../shared/lib/routes";
import { deriveChatKey, decryptText, encryptText } from "../../shared/lib/e2ee";
import { saveChatKey } from "./chatKeys";

interface DecryptedMessage {
  id: string;
  mine: boolean;
  text: string;
  at: string;
}

const POLL_MS = 5_000;

/**
 * Report chat opened from an invite link (#/chat/<room>/<secret>).
 *
 * The secret from the hash is used twice: to join (the server checks its
 * SHA-256) and to derive the AES key here, on this device. Every message is
 * decrypted/encrypted locally — a reading server would see only base64.
 */
export function ChatPage({
  roomId,
  inviteToken,
}: {
  roomId: string;
  inviteToken: string;
}) {
  const token = useApiToken();
  const { status, handleUnauthorized } = useAuth();
  const myId = status.state === "authed" ? status.user.id : "";

  const [room, setRoom] = useState<ApiReportRoom | null>(null);
  const [key, setKey] = useState<CryptoKey | null>(null);
  const [joinState, setJoinState] = useState<"pending" | "ok" | "invalid">("pending");
  const [messages, setMessages] = useState<DecryptedMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  // Join with the invite secret and derive the local key.
  useEffect(() => {
    if (token === null) return;
    let cancelled = false;
    setJoinState("pending");
    (async () => {
      try {
        const joined = await api.joinReportRoom(token, roomId, inviteToken);
        saveChatKey(roomId, inviteToken);
        const derived = await deriveChatKey(inviteToken);
        if (cancelled) return;
        setRoom(joined);
        setKey(derived);
        setJoinState("ok");
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.isUnauthorized) {
          handleUnauthorized();
          return;
        }
        // 404 (bad room or bad secret) and unknown failures read the same:
        // the server never distinguishes them, and neither do we.
        setJoinState("invalid");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, roomId, inviteToken, handleUnauthorized]);

  // Poll the relay; messages arrive as ciphertext and decrypt here only.
  useEffect(() => {
    if (token === null || key === null || joinState !== "ok") return;
    let cancelled = false;

    async function fetchOnce(): Promise<void> {
      if (token === null || key === null) return;
      try {
        const rows = await api.listReportMessages(token, roomId);
        if (cancelled) return;
        const out: DecryptedMessage[] = [];
        for (const row of rows) {
          let plain: string;
          try {
            plain = await decryptText(key, row.ciphertext);
          } catch {
            plain = "Сообщение не расшифровывается (ключ не совпадает).";
          }
          out.push({
            id: row.id,
            mine: row.sender_id === myId,
            text: plain,
            at: row.created_at,
          });
        }
        out.sort((a, b) => a.at.localeCompare(b.at));
        setMessages(out);
      } catch {
        // A dropped poll is not an error on screen: the next tick retries.
      }
    }

    void fetchOnce();
    const timer = window.setInterval(() => void fetchOnce(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [token, key, roomId, joinState, myId, refreshNonce]);

  const submit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      if (token === null || key === null || sending || text.trim() === "") return;
      setSending(true);
      setSendError(null);
      try {
        await api.postReportMessage(token, roomId, await encryptText(key, text.trim()));
        setText("");
        setRefreshNonce((n) => n + 1);
      } catch (err) {
        if (err instanceof ApiError && err.isUnauthorized) handleUnauthorized();
        else if (err instanceof ApiError && err.serverMessage) setSendError(err.serverMessage);
        else setSendError("Не удалось отправить сообщение.");
      } finally {
        setSending(false);
      }
    },
    [token, key, roomId, sending, text, handleUnauthorized],
  );

  if (joinState === "invalid") {
    return (
      <EmptyState
        icon="lock"
        title="Ссылка недействительна"
        description="Комната или секрет не найдены. Попросите новую ссылку у создателя чата."
        action={
          <Button variant="secondary" onClick={() => navigate("#/reports")}>
            К отчётам
          </Button>
        }
      />
    );
  }

  if (joinState === "pending" || room === null) {
    return <Skeleton lines={4} />;
  }

  return (
    <>
      <div className="page-header">
        <div>
          <p className="eyebrow">ЗАЩИЩЁННЫЙ ЧАТ</p>
          <h1>{room.name}</h1>
          <p className="page-description">
            Сообщения и файлы читают только участники со ссылкой. Ключ
            шифрования — в самой ссылке, сервер видит только шифр.
          </p>
        </div>
      </div>

      <div className="chat-log" aria-live="polite">
        {messages.length === 0 && <p className="field-hint">Пока пусто.</p>}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`chat-message${m.mine ? " chat-message-mine" : ""}`}
          >
            <span className="chat-message-meta">
              {m.mine ? "Вы" : "Собеседник"} · {formatTime(m.at)}
            </span>
            <p>{m.text}</p>
          </div>
        ))}
      </div>

      <form className="chat-form" onSubmit={(e) => void submit(e)}>
        <input
          className="search-input"
          aria-label="Текст сообщения"
          placeholder="Сообщение…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={50_000}
        />
        <Button type="submit" busy={sending} disabled={text.trim() === ""}>
          Отправить
        </Button>
      </form>
      {sendError !== null && (
        <p className="form-error" role="alert">
          {sendError}
        </p>
      )}
    </>
  );
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
