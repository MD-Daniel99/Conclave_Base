import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ToastService from 'primevue/toastservice'
import Tooltip from 'primevue/tooltip'

import App from './App.vue'
import { router } from './app/router'
import { midnightIndigoPreset } from './app/theme'
import { focusTrap } from './shared/directives/focusTrap'
import { useAuthStore } from './app/stores/auth'
import { initResizableTables } from './shared/lib/resizableTables'
import './assets/styles.css'
import './assets/design-system.css'
import './assets/aurora-theme.css'
import './assets/light-refresh.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(PrimeVue, {
  ripple: true,
  theme: {
    preset: midnightIndigoPreset,
    options: {
      prefix: 'p',
      darkModeSelector: false,
      cssLayer: false,
    },
  },
})
app.use(ToastService)
app.use(ConfirmationService)
app.directive('tooltip', Tooltip)
app.directive('focus-trap', focusTrap)

app.mount('#app')

initResizableTables(() => useAuthStore(pinia).user?.user_id)
