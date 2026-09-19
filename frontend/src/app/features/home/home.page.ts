import { Component } from '@angular/core';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynIconComponent } from '@synergy-design-system/angular/components/icon';

@Component({
  imports: [SynButtonComponent, SynIconComponent],
  selector: 'app-home-page',
  templateUrl: './home.page.html',
})
export class HomePage {}
