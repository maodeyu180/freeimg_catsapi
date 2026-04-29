<script setup>
import { ref, computed, watch, reactive } from 'vue'
import ImageUploader from './ImageUploader.vue'

const props = defineProps({
  models: { type: Array, required: true },
  disabled: { type: Boolean, default: false },
  prefill: { type: Object, default: null },
})
const emit = defineEmits(['submit'])

const selectedKey = ref(props.models[0]?.key || '')
const prompt = ref('')
const numImages = ref(1)
const params = reactive({})
const refImages = ref([]) // [{ base64, name }]
const startFrame = ref([]) // 视频首帧图，最多 1 张；复用 ImageUploader 的数组契约

const selectedModel = computed(() => props.models.find((m) => m.key === selectedKey.value))
const isVideo = computed(() => selectedModel.value?.task_type === 'video')

// 需要在 UI 上隐藏、但仍然按默认值提交的参数（model → [param_key]）
const HIDDEN_PARAMS = {
  grokImagineVideo: ['resolution'], // 只允许 480p，不让用户改
}
function isHidden(modelKey, paramKey) {
  return (HIDDEN_PARAMS[modelKey] || []).includes(paramKey)
}

function resetParams() {
  const m = selectedModel.value
  for (const k of Object.keys(params)) delete params[k]
  if (!m) return
  for (const [k, spec] of Object.entries(m.params)) {
    params[k] = spec.default
  }
  if (numImages.value > m.max_num_images) numImages.value = m.max_num_images
  if (refImages.value.length > m.max_reference_images) {
    refImages.value = refImages.value.slice(0, m.max_reference_images)
  }
  // 切换到非视频模型时清空首帧图
  if (m.task_type !== 'video') startFrame.value = []
}

watch(selectedKey, resetParams, { immediate: true })

// 一键同款：外部传入参数就填进表单
watch(
  () => props.prefill,
  (v) => {
    if (!v) return
    if (props.models.some((m) => m.key === v.model)) {
      selectedKey.value = v.model
    }
    resetParams()
    prompt.value = v.prompt || ''
    if (v.num_images) numImages.value = Math.min(v.num_images, selectedModel.value?.max_num_images || 1)
    if (v.params) {
      for (const [k, val] of Object.entries(v.params)) {
        if (k in params && !isHidden(selectedKey.value, k)) params[k] = val
      }
    }
  },
  { immediate: false }
)

function submit() {
  if (!prompt.value.trim()) {
    alert('请输入提示词')
    return
  }
  emit('submit', {
    model: selectedKey.value,
    prompt: prompt.value.trim(),
    num_images: Number(numImages.value),
    params: { ...params },
    reference_images: refImages.value,
    start_frame: isVideo.value && startFrame.value.length ? startFrame.value[0] : null,
  })
}
</script>

<template>
  <div class="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
    <!-- 模型选择 -->
    <div>
      <label class="block text-sm font-medium text-slate-700 mb-2">模型</label>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
        <button
          v-for="m in models"
          :key="m.key"
          type="button"
          @click="selectedKey = m.key"
          :class="[
            'px-3 py-2 rounded-lg border text-sm text-left transition',
            selectedKey === m.key
              ? 'bg-brand-50 border-brand-500 text-brand-700 ring-1 ring-brand-500'
              : 'bg-white border-slate-200 text-slate-600 hover:border-brand-300',
          ]"
        >
          <div class="font-medium">{{ m.display_name }}</div>
          <div class="text-xs text-slate-400 mt-0.5">
            {{ m.task_type === 'image' ? '🖼️ 图片' : '🎬 视频' }}
          </div>
        </button>
      </div>
    </div>

    <!-- Prompt -->
    <div>
      <label class="block text-sm font-medium text-slate-700 mb-2">提示词</label>
      <textarea
        v-model="prompt"
        rows="4"
        placeholder="描述你想要的画面……"
        class="w-full px-3 py-2 rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none text-sm resize-none"
      />
    </div>

    <!-- 参考图 -->
    <div v-if="selectedModel && selectedModel.max_reference_images > 0">
      <label class="block text-sm font-medium text-slate-700 mb-2">参考图（可选）</label>
      <ImageUploader v-model="refImages" :max="selectedModel.max_reference_images" />
    </div>

    <!-- 视频首帧图（可选，仅视频模型显示，最多 1 张） -->
    <div v-if="isVideo">
      <label class="block text-sm font-medium text-slate-700 mb-2">首帧图（可选）</label>
      <ImageUploader
        v-model="startFrame"
        :max="1"
        add-label="+ 首帧图"
        hint="上传后将基于该图生成视频；不传则为纯文生视频。单张 ≤ 5MB"
      />
    </div>

    <!-- 参数 -->
    <div v-if="selectedModel" class="grid grid-cols-2 md:grid-cols-3 gap-3">
      <!-- 生成数量 -->
      <div v-if="selectedModel.task_type === 'image'">
        <label class="block text-xs font-medium text-slate-600 mb-1">生成数量</label>
        <select
          v-model.number="numImages"
          class="w-full px-2 py-1.5 rounded-lg border border-slate-300 text-sm"
        >
          <option v-for="n in selectedModel.max_num_images" :key="n" :value="n">{{ n }}</option>
        </select>
      </div>
      <!-- 其他参数（隐藏参数不渲染，但 resetParams 里已填好默认值仍会提交） -->
      <template v-for="(spec, key) in selectedModel.params" :key="key">
        <template v-if="!isHidden(selectedKey, key)">
          <div v-if="spec.type === 'dropdown'">
            <label class="block text-xs font-medium text-slate-600 mb-1">{{ spec.label || key }}</label>
            <select
              v-model="params[key]"
              class="w-full px-2 py-1.5 rounded-lg border border-slate-300 text-sm"
            >
              <option v-for="opt in spec.options" :key="opt" :value="opt">{{ opt }}</option>
            </select>
          </div>
          <div v-else-if="spec.type === 'switch'" class="flex items-center gap-2 pt-5">
            <input
              :id="`switch-${key}`"
              type="checkbox"
              v-model="params[key]"
              class="w-4 h-4 accent-brand-600"
            />
            <label :for="`switch-${key}`" class="text-xs text-slate-600">{{ spec.label || key }}</label>
          </div>
        </template>
      </template>
    </div>

    <button
      type="button"
      @click="submit"
      :disabled="disabled"
      class="w-full bg-brand-600 hover:bg-brand-700 disabled:bg-slate-300 text-white font-medium py-2.5 rounded-lg transition"
    >
      {{ disabled ? '你有任务正在进行中...' : '开始生成' }}
    </button>
  </div>
</template>
