<script setup lang="ts">
import ConfirmDialog from 'primevue/confirmdialog'
import Toast from 'primevue/toast'
import TableHorizontalScrollbar from '@/shared/ui/TableHorizontalScrollbar.vue'
import { useModalScrollRestoration } from '@/shared/composables/useModalScrollRestoration'

useModalScrollRestoration()
</script>

<template>
  <RouterView />
  <Toast position="top-right" />
  <ConfirmDialog />
  <TableHorizontalScrollbar />
</template>
