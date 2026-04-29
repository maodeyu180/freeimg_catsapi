<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] }, // [{ base64, name }]
  max: { type: Number, default: 2 },
  addLabel: { type: String, default: '+ 参考图' },
  hint: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const fileInput = ref(null)

const images = computed(() => props.modelValue)

function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => {
      const s = r.result
      const idx = s.indexOf(',')
      resolve(idx >= 0 ? s.slice(idx + 1) : s)
    }
    r.onerror = reject
    r.readAsDataURL(file)
  })
}

async function onFiles(e) {
  const files = Array.from(e.target.files || [])
  const room = props.max - images.value.length
  const picked = files.slice(0, room)
  const added = []
  for (const f of picked) {
    if (f.size > 5 * 1024 * 1024) {
      alert(`${f.name} 超过 5MB，已跳过`)
      continue
    }
    const base64 = await readAsBase64(f)
    added.push({ base64, name: f.name })
  }
  emit('update:modelValue', [...images.value, ...added])
  if (fileInput.value) fileInput.value.value = ''
}

function remove(i) {
  const next = images.value.slice()
  next.splice(i, 1)
  emit('update:modelValue', next)
}
</script>

<template>
  <div>
    <div class="flex flex-wrap gap-2">
      <div
        v-for="(img, i) in images"
        :key="i"
        class="relative w-20 h-20 rounded-lg overflow-hidden border border-slate-200 bg-slate-100"
      >
        <img :src="`data:image/*;base64,${img.base64}`" class="w-full h-full object-cover" />
        <button
          type="button"
          @click="remove(i)"
          class="absolute top-0 right-0 w-5 h-5 bg-black/60 text-white text-xs rounded-bl"
        >
          ×
        </button>
      </div>
      <label
        v-if="images.length < max"
        class="w-20 h-20 rounded-lg border-2 border-dashed border-slate-300 flex items-center justify-center text-xs text-slate-400 hover:border-brand-500 hover:text-brand-500 cursor-pointer"
      >
        <input
          ref="fileInput"
          type="file"
          accept="image/*"
          multiple
          class="hidden"
          @change="onFiles"
        />
        {{ addLabel }}
      </label>
    </div>
    <p class="text-xs text-slate-400 mt-1">{{ hint || `最多 ${max} 张，单张 ≤ 5MB` }}</p>
  </div>
</template>
