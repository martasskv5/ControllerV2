import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Mediapage } from './mediapage';

describe('Mediapage', () => {
  let component: Mediapage;
  let fixture: ComponentFixture<Mediapage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Mediapage]
    })
    .compileComponents();

    fixture = TestBed.createComponent(Mediapage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
