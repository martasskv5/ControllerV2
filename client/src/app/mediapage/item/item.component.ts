import { ChangeDetectionStrategy, Component, computed, input } from "@angular/core";
import { MediaItem } from '../../../models';

@Component({
  selector: 'app-mediapage-item',
  templateUrl: './item.component.html',
  styleUrls: ['./item.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MediaPageItem {
  readonly item = input.required<MediaItem>();
  readonly selectedSession = input<string | null>(null);

  protected readonly sourceName = computed(() => this.item().source ?? "Unknown source");
}
