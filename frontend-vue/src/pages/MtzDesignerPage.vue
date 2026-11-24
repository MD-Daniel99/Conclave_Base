<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getApiErrorMessage } from '@/shared/api/http'
import {
  fetchMtzConfig, saveMtzConfig, fetchMtzTemplates, fetchMtzTemplateEditor,
  saveMtzTemplateEditor, restoreMtzTemplateEditor, downloadMtzTemplate,
  type MtzFormConfig, type MtzTemplateEditor, type MtzTemplateOption,
  type MtzCustomField,
} from '@/shared/api/documents'

const router=useRouter()
const tab=ref<'fields'|'tables'>('fields')
const config=ref<MtzFormConfig | null>(null)
const templates=ref<MtzTemplateOption[]>([])
const templateKey=ref('')
const editor=ref<MtzTemplateEditor | null>(null)
const busy=ref(false)
const error=ref('')
const info=ref('')
const sourceOptions = [
  ['full_name','ФИО пациента'],['birth_date','Дата рождения'],['passport_series','Серия паспорта'],
  ['passport_number','Номер паспорта'],['passport_issuer','Кем выдан паспорт'],
  ['passport_issue_date','Дата выдачи'],['passport_department','Код подразделения'],
  ['mse_reference','Справка МСЭ'],
] as const
const fields= computed(() => Object.entries(config.value?.manual ?? {}))
const autoFields= computed(() => Object.entries(config.value?.auto ?? {}))
const optionKeys=['disability_group_reason','diagnoses','stump_condition','activity_level']
const descriptions: Record<string,string>={
  disability_group_reason:'Причина инвалидности',diagnoses:'Диагнозы (несколько значений)',
  stump_condition:'Состояние культи',activity_level:'Уровень активности',
  weight_kg:'Вес, кг',amputation_level:'Уровень ампутации (для каждого ТСР)',
  amputation_code:'Код уровня ампутации (для каждого ТСР)',
}
const restoreRevision=ref(0)
// Preserve line breaks while typing; only parse option lists when publishing.
const optionDrafts=ref<Record<string,string>>({})
const activityDraftOptions=computed(()=>String(optionDrafts.value.activity_level??'').split(/\r?\n/).map(v=>v.trim()).filter(Boolean))
function initOptionDrafts(next: MtzFormConfig){
  optionDrafts.value={}
  for(const [key,field] of Object.entries(next.manual)){
    if(field.options)optionDrafts.value[key]=field.options.join('\n')
  }
  for(const field of next.custom_fields){
    if(field.kind==='select')optionDrafts.value[`custom:${field.key}`]=(field.options??[]).join('\n')
  }
}
const newField=ref<MtzCustomField>({key:'custom_',label:'',kind:'text',scope:'shared',required:false,placeholder:''})

function parseOptions(value:string){return value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean)}
function addCustomField() {
  if (!config.value) return
  if (!/^custom_[a-z][a-z0-9_]{1,35}$/.test(newField.value.key) || !newField.value.label.trim()) {
    error.value='Ключ должен быть в виде custom_name (латиница), а название — заполнено.'; return
  }
  if (config.value.custom_fields.some(f=>f.key===newField.value.key)) {
    error.value='Такое поле уже существует';return
  }
  config.value.custom_fields.push({...newField.value,
    ...(newField.value.kind==='select'?{options:[...(newField.value.options?.length ? newField.value.options : ['Вариант 1'])]}:{}),
    ...(newField.value.kind==='auto'?{source:newField.value.source||'full_name'}:{})})
  if (newField.value.kind==='select') optionDrafts.value[`custom:${newField.value.key}`]='Вариант 1'
  newField.value={key:'custom_',label:'',kind:'text',scope:'shared',required:false,placeholder:''}
  error.value=''
}
async function saveFields() {
  if (!config.value) return
  busy.value=true;error.value='';info.value=''
  try {
    for(const key of optionKeys){
      if(config.value.manual[key])config.value.manual[key].options=parseOptions(optionDrafts.value[key]??'')
    }
    for(const field of config.value.custom_fields){
      if(field.kind==='select')field.options=parseOptions(optionDrafts.value[`custom:${field.key}`]??'')
    }
    config.value=await saveMtzConfig(config.value)
    initOptionDrafts(config.value)
    info.value='Настройки сохранены. Новые правила применятся при следующем формировании МТЗ.'
  } catch(e){error.value=getApiErrorMessage(e)}
  finally{busy.value=false}
}
async function loadEditor(key:string) {
  if (!key) return
  busy.value=true;error.value='';info.value='';editor.value=null
  try {
    editor.value=await fetchMtzTemplateEditor(key)
    restoreRevision.value=editor.value.revision
  } catch(e){error.value=getApiErrorMessage(e)}
  finally{busy.value=false}
}
watch(templateKey, key=>{void loadEditor(key)})
function addRowAfter(index:number) {
  if (!editor.value || editor.value.rows.length>=150) return
  const from=editor.value.rows[index]
  const cloneFrom=from.source_index ?? from.clone_from
  if (typeof cloneFrom!=='number') return
  editor.value.rows.splice(index+1,0,{
    source_index:null,clone_from:cloneFrom,
    cells:from.cells.map(cell=>({...cell,text:''})),
  })
}
function removeRow(index:number){
  if (editor.value && editor.value.rows.length>2) editor.value.rows.splice(index,1)
}
async function saveTable() {
  if (!editor.value) return
  busy.value=true;error.value='';info.value=''
  try {
    const updated=await saveMtzTemplateEditor(templateKey.value,editor.value)
    editor.value=updated
    restoreRevision.value=updated.revision
    templates.value=await fetchMtzTemplates()
    info.value=`Сохранена редакция ${updated.revision}. Исходный утверждённый DOCX не изменён.`
  } catch(e){error.value=getApiErrorMessage(e)}
  finally{busy.value=false}
}
async function restore() {
  if (!editor.value) return
  if (!window.confirm(`Восстановить содержимое редакции ${restoreRevision.value}? Будет создана новая версия.`))return
  busy.value=true;error.value='';info.value=''
  try {
    editor.value=await restoreMtzTemplateEditor(templateKey.value,Number(restoreRevision.value),editor.value.revision)
    templates.value=await fetchMtzTemplates()
    info.value=`Предыдущая версия восстановлена как редакция ${editor.value.revision}.`
  }catch(e){error.value=getApiErrorMessage(e)}
  finally{busy.value=false}
}
async function getDocx() {
  if (!editor.value)return
  try{
    const blob=await downloadMtzTemplate(templateKey.value)
    const url=URL.createObjectURL(blob);const a=document.createElement('a')
    a.href=url;a.download=`mtz_${templateKey.value}_rev${editor.value.revision}.docx`
    a.click();setTimeout(()=>URL.revokeObjectURL(url),10000)
  }catch(e){error.value=getApiErrorMessage(e)}
}
onMounted(async()=>{
  busy.value=true
  try{
    const [settings,templateList]=await Promise.all([fetchMtzConfig(),fetchMtzTemplates()])
    config.value=settings;initOptionDrafts(settings);templates.value=templateList
    templateKey.value=templateList[0]?.value??''
  }catch(e){error.value=getApiErrorMessage(e)}
  finally{busy.value=false}
})
</script>

<template>
  <section class="mtz-designer-page">
    <div class="mtz-designer-head">
      <div><p class="eyebrow">Документы / МТЗ</p><h1>Конструктор МТЗ</h1><p>Настраивайте поля автозаполнения и таблицы заключений без изменения кода приложения.</p></div>
      <button type="button" class="secondary-button" @click="router.push({name:'documents-mtz-templates'})">Назад к библиотеке</button>
    </div>
    <div v-if="error" class="mtz-designer-error" role="alert">{{ error }}</div>
    <div v-if="info" class="mtz-designer-ok" role="status">{{ info }}</div>
    <nav class="mtz-designer-nav" aria-label="Разделы конструктора">
      <button type="button" :class="{selected:tab==='fields'}" @click="tab='fields'">Поля и автозаполнение</button>
      <button type="button" :class="{selected:tab==='tables'}" @click="tab='tables'">Заключения и таблицы</button>
    </nav>
    <template v-if="config && tab==='fields'">
      <div class="mtz-designer-note">Эти настройки действуют для всех следующих МТЗ. Уже сформированные файлы не меняются. Для новых полей используйте метку вида <code v-pre>{{custom_example}}</code> в нужной ячейке DOCX.</div>
      <form class="mtz-designer-content" @submit.prevent="saveFields">
        <section class="mtz-designer-panel"><h2>Автоматические данные пациента</h2><p>Для каждой метки в шапке можно изменить подпись и выбрать источник данных из карточки пациента.</p>
          <div class="mtz-auto-fields">
            <div v-for="([key, field]) in autoFields" :key="key" class="mtz-auto-row">
              <span class="mtz-field-key">{{ key }}</span>
              <label>Название поля<input v-model="field.label" maxlength="180" /></label>
              <label>Откуда брать данные<select v-model="field.source"><option v-for="[value,name] in sourceOptions" :key="value" :value="value">{{ name }}</option></select></label>
              <label>Если не заполнено<input v-model="field.default" maxlength="250" placeholder="Необязательно" /></label>
            </div>
          </div>
        </section>
        <section class="mtz-designer-panel"><h2>Поля для ручного ввода</h2><p>Подписи, подсказки и варианты выбора редактируются здесь. Каждый вариант списка указывайте с новой строки.</p>
          <div class="mtz-manual-grid">
            <article v-for="([key,field]) in fields" :key="key" class="mtz-field-editor">
              <div class="mtz-field-editor-head"><strong>{{ descriptions[key] || key }}</strong><code>{{ key }}</code></div>
              <label>Подпись<input v-model="field.label" maxlength="180" /></label>
              <label v-if="optionKeys.includes(key)">Варианты выбора<textarea rows="5" v-model="optionDrafts[key]" /></label>
              <label v-else>Подсказка<input v-model="field.placeholder" maxlength="180" /></label>
              <div v-if="key==='activity_level'" class="mtz-activity-codes">
                <label v-for="value in activityDraftOptions" :key="value">Код для «{{ value }}»
                  <input v-model="config.codes.activity_level[value]" placeholder="Например, 1.3.3" />
                </label>
              </div>
            </article>
          </div>
        </section>
        <section class="mtz-designer-panel"><h2>Дополнительные поля</h2><p>Можно создавать новые ручные поля и автополя. Укажите метку <code v-pre>{{custom_name}}</code> в редакторе таблицы — и она будет заполнена при формировании МТЗ.</p>
          <div v-for="(field,index) in config.custom_fields" :key="field.key" class="mtz-custom-field">
            <div><strong>{{ field.label }}</strong><code v-pre>{{</code><code>{{field.key}}</code><code v-pre>}}</code></div>
            <label>Подпись<input v-model="field.label" /></label>
            <label>Область<select v-model="field.scope"><option value="shared">Общее для всего МТЗ</option><option value="per_item">Отдельно для каждого ТСР</option></select></label>
            <label v-if="field.kind==='auto'">Источник<select v-model="field.source"><option v-for="[value,name] in sourceOptions" :key="value" :value="value">{{ name }}</option></select></label>
            <label v-if="field.kind==='select'">Варианты (каждый с новой строки)<textarea v-model="optionDrafts[`custom:${field.key}`]" rows="3" /></label>
            <label v-if="field.kind==='text'">Подсказка<input v-model="field.placeholder" /></label>
            <label v-if="field.kind!=='auto'" class="mtz-checkbox"><input v-model="field.required" type="checkbox" /> Обязательно для заполнения</label>
            <button type="button" class="secondary-button" @click="config.custom_fields.splice(index,1)">Удалить поле</button>
          </div>
          <div class="mtz-new-field">
            <label>Ключ (латиницей)<input v-model="newField.key" placeholder="custom_material" /></label>
            <label>Подпись<input v-model="newField.label" placeholder="Наименование поля" /></label>
            <label>Вид<select v-model="newField.kind"><option value="text">Текст вручную</option><option value="select">Выбор варианта</option><option value="auto">Из карточки пациента</option></select></label>
            <label>Где заполняется<select v-model="newField.scope"><option value="shared">Один раз на МТЗ</option><option value="per_item">Для каждого ТСР</option></select></label>
            <button type="button" class="secondary-button" @click="addCustomField">+ Добавить поле</button>
          </div>
        </section>
        <div class="mtz-editor-save"><button type="submit" class="primary-button" :disabled="busy">{{ busy?'Сохраняем…':'Сохранить настройки полей' }}</button></div>
      </form>
    </template>
    <template v-else-if="tab==='tables'">
      <div class="mtz-designer-panel mtz-editor-selector">
        <label>Заключение для редактирования<select v-model="templateKey"><option v-for="item in templates" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
        <p>Правки не изменяют исходный DOCX. При сохранении создаётся новая версия заключения, старую можно восстановить.</p>
      </div>
      <div v-if="editor" class="mtz-designer-content">
        <section class="mtz-designer-panel">
          <div class="mtz-editor-toolbar"><strong>Редакция {{ editor.revision }}</strong><button type="button" class="secondary-button" @click="getDocx">Скачать текущий DOCX</button></div>
          <label class="mtz-editor-title">Наименование заключения и полный код ТСР<input v-model="editor.title" maxlength="310" /></label>
          <p>Ниже можно редактировать любой текст таблицы. Для большой таблицы раскрывайте только нужную строку. Порядок и объединение исходных ячеек сохраняются.</p>
          <div class="mtz-rows">
            <details v-for="(row,idx) in editor.rows" :key="idx" class="mtz-row-editor">
              <summary>Строка {{idx+1}} · {{ row.cells.map(c=>c.text).filter(Boolean).join(' · ').slice(0,110) || 'Новая строка' }}</summary>
              <div class="mtz-row-body">
                <label v-for="cell in row.cells" :key="cell.col">Ячейка {{cell.col+1}}
                  <textarea v-model="cell.text" rows="2" maxlength="1300" />
                </label>
                <div class="mtz-row-actions"><button type="button" class="secondary-button" @click="addRowAfter(idx)">Дублировать строку ниже</button><button type="button" class="secondary-button" :disabled="editor.rows.length<=2" @click="removeRow(idx)">Удалить строку</button></div>
              </div>
            </details>
          </div>
          <div class="mtz-editor-save"><button class="primary-button" type="button" :disabled="busy" @click="saveTable">{{busy?'Сохраняем…':'Сохранить новую редакцию заключения'}}</button></div>
        </section>
        <section class="mtz-designer-panel mtz-history-panel"><h3>История и восстановление</h3><p>Возврат создаёт новую редакцию и не затрагивает уже сформированные МТЗ.</p>
          <select v-model.number="restoreRevision"><option v-for="item in editor.history" :key="item.revision" :value="item.revision">{{ item.revision }} · {{ item.label }}</option></select>
          <button class="secondary-button" type="button" :disabled="busy" @click="restore">Восстановить выбранную версию</button>
        </section>
      </div>
    </template>
  </section>
</template>
