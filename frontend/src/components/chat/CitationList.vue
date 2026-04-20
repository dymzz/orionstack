<template>
  <section class="card">
    <h2>引用</h2>
    <ul class="citation-list">
      <li v-for="citation in citations" :key="citation.citation_id">
        <div class="citation-head">
          <div class="citation-title-group">
            <strong>{{ citation.source_label }}</strong>
            <span class="citation-kind" :class="getCitationKindClass(citation)">{{ getCitationKindText(citation) }}</span>
          </div>
          <span class="citation-id">{{ citation.citation_id }}</span>
        </div>
        <p class="locator-label">{{ getLocatorLabel(citation) }}</p>
        <p class="locator">{{ citation.source_locator }}</p>
        <p class="citation-snippet-label">{{ getSnippetLabel(citation) }}</p>
        <p class="citation-snippet">{{ citation.snippet }}</p>
      </li>
    </ul>
  </section>
</template>

<script setup lang="ts">
import type { CitationItem } from '../../types/chat'

defineProps<{ citations: CitationItem[] }>()

function isFaqCitation(citation: CitationItem) {
  return citation.citation_id.startsWith('faq-')
}

function getCitationKindText(citation: CitationItem) {
  return isFaqCitation(citation) ? 'FAQ 来源' : '文档来源'
}

function getCitationKindClass(citation: CitationItem) {
  return isFaqCitation(citation) ? 'citation-kind-faq' : 'citation-kind-document'
}

function getLocatorLabel(citation: CitationItem) {
  return isFaqCitation(citation) ? 'FAQ 定位' : '文档定位'
}

function getSnippetLabel(citation: CitationItem) {
  return isFaqCitation(citation) ? '引用 / 证据片段' : '引用片段'
}
</script>
