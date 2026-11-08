// @vitest-environment node
// The node environment provides real WebCrypto (Node ≥ 19 exposes
// globalThis.crypto); jsdom has no SubtleCrypto, so a browser-environment
// test here would only ever test a stub.
import { describe, expect, it } from "vitest";
import { decryptText, deriveChatKey, encryptText } from "./e2ee";

describe("e2ee report-chat crypto", () => {
  it("round-trips a message through AES-GCM", async () => {
    const key = await deriveChatKey("x".repeat(32));
    const text = "Отчёт по самообразованию — черновик №3 📄";
    const payload = await encryptText(key, text);
    expect(payload).not.toContain("Отчёт");
    expect(await decryptText(key, payload)).toBe(text);
  });

  it("produces a different ciphertext per call (random IV)", async () => {
    const key = await deriveChatKey("x".repeat(32));
    const a = await encryptText(key, "одинаковый текст");
    const b = await encryptText(key, "одинаковый текст");
    expect(a).not.toBe(b);
  });

  it("derives the same key from the same secret and different keys otherwise", async () => {
    const k1 = await deriveChatKey("secret-one");
    const k2 = await deriveChatKey("secret-one");
    const k3 = await deriveChatKey("secret-two");
    const payload = await encryptText(k1, "проверка");
    expect(await decryptText(k2, payload)).toBe("проверка");
    await expect(decryptText(k3, payload)).rejects.toThrow();
  });

  it("rejects tampered and truncated payloads", async () => {
    const key = await deriveChatKey("x".repeat(32));
    const payload = await encryptText(key, "важный отчёт");
    // The first base64 char carries IV bits: corrupting it must always
    // break GCM authentication (deterministic, unlike tail padding bits).
    const tampered = (payload[0] === "Q" ? "A" : "Q") + payload.slice(1);
    await expect(decryptText(key, tampered)).rejects.toThrow();
    await expect(decryptText(key, "c2hvcnQ=")).rejects.toThrow();
  });
});
