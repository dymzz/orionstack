export interface DocumentListItem {
  document_id: string
  filename: string
  content_type: string
  size_bytes: number
  created_at: string
  text_length: number
  chunk_count: number
}

export interface DocumentListResponse {
  items: DocumentListItem[]
}

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

export interface DocumentDeleteResponse {
  status: 'deleted'
  document_id: string
}
