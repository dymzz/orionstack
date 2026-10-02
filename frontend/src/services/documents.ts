import { deleteJson, getJson } from './api'
import type {
  DocumentDeleteResponse,
  DocumentListResponse,
  DocumentUploadResponse,
} from '../types/document'
import { AUTH_TOKEN_STORAGE_KEY } from './api'

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const token = window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/v1/documents/upload', {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Upload failed: ${response.status}`)
  }

  return (await response.json()) as DocumentUploadResponse
}

export async function listDocuments(): Promise<DocumentListResponse> {
  return await getJson<DocumentListResponse>('/api/v1/documents')
}

export async function deleteDocument(documentId: string): Promise<DocumentDeleteResponse> {
  return await deleteJson<DocumentDeleteResponse>(`/api/v1/documents/${documentId}`)
}