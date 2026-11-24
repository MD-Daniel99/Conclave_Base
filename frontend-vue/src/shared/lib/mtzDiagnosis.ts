/** These are *suggestions by the equipment name*, not a medical diagnosis. */
export const MTZ_DISABILITY_REASONS = [
  'I Группа, Военная травма',
  'II Группа, Военная травма',
  'III Группа, Военная травма',
  'I Группа, Общее заболевание',
  'II Группа, Общее заболевание',
  'III Группа, Общее заболевание',
] as const

export const MTZ_DIAGNOSIS_GROUPS = {
  shoulder: ['Амп. Культя правого и левого плеча', 'Амп. Культя правого плеча', 'Амп. Культя левого плеча'],
  fingers: ['Амп. пальцев правой и левой руки', 'Амп. пальцев правой руки', 'Амп. пальцев левой руки'],
  forearm: ['Амп. Культя правого и левого предплечья', 'Амп. Культя правого предплечья', 'Амп. Культя левого предплечья'],
  hand: ['Амп. Культя правой и левой кисти', 'Амп. Культя правой кисти', 'Амп. Культя левой кисти'],
  thigh: ['Амп. Культя правого и левого бедра', 'Амп. Культя правого бедра', 'Амп. Культя левого бедра'],
  shin: ['Амп. Культя правой и левой голени', 'Амп. Культя правой голени', 'Амп. Культя левой голени'],
} as const

export const MTZ_DIAGNOSES = Object.values(MTZ_DIAGNOSIS_GROUPS).flatMap((values) => [...values])

type DiagnosisGroup = keyof typeof MTZ_DIAGNOSIS_GROUPS

export function suggestMtzDiagnoses(tsrLabels: string[]): string[] {
  const detected = new Set<DiagnosisGroup>()
  for (const entry of tsrLabels) {
    const value = String(entry ?? '').toLowerCase().replace(/ё/g, 'е')
    if (/(^|[\s-])плеч[аоуеи]|протез плеча/.test(value)) detected.add('shoulder')
    if (/предплеч/.test(value)) detected.add('forearm')
    if (/пальц|пальцев/.test(value)) detected.add('fingers')
    if (/кист/.test(value)) detected.add('hand')
    if (/бедр/.test(value)) detected.add('thigh')
    if (/голен|голени/.test(value)) detected.add('shin')

    // Known reference codes for older TSR records containing no description.
    const code = value.replace(/8\(0?1\)/g, '8.1').replace(/8\.01/g, '8.1')
    if (/8\.1-07-12|8-07-05|8-07-10/.test(code)) detected.add('thigh')
    if (/8\.1-07-14|8-07-04|8-07-09/.test(code)) detected.add('shin')
  }
  return Object.entries(MTZ_DIAGNOSIS_GROUPS)
    .filter(([group]) => detected.has(group as DiagnosisGroup))
    .flatMap(([, values]) => [...values])
}
