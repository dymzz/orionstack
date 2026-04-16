import type {
  DocumentDeleteResponse,
  DocumentListResponse,
  DocumentUploadResponse,
} from '../types/document'

async function readJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  return (await response.json()) as T
}

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/documents/upload', {
    method: 'POST',
    body: formData,
  })

  return await readJsonResponse<DocumentUploadResponse>(response)
}

export async function listDocuments(): Promise<DocumentListResponse> {
  const response = await fetch('/api/documents')
  return await readJsonResponse<DocumentListResponse>(response)
}

export async function deleteDocument(documentId: string): Promise<DocumentDeleteResponse> {
  const response = await fetch(`/api/documents/${documentId}`, {
    method: 'DELETE',
  })
  return await readJsonResponse<DocumentDeleteResponse>(response)
}
