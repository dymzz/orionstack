<template>
  <div v-if="result && result.data.length > 0" class="dynamic-query-card">
    <p class="dynamic-query-description">{{ result.description }}</p>
    <div class="dynamic-query-table-wrap">
      <table class="dynamic-query-table">
        <thead>
          <tr>
            <th v-for="key in columnKeys" :key="key">{{ formatHeader(key) }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, idx) in result.data" :key="idx">
            <td v-for="key in columnKeys" :key="key">{{ formatCell(key, row[key]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DynamicQueryResultItem } from '../../types/chat'

const props = defineProps<{
  result?: DynamicQueryResultItem | null
}>()

const HEADER_MAP: Record<string, string> = {
  name: '名称',
  state: '状态',
  holiday_status_id: '假期类型',
  date_from: '开始时间',
  date_to: '结束时间',
  number_of_days: '天数',
  total_amount: '金额',
  date: '日期',
  check_in: '签到时间',
  check_out: '签退时间',
  worked_hours: '工时',
  expected_revenue: '预期收入',
  stage_id: '阶段',
  probability: '概率',
}

const DECIMAL_KEYS = new Set(['total_amount', 'expected_revenue'])
const ONE_DECIMAL_KEYS = new Set(['worked_hours', 'probability'])

const columnKeys = computed(() => {
  if (!props.result?.data?.length) return []
  return Object.keys(props.result.data[0])
})

function formatHeader(key: string) {
  return HEADER_MAP[key] || key
}

function formatCell(key: string, value: unknown) {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'number') {
    if (DECIMAL_KEYS.has(key)) return value.toFixed(2)
    if (ONE_DECIMAL_KEYS.has(key)) return value.toFixed(1)
    return String(value)
  }
  return String(value)
}
</script>
