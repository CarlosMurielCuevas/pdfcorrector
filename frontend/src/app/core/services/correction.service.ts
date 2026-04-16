// Servicio Angular para comunicarse con el backend FastAPI
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpEventType } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { CorrectionResponse } from '../models/correction.model';

@Injectable({ providedIn: 'root' })
export class CorrectionService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  /**
   * Envía el PDF al backend para su corrección.
   * Usa multipart/form-data para incluir el archivo y el contexto.
   */
  correctPdf(file: File, context: string): Observable<CorrectionResponse> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    formData.append('context', context);

    return this.http
      .post<CorrectionResponse>(`${this.apiUrl}/correct`, formData)
      .pipe(
        catchError((error) => {
          // Extraemos el mensaje de error del backend si existe
          const message =
            error.error?.detail ??
            'Error al procesar el PDF. Inténtalo de nuevo.';
          return throwError(() => new Error(message));
        })
      );
  }

  /**
   * Descarga el PDF corregido desde la cadena base64 devuelta por la API.
   * Crea un enlace temporal y lo descarga automáticamente.
   */
  downloadCorrectedPdf(base64: string, originalName: string): void {
    const binaryStr = atob(base64);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }

    const blob = new Blob([bytes], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const correctedName = originalName.replace(/\.pdf$/i, '_corregido.pdf');

    link.href = url;
    link.download = correctedName;
    link.click();

    // Liberamos la URL temporal después de un momento
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}