export interface WSLike {
  send: (data: string) => void;
  close: () => void;
  onopen?: ((ev?: any) => void) | null;
  onclose?: ((ev?: any) => void) | null;
  onerror?: ((ev?: any) => void) | null;
  onmessage?: ((ev: { data: string }) => void) | null;
  readyState?: number;
};

export interface ServerMessage {
    ok: boolean;
    type: MessageType | string;
    error?: string;
    [k: string]: any;
}

export interface MediaItem {
    id: string;
    title?: string | null;
    artist?: string | null;
    album?: string | null;
    is_playing?: boolean;
    status?: string | null;
    source?: string | null;
    volume?: number | null; // 0..1
    audio_level?: number | null; // 0..1 peak meter
}


export enum MessageType {
    MediaController = "mediacontroller",
    Keyboard = "keyboard",
}