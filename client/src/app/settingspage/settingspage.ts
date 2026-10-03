import { ChangeDetectionStrategy, Component, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { SettingsService, ThemeMode } from "../settings.service";

const THEME_OPTIONS: Array<{ value: ThemeMode; label: string; description: string }> = [
    { value: "system", label: "System", description: "Follow the device theme" },
    { value: "light", label: "Light", description: "Bright surfaces and high contrast" },
    { value: "dark", label: "Dark", description: "Dimmer surfaces for low-light use" },
];

@Component({
    selector: "app-settingspage",
    imports: [ReactiveFormsModule],
    templateUrl: "./settingspage.html",
    styleUrl: "./settingspage.scss",
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsPage {
    protected readonly themeOptions = THEME_OPTIONS;
    protected readonly settingsService = inject(SettingsService);
    private readonly fb = inject(FormBuilder);

    protected readonly form = this.fb.nonNullable.group({
        theme: this.fb.nonNullable.control(this.settingsService.theme(), Validators.required),
        websocketUrl: this.fb.nonNullable.control(this.settingsService.websocketUrl(), [Validators.required, Validators.pattern(/^wss?:\/\/.+/i)]),
    });

    protected save() {
        if (this.form.invalid) {
            this.form.markAllAsTouched();
            return;
        }

        const { theme, websocketUrl } = this.form.getRawValue();
        this.settingsService.setTheme(theme);
        this.settingsService.setWebsocketUrl(websocketUrl);
    }

    protected reset() {
        this.settingsService.reset();
        const snapshot = this.settingsService.snapshot();
        this.form.reset(snapshot);
    }
}