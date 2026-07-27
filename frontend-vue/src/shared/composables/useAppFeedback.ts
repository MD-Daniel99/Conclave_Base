import { watch, type Ref } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'

type ConfirmOptions = {
  message: string
  header?: string
  acceptLabel?: string
  rejectLabel?: string
  danger?: boolean
}

export function useSuccessToast(successMessage: Ref<string>, summary = 'Готово') {
  const toast = useToast()

  watch(successMessage, (message) => {
    if (!message) {
      return
    }

    toast.add({
      severity: 'success',
      summary,
      detail: message,
      life: 3600,
    })
  })
}

export function useAppConfirm() {
  const confirmation = useConfirm()

  return (options: ConfirmOptions) => new Promise<boolean>((resolve) => {
    let settled = false

    const finish = (result: boolean) => {
      if (settled) {
        return
      }

      settled = true
      resolve(result)
    }

    confirmation.require({
      header: options.header ?? (options.danger ? 'Подтвердите удаление' : 'Подтвердите действие'),
      message: options.message,
      acceptLabel: options.acceptLabel ?? (options.danger ? 'Удалить' : 'Продолжить'),
      rejectLabel: options.rejectLabel ?? 'Отмена',
      acceptClass: options.danger ? 'p-button-danger' : undefined,
      rejectProps: {
        severity: 'secondary',
        outlined: true,
      },
      accept: () => finish(true),
      reject: () => finish(false),
      onHide: () => finish(false),
    })
  })
}
