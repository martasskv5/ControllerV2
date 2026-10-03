import { ChangeDetectionStrategy, Component, effect, inject } from "@angular/core";
import { RouterLink, RouterOutlet } from "@angular/router";
import { SettingsService } from "./settings.service";
import { WsService } from "./websocket";

@Component({
  selector: "app-root",
  imports: [RouterLink, RouterOutlet],
  templateUrl: "./app.component.html",
  styleUrl: "./app.component.scss",
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppComponent {
  protected readonly settingsService = inject(SettingsService);
  private readonly wsService = inject(WsService);

  constructor() {
    effect(() => {
      const websocketUrl = this.settingsService.websocketUrl();
      void this.wsService.connect(websocketUrl);
    });
  }

}
