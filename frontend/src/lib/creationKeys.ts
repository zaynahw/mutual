/** Keep retry keys across aborted navigation, without storing form contents. */
export async function creationKey(actor: string, operation: string, input: unknown) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(input)));
  const hash = [...new Uint8Array(bytes)].map(byte => byte.toString(16).padStart(2, '0')).join('');
  const storageKey = `mutual-demo-create:${actor}:${operation}:${hash}`;
  const key = sessionStorage.getItem(storageKey) || crypto.randomUUID();
  sessionStorage.setItem(storageKey, key);
  return { key, confirmed: () => sessionStorage.removeItem(storageKey) };
}
