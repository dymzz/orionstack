import { deleteJson, getJson, postForm } from './api'
import type {
  DocumentDeleteResponse,
  DocumentListResponse,
  DocumentUploadResponse,
} from '../types/document'

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  return postForm<DocumentUploadResponse>('/api/v1/documents/upload', formData)
}

export async function listDocuments(): Promise<DocumentListResponse> {
  return await getJson<DocumentListResponse>('/api/v1/documents')
}

export async function deleteDocument(documentId: string): Promise<DocumentDeleteResponse> {
  return await deleteJson<DocumentDeleteResponse>(`/api/v1/documents/${documentId}`)
}
