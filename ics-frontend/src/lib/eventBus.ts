export type BusEvents = { 'session-invalid': void };
const listeners: { [K in keyof BusEvents]?: Array<(p: BusEvents[K]) => void> } = {};

export function on<K extends keyof BusEvents>(e: K, cb: (p: BusEvents[K]) => void) {
  listeners[e] = listeners[e] || [];
  listeners[e]!.push(cb);
  return () => off(e, cb);
}
export function off<K extends keyof BusEvents>(e: K, cb: (p: BusEvents[K]) => void) {
  listeners[e] = (listeners[e] || []).filter((fn) => fn !== cb);
}
export function emit<K extends keyof BusEvents>(e: K, p: BusEvents[K]) {
  (listeners[e] || []).forEach((fn) => fn(p));
}
