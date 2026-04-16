export interface DocumentUploadResponse {
  status: 'uploaded'
  document_id: string
  filename: string
  content_type: string
  size_bytes: number
  created_at: string
  text_length: number
  chunk_count: number
}
