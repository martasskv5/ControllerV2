import { Injectable, model } from "@angular/core";
import { Subject, Observable, ReplaySubject } from "rxjs";
import { WSLike, ServerMessage } from "../models";

@Injectable({ providedIn: "root" })
export class WsService {
    // Use ReplaySubject(1) so the latest server message (e.g. mediaList)
    // is replayed to new subscribers when they navigate back to the page.
    private msg = new ReplaySubject<ServerMessage>(1);
    public messages$ = this.msg.asObservable();

    private ws: WSLike | null = null;

    async connect(url: string) {
        this.close();

        // Try Tauri websocket plugin first
        try {
            if (typeof window !== "undefined" && (window as any).__TAURI__) {
                const plugin = await import("@tauri-apps/plugin-websocket");
                const anyWs: any = plugin;
                const fn = anyWs.create || anyWs.connect || anyWs.open;
                if (fn) {
                    const conn = await fn(url);
                    const wrapped: WSLike = {
                        send: (d: string) => conn.send(d),
                        close: () => conn.close(),
                        onopen: null,
                        onclose: null,
                        onerror: null,
                        onmessage: null,
                        readyState: 1,
                    };
                    conn.onmessage((m: any) => {
                        try {
                            const parsed = typeof m === "string" ? JSON.parse(m) : m;
                            this.msg.next(parsed);
                        } catch {}
                        wrapped.onmessage && wrapped.onmessage({ data: m });
                    });
                    conn.onopen(() => wrapped.onopen && wrapped.onopen());
                    conn.onerror((e: any) => wrapped.onerror && wrapped.onerror(e));
                    conn.onclose(() => wrapped.onclose && wrapped.onclose());
                    this.bind(wrapped);
                    this.ws = wrapped;
                    return;
                }
            }
        } catch (e) {
            // fallthrough to browser WebSocket
        }

        return new Promise<void>((resolve, reject) => {
            try {
                const w = new WebSocket(url);
                w.onopen = () => resolve();
                w.onmessage = (ev) => {
                    try {
                        this.msg.next(JSON.parse(ev.data));
                    } catch {}
                };
                w.onclose = () => {
                    /* noop */
                };
                w.onerror = (e) => reject(e);
                this.ws = w as any;
            } catch (err) {
                reject(err);
            }
        });
    }

    private bind(w: WSLike) {
        w.onmessage = (ev) => {
            try {
                this.msg.next(typeof ev.data === "string" ? JSON.parse(ev.data) : ev.data);
            } catch {}
        };
    }

    send(obj: any) {
        try {
            if (!this.ws || this.ws.readyState !== 1) {
                // not connected
                console.debug('ws: not connected, drop send');
                return;
            }
            const payload = typeof obj === 'string' ? obj : JSON.stringify(obj);
            this.ws.send(payload);
            console.debug('ws: sent', payload);
        } catch (e) {
            console.error('ws: send failed', e);
        }
    }

    close() {
        try {
            this.ws?.close();
        } catch {}
        this.ws = null;
    }
}
