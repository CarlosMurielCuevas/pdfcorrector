import { Component, inject, signal, computed, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';
import {
  trigger, state, style, transition, animate, keyframes
} from '@angular/animations';

import { CorrectionService } from '../../core/services/correction.service';
import {
  CorrectionResponse, ProcessingState, TextBlock
} from '../../core/models/correction.model';

// Pasos del proceso con sus claves de traducción
const PROCESSING_STEPS = [
  'PROCESSING.STEP_1',
  'PROCESSING.STEP_2',
  'PROCESSING.STEP_3',
  'PROCESSING.STEP_4',
  'PROCESSING.STEP_5',
];

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslateModule],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
  animations: [
    // Animación de entrada del panel de resultados
    trigger('slideUp', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateY(20px)' }),
        animate('400ms ease', style({ opacity: 1, transform: 'translateY(0)' })),
      ]),
    ]),
    // Animación del estado de drag-over
    trigger('dropZone', [
      state('idle', style({ transform: 'scale(1)' })),
      state('over', style({ transform: 'scale(1.01)' })),
      transition('idle <=> over', animate('150ms ease')),
    ]),
  ],
})
export class HomeComponent {
  private readonly correctionService = inject(CorrectionService);

  // Estado reactivo con signals
  readonly state = signal<ProcessingState>('idle');
  readonly selectedFile = signal<File | null>(null);
  readonly context = signal<string>('');
  readonly result = signal<CorrectionResponse | null>(null);
  readonly errorMessage = signal<string>('');
  readonly currentStep = signal<string>(PROCESSING_STEPS[0]);
  readonly isDragOver = signal<boolean>(false);

  // Bloques con cambios reales (computed automáticamente)
  readonly changedBlocks = computed(() => {
    const r = this.result();
    if (!r) return [];
    return r.blocks.filter(
      (b) => b.original_text !== b.corrected_text && b.corrected_text
    );
  });

  // Páginas únicas que tuvieron cambios
  readonly pagesCount = computed(() => {
    const r = this.result();
    if (!r) return 0;
    return new Set(r.blocks.map((b) => b.page)).size;
  });

  /** Maneja la selección de archivo por input */
  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files?.[0]) {
      this.validateAndSetFile(input.files[0]);
    }
  }

  /** Maneja el drop del archivo */
  onFileDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) this.validateAndSetFile(file);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver.set(true);
  }

  onDragLeave(): void {
    this.isDragOver.set(false);
  }

  /** Valida el archivo y lo establece si es válido */
  private validateAndSetFile(file: File): void {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.errorMessage.set('ERRORS.FILE_TYPE');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      this.errorMessage.set('ERRORS.FILE_SIZE');
      return;
    }
    this.selectedFile.set(file);
    this.errorMessage.set('');
    this.state.set('idle');
    this.result.set(null);
  }

  /** Inicia el proceso de corrección */
  async correctPdf(): Promise<void> {
    const file = this.selectedFile();
    if (!file) return;

    this.state.set('processing');
    this.errorMessage.set('');

    // Animamos los pasos de procesamiento
    let stepIndex = 0;
    const stepInterval = setInterval(() => {
      stepIndex = Math.min(stepIndex + 1, PROCESSING_STEPS.length - 1);
      this.currentStep.set(PROCESSING_STEPS[stepIndex]);
    }, 1200);

    this.correctionService.correctPdf(file, this.context()).subscribe({
      next: (response) => {
        clearInterval(stepInterval);
        this.result.set(response);
        this.state.set('done');
      },
      error: (error: Error) => {
        clearInterval(stepInterval);
        this.errorMessage.set(error.message || 'ERRORS.GENERIC');
        this.state.set('error');
      },
    });
  }

  /** Descarga el PDF corregido */
  downloadPdf(): void {
    const r = this.result();
    const file = this.selectedFile();
    if (r && file) {
      this.correctionService.downloadCorrectedPdf(r.pdf_base64, file.name);
    }
  }

  /** Reinicia el formulario para subir otro PDF */
  reset(): void {
    this.state.set('idle');
    this.selectedFile.set(null);
    this.context.set('');
    this.result.set(null);
    this.errorMessage.set('');
  }

  /** Devuelve tokens del original marcando solo las palabras que cambiaron */
  getOriginalTokens(original: string, corrected: string): { text: string; changed: boolean }[] {
    const origTokens = original.split(/(\s+)/);
    const corrTokens = corrected.split(/(\s+)/);
    return origTokens.map((token, i) => ({
      text: token,
      changed: !token.match(/^\s+$/) && token !== (corrTokens[i] ?? ''),
    }));
  }

  /** Devuelve tokens del corregido marcando solo las palabras que cambiaron */
  getCorrectedTokens(original: string, corrected: string): { text: string; changed: boolean }[] {
    const origTokens = original.split(/(\s+)/);
    const corrTokens = corrected.split(/(\s+)/);
    return corrTokens.map((token, i) => ({
      text: token,
      changed: !token.match(/^\s+$/) && token !== (origTokens[i] ?? ''),
    }));
  }
}