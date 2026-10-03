import {
    Component,
    ElementRef,
    ViewChild,
    computed,
    inject,
    OnDestroy,
    OnInit,
    signal,
    WritableSignal,
} from "@angular/core";
import { WsService } from "../websocket";
import { MediaItem, ServerMessage, MessageType } from "../../models";
import { MediaPageItem } from "./item/item.component";

@Component({
    selector: "app-mediapage",
    imports: [MediaPageItem],
    templateUrl: "./mediapage.html",
    styleUrl: "./mediapage.scss",
})
export class Mediapage implements OnInit, OnDestroy {
    protected readonly mediaList: WritableSignal<MediaItem[]> = signal([]);
    protected readonly selectedSessionId = signal<string | null>(null);
    protected readonly visualizerBars = signal<number[]>(Array.from({ length: 16 }, () => 0.2));
    protected readonly visualizerPeak = computed(() => this.nowPlaying()?.audio_level ?? this.selectedSession()?.audio_level ?? 0);
    protected readonly nowPlaying = computed(() => {
        const list = this.mediaList();
        return list.find((item) => item.is_playing) ?? list[0] ?? null;
    });
    protected readonly selectedSession = computed(() => {
        const selectedId = this.selectedSessionId();
        const list = this.mediaList();
        return list.find((item) => item.id === selectedId) ?? this.nowPlaying();
    });
    protected readonly orderedMediaList = computed(() => {
        const list = [...this.mediaList()];
        return list.sort((a, b) => Number(Boolean(b.is_playing)) - Number(Boolean(a.is_playing)));
    });

    @ViewChild("sourceList")
    private sourceListRef?: ElementRef<HTMLElement>;

    private ws = inject(WsService);
    private scrollRaf: number | null = null;
    private meterTimer: number | null = null;
    private visualizerRaf: number | null = null;
    private visualizerPhase = 0;

    ngOnInit() {
        // subscribe to server messages
        this.ws.messages$.subscribe((msg: ServerMessage) => {
            if (msg.type === MessageType.MediaController && msg.ok) {
                const sessions = msg["sessions"] || [];
                this.mediaList.set(sessions);
                this.syncSelectedSession(sessions);
                this.updateVisualizerFromMeter();

                // first message - set entire list
                // if (this.mediaList().length === 0) {
                //     this.mediaList.set(msg["sessions"] || []);
                // }
                console.log(this.mediaList());

                // for (const s of msg["sessions"] || []) {
                //     // update only changed items
                //     const idx = this.mediaList().findIndex((mi) => mi.id === s.id);
                //     if (idx >= 0) {
                //         const current = this.mediaList()[idx];
                //         if (JSON.stringify(current) !== JSON.stringify(s)) {
                //             const updated = [...this.mediaList()];
                //             updated[idx] = s;
                //             this.mediaList.set(updated);
                //         }
                //     } else {
                //         this.mediaList.set([...this.mediaList(), s]);
                //     }
                // }
            }
        });

        this.ws.send({
            action: "mc_list",
        });

        this.meterTimer = window.setInterval(() => {
            this.ws.send({ action: "mc_list" });
        }, 250);

        this.visualizerRaf = window.requestAnimationFrame(() => this.animateVisualizer());
    }

    ngOnDestroy() {
        if (this.meterTimer !== null) {
            window.clearInterval(this.meterTimer);
            this.meterTimer = null;
        }

        if (this.visualizerRaf !== null) {
            window.cancelAnimationFrame(this.visualizerRaf);
            this.visualizerRaf = null;
        }
    }

    protected selectSession(sessionId: string) {
        this.selectedSessionId.set(sessionId);
    }

    protected handleListScroll() {
        if (this.scrollRaf !== null) {
            return;
        }

        this.scrollRaf = requestAnimationFrame(() => {
            this.scrollRaf = null;
            this.selectNearestCardToAnchor();
        });
    }

    private selectNearestCardToAnchor() {
        const container = this.sourceListRef?.nativeElement;
        if (!container) {
            return;
        }

        const cardNodes = Array.from(container.querySelectorAll<HTMLElement>("[data-session-id]"));
        if (cardNodes.length === 0) {
            return;
        }

        const containerBounds = container.getBoundingClientRect();
        const anchorY = containerBounds.top + Math.min(84, containerBounds.height / 3);
        let nearest: { id: string; distance: number } | null = null;

        for (const node of cardNodes) {
            const id = node.dataset["sessionId"];
            if (!id) {
                continue;
            }
            const rect = node.getBoundingClientRect();
            if (rect.bottom < containerBounds.top || rect.top > containerBounds.bottom) {
                continue;
            }

            const distance = Math.abs(rect.top - anchorY);
            if (!nearest || distance < nearest.distance) {
                nearest = { id, distance };
            }
        }

        if (nearest && nearest.id !== this.selectedSessionId()) {
            this.selectedSessionId.set(nearest.id);
        }
    }

    private syncSelectedSession(sessions: MediaItem[]) {
        if (sessions.length === 0) {
            this.selectedSessionId.set(null);
            return;
        }

        const selectedId = this.selectedSessionId();
        if (selectedId && sessions.some((session) => session.id === selectedId)) {
            return;
        }

        const fallback = sessions.find((session) => session.is_playing) ?? sessions[0];
        this.selectedSessionId.set(fallback.id);
    }

    private updateVisualizerFromMeter() {
        const peak = Math.max(0, Math.min(1, this.visualizerPeak() || 0));
        const base = this.selectedSession()?.is_playing ? peak : peak * 0.35;
        const nextBars = Array.from({ length: 16 }, (_, index) => {
            const wobble = 0.28 + 0.72 * Math.abs(Math.sin(this.visualizerPhase + index * 0.55));
            const accent = index % 2 === 0 ? 1 : 0.82;
            const height = 0.12 + base * wobble * accent;
            return Math.max(0.1, Math.min(1, height));
        });
        this.visualizerBars.set(nextBars);
    }

    private animateVisualizer() {
        this.visualizerPhase += 0.08;
        this.updateVisualizerFromMeter();
        this.visualizerRaf = window.requestAnimationFrame(() => this.animateVisualizer());
    }

    handleSetVolume(volume: number) {
        const selected = this.selectedSession();
        if (!selected) {
            return;
        }

        console.log("setting volume");

        this.ws.send({
            "action": "mc_set_volume",
            "id": selected.id,
            "level": volume,
        });
    }

    handleAction(event: { action: string; id?: string }) {
        const selected = this.selectedSession();
        if (!selected) {
            return;
        }

        console.log("handling action", event);
        this.ws.send({
            "action": event.action,
            "id": selected.id,
        });
    }
}
