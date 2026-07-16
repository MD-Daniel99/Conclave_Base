"""Turn the approved ООО DOCX into a docxtpl template while preserving its layout."""
from pathlib import Path

from docx import Document


SOURCE = Path("app/templates/Проект договора от 150626.docx")
TARGET = Path("app/templates/llc_contract.docx")


def set_paragraph(paragraph, text: str) -> None:
    if not paragraph.runs:
        paragraph.add_run(text)
        return
    paragraph.runs[0].text = text
    for run in paragraph.runs[1:]:
        run.text = ""


def set_cell(cell, text: str) -> None:
    # Cell text can contain runs inside bookmarks/content controls that are not
    # exposed through paragraph.runs. Replacing the cell content avoids leaving
    # any sample values next to the Jinja expression.
    cell.text = text


def set_loop_table(table, values: list[str], *, total_values: list[str] | None = None) -> None:
    # The approved template has exactly three sample rows; reuse them as
    # docxtpl's opening marker, repeated data row and closing marker.
    marker_row, data_row, end_row = table.rows[1:4]
    for cell in marker_row.cells:
        set_cell(cell, "")
    set_cell(marker_row.cells[0], "{%tr for item in contract_items %}")
    for cell, value in zip(data_row.cells, values):
        set_cell(cell, value)
    for cell in end_row.cells:
        set_cell(cell, "")
    set_cell(end_row.cells[0], "{%tr endfor %}")
    if total_values is not None:
        for cell, value in zip(table.rows[4].cells, total_values):
            set_cell(cell, value)


def main() -> None:
    doc = Document(SOURCE)
    p = doc.paragraphs

    replacements = {
        0: "Договор № {{НомерДоговораБуквы}}/{{НомерДоговораЧисло}}",
        4: "г. Москва\t\t\t\t\t\t\t\t{{ДатаДоговора}} г.",
        6: "ООО «Смарт Движение», в лице Генерального директора Абашеева Георгия Дмитриевича, действующего на основании Устава, именуемое в дальнейшем «Исполнитель», с одной стороны, и {{ФИОЗаказчика}}, именуемый(ая) в дальнейшем «Потребитель», с другой стороны, совместно именуемые «Стороны», заключили настоящий Договор о нижеследующем:",
        13: "2.1. Стоимость выполнения работ и поставки ТСР по настоящему Договору составляет {{Сумма}} ({{СуммаПрописью}}) рублей, НДС не облагается на основании п.1. ч.2 ст. 149 Налогового кодекса Российской Федерации.",
        91: "_____________________ /Абашеев Г.Д./\t\t______________________ /{{ИнициалыЗаказчикаКратко}}/",
        105: "Приложение 1 от {{ДатаПриложения}}",
        106: "к Договору № {{НомерДоговора}} от {{ДатаДоговора}}",
        119: "ТСР изготавливаются на основании технических характеристик, предусмотренных ИПРА № {{НомерИПРА}} от {{ДатаВыдачиИПРА}}.",
        132: "_____________________ /Абашеев Г.Д./\t\t______________________ /{{ИнициалыЗаказчикаКратко}}/",
        136: "Приложение 2 от {{ДатаПриложения}}",
        137: "К Договору № {{НомерДоговора}} от {{ДатаДоговора}}",
        177: "Приложение 3 от {{ДатаПриложения}}",
        178: "К Договору № {{НомерДоговора}} от {{ДатаДоговора}}",
        180: "Акт сдачи-приемки работ № {{НомерАкта}}",
        182: "{{ДатаАкта}} г.",
        184: "ООО «Смарт Движение», в лице Генерального директора Абашеева Георгия Дмитриевича, действующего на основании Устава, именуемое в дальнейшем «Исполнитель», с одной стороны, и гр. {{ФИОЗаказчика}}, дата рождения {{ДатаРожденияЗаказчика}} г., паспорт: серия {{ПаспортСерия}} № {{ПаспортНомер}}, выдан {{КемВыданПаспорт}}, {{ДатаВыдачиПаспорта}} г., код подразделения {{КодПодразделения}}, адрес места жительства: {{АдресРегистрацииЗаказчика}}, именуемый(ая) в дальнейшем «Потребитель», с другой стороны, совместно именуемые «Стороны», подписали настоящий Акт о нижеследующем:",
        199: "_____________________ /Абашеев Г.Д./\t\t______________________ /{{ИнициалыЗаказчикаКратко}}/",
        217: "Приложение 4 от {{ДатаПриложения}}",
        218: "к Договору № {{НомерДоговора}} от {{ДатаДоговора}}",
        289: "_______________ {{ФИОЗаказчика}}, {{Телефон_заказчика}}",
        292: "{{ДатаДоговора}}",
        310: "Приложение 5 от {{ДатаПриложения}}",
        311: "к Договору № {{НомерДоговора}} от {{ДатаДоговора}}",
        315: "Я, {{ФИОЗаказчика}}, {{ДатаРожденияЗаказчика}} года рождения, место рождения {{МестоРожденияЗаказчика}}, паспорт: серия {{ПаспортСерия}} № {{ПаспортНомер}}, выдан {{КемВыданПаспорт}}, {{ДатаВыдачиПаспорта}} г., код подразделения {{КодПодразделения}}, зарегистрированный(ая) по адресу: {{АдресРегистрацииЗаказчика}}, даю своё согласие на обработку моих персональных данных.",
        331: "_______________ {{ФИОЗаказчика}}, {{Телефон_заказчика}}",
        334: "{{ДатаДоговора}}",
        353: "Приложение 6 от {{ДатаПриложения}}",
        354: "к Договору № {{НомерДоговора}} от {{ДатаДоговора}}",
        358: "Пациент (Ф.И.О.) {{ФИОЗаказчика}}",
        359: "Дата рождения {{ДатаРожденияЗаказчика}}",
        360: "Адрес {{АдресРегистрацииЗаказчика}}",
        396: "Приложение 7 от {{ДатаПриложения}}",
        397: "к Договору № {{НомерДоговора}} от {{ДатаДоговора}}",
        412: "_______________ {{ФИОЗаказчика}}, {{Телефон_заказчика}}",
        415: "{{ДатаДоговора}}",
    }
    for index, value in replacements.items():
        set_paragraph(p[index], value)

    requisites = doc.tables[0]
    set_cell(requisites.rows[0].cells[1], "Потребитель: {{ФИОЗаказчика}}")
    set_cell(requisites.rows[1].cells[1], "Паспорт: {{ПаспортПолностью}}")
    set_cell(requisites.rows[2].cells[1], "Адрес регистрации: {{АдресРегистрацииЗаказчика}}")
    set_cell(requisites.rows[3].cells[1], "СНИЛС: {{СНИЛСЗаказчика}}")
    set_cell(requisites.rows[4].cells[1], "Телефон: {{Телефон_заказчика}}")
    set_cell(requisites.rows[5].cells[1], "Дата выдачи ИПРА: {{ДатаВыдачиИПРА}}")
    set_cell(requisites.rows[6].cells[1], "Номер ИПРА: {{НомерИПРА}}")

    set_loop_table(doc.tables[1], ["{{item.number}}", "{{item.description}}", "{{item.quantity}}"])
    set_loop_table(
        doc.tables[2],
        ["{{item.name_and_code}}", "{{item.quantity}}", "{{item.price}}", "{{item.total_price}}"],
        total_values=["Итого", "{{ИтогоКоличество}}", "", "{{ИтогоСтоимость}}"],
    )
    set_loop_table(
        doc.tables[3],
        ["{{item.number}}", "{{item.description}}", "{{item.quantity}}", "{{item.components_text}}"],
    )

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    doc.save(TARGET)


if __name__ == "__main__":
    main()
