import { Injectable, computed, effect, signal } from "@angular/core";

export type ThemeMode = "system" | "light" | "dark";

export interface AppSettings {
    theme: ThemeMode;
    websocketUrl: string;
}

const STORAGE_KEY = "controllerv2.settings";

const DEFAULT_SETTINGS: AppSettings = {
    theme: "system",
    websocketUrl: "ws://localhost:21234",
};

@Injectable({ providedIn: "root" })
export class SettingsService {
    private readonly settingsSignal = signal<AppSettings>(this.readSettings());

    readonly settings = this.settingsSignal.asReadonly();
    readonly theme = computed(() => this.settingsSignal().theme);
    readonly themeLabel = computed(() => {
        const theme = this.settingsSignal().theme;
        if (theme === "dark") {
            return "Dark mode";
        }
        if (theme === "light") {
            return "Light mode";
        }
        return "System theme";
    });
    readonly websocketUrl = computed(() => this.settingsSignal().websocketUrl);

    constructor() {
        effect(() => {
            const settings = this.settingsSignal();
            this.persistSettings(settings);
            this.applyTheme(settings.theme);
        });
    }

    setTheme(theme: ThemeMode) {
        this.settingsSignal.update((settings) => ({ ...settings, theme }));
    }

    setWebsocketUrl(websocketUrl: string) {
        const normalizedUrl = websocketUrl.trim();
        if (!normalizedUrl) {
            return;
        }

        this.settingsSignal.update((settings) => ({ ...settings, websocketUrl: normalizedUrl }));
    }

    reset() {
        this.settingsSignal.set({ ...DEFAULT_SETTINGS });
    }

    snapshot(): AppSettings {
        return { ...this.settingsSignal() };
    }

    private readSettings(): AppSettings {
        if (typeof window === "undefined") {
            return { ...DEFAULT_SETTINGS };
        }

        try {
            const raw = window.localStorage.getItem(STORAGE_KEY);
            if (!raw) {
                return { ...DEFAULT_SETTINGS };
            }

            const parsed = JSON.parse(raw) as Partial<AppSettings>;
            const theme = parsed.theme === "light" || parsed.theme === "dark" || parsed.theme === "system" ? parsed.theme : DEFAULT_SETTINGS.theme;
            const websocketUrl = typeof parsed.websocketUrl === "string" && parsed.websocketUrl.trim() ? parsed.websocketUrl.trim() : DEFAULT_SETTINGS.websocketUrl;

            return {
                theme,
                websocketUrl,
            };
        } catch {
            return { ...DEFAULT_SETTINGS };
        }
    }

    private persistSettings(settings: AppSettings) {
        if (typeof window === "undefined") {
            return;
        }

        try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
        } catch {
            // ignore storage failures in restricted environments
        }
    }

    private applyTheme(theme: ThemeMode) {
        if (typeof document === "undefined") {
            return;
        }

        const root = document.documentElement;
        root.dataset["theme"] = theme;
    }
}