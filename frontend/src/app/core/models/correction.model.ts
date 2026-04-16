// Interfaces TypeScript que mapean los modelos del backend

/** Bloque de texto con su texto original y corregido */
export interface TextBlock {
  page: number;
  block_index: number;
  original_text: string;
  corrected_text: string | null;
  bbox: [number, number, number, number] | null;
}

/** Estadísticas devueltas por la API */
export interface CorrectionStats {
  total_blocks: number;
  corrected_blocks: number;
  total_changes: number;
  processing_time_seconds: number;
}

/** Respuesta completa del endpoint /api/correct */
export interface CorrectionResponse {
  blocks: TextBlock[];
  stats: CorrectionStats;
  pdf_base64: string;
}

/** Estado interno del componente home */
export type ProcessingState = 'idle' | 'uploading' | 'processing' | 'done' | 'error';

/** Entrada del formulario de corrección */
export interface CorrectionRequest {
  file: File;
  context: string;
}