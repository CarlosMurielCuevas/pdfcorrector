// Servicio para gestionar el cambio de idioma ES/EN
import { Injectable, inject } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';
import { BehaviorSubject } from 'rxjs';

export type AppLanguage = 'es' | 'en';

@Injectable({ providedIn: 'root' })
export class LanguageService {
  private readonly translate = inject(TranslateService);
  private readonly _currentLang$ = new BehaviorSubject<AppLanguage>('es');

  readonly currentLang$ = this._currentLang$.asObservable();

  constructor() {
    this.translate.addLangs(['es', 'en']);
    this.translate.setDefaultLang('es');
    this.translate.use('es');
  }

  /** Cambia el idioma de la aplicación */
  setLanguage(lang: AppLanguage): void {
    this.translate.use(lang);
    this._currentLang$.next(lang);
    document.documentElement.lang = lang;
  }

  get currentLang(): AppLanguage {
    return this._currentLang$.value;
  }
}