/** Browser WebAuthn serialization. Only the server decides whether a proof is valid. */

export type RegistrationJSON = {
  challenge: string;
  rp: PublicKeyCredentialRpEntity;
  user: { id: string; name: string; displayName: string };
  pubKeyCredParams: PublicKeyCredentialParameters[];
  timeout?: number;
  attestation?: AttestationConveyancePreference;
  authenticatorSelection?: AuthenticatorSelectionCriteria;
  excludeCredentials?: { id: string; type: PublicKeyCredentialType }[];
};

export type AuthenticationJSON = {
  challenge: string;
  rpId?: string;
  timeout?: number;
  userVerification?: UserVerificationRequirement;
  allowCredentials?: { id: string; type: PublicKeyCredentialType }[];
};

function bytes(encoded: string): ArrayBuffer {
  const raw = atob(encoded.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(encoded.length / 4) * 4, "="));
  return Uint8Array.from(raw, (char) => char.charCodeAt(0)).buffer as ArrayBuffer;
}

function b64url(buffer: ArrayBuffer): string {
  const data = new Uint8Array(buffer);
  let text = "";
  for (const byte of data) text += String.fromCharCode(byte);
  return btoa(text).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function supported(): void {
  if (!window.isSecureContext || !window.PublicKeyCredential || !navigator.credentials) {
    throw new Error("Этот браузер не поддерживает подтверждение ключом устройства. Откройте Смену на телефоне через HTTPS.");
  }
}

export async function createSafePasskey(options: RegistrationJSON): Promise<Record<string, unknown>> {
  supported();
  const credential = (await navigator.credentials.create({
    publicKey: {
      ...options,
      challenge: bytes(options.challenge),
      user: { ...options.user, id: bytes(options.user.id) },
      excludeCredentials: options.excludeCredentials?.map((item) => ({ ...item, id: bytes(item.id) })),
    },
  })) as PublicKeyCredential | null;
  if (!credential) throw new Error("Создание ключа отменено");
  const response = credential.response as AuthenticatorAttestationResponse;
  return {
    id: credential.id,
    rawId: b64url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: b64url(response.clientDataJSON),
      attestationObject: b64url(response.attestationObject),
    },
  };
}

export async function confirmSafePasskey(options: AuthenticationJSON): Promise<Record<string, unknown>> {
  supported();
  const credential = (await navigator.credentials.get({
    publicKey: {
      ...options,
      challenge: bytes(options.challenge),
      allowCredentials: options.allowCredentials?.map((item) => ({ ...item, id: bytes(item.id) })),
    },
  })) as PublicKeyCredential | null;
  if (!credential) throw new Error("Подтверждение отменено");
  const response = credential.response as AuthenticatorAssertionResponse;
  return {
    id: credential.id,
    rawId: b64url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: b64url(response.clientDataJSON),
      authenticatorData: b64url(response.authenticatorData),
      signature: b64url(response.signature),
      userHandle: response.userHandle ? b64url(response.userHandle) : null,
    },
  };
}
