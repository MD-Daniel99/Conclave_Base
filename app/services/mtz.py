"""One ZET-headed medical-technical conclusion with one or many TSR sections.

The common approved header, indication list, signatures, footer and page fields
come solely from mtz_zet_thigh_mpu_approved.docx. Source conclusions contain
only their title and specification table; historical personal data/branding are
never merged into the output.
"""
from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from sqlalchemy.orm import Session

from app.services.document_filenames import next_document_filename
from app.services import mtz_conclusions, mtz_designer

STORAGE_DIR = os.environ.get("STORAGE_DIR", "/app/storage")
BASE_TEMPLATE = Path(__file__).resolve().parents[1] / 'templates' / 'mtz_zet_thigh_mpu_approved.docx'

DISABILITY_REASONS = tuple(
    f"{group} Группа, {cause}"
    for cause in ("Военная травма", "Общее заболевание")
    for group in ("I", "II", "III")
)
DIAGNOSIS_OPTIONS = (
    "Амп. Культя правого и левого плеча", "Амп. Культя правого плеча", "Амп. Культя левого плеча",
    "Амп. пальцев правой и левой руки", "Амп. пальцев правой руки", "Амп. пальцев левой руки",
    "Амп. Культя правого и левого предплечья", "Амп. Культя правого предплечья", "Амп. Культя левого предплечья",
    "Амп. Культя правой и левой кисти", "Амп. Культя правой кисти", "Амп. Культя левой кисти",
    "Амп. Культя правого и левого бедра", "Амп. Культя правого бедра", "Амп. Культя левого бедра",
    "Амп. Культя правой и левой голени", "Амп. Культя правой голени", "Амп. Культя левой голени",
)


def list_mtz_templates() -> list[dict]:
    return mtz_conclusions.list_templates()


def _format_date(value: Any) -> str:
    if not value: return ""
    if hasattr(value, 'strftime'): return value.strftime('%d.%m.%Y')
    raw = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d-%m-%Y'):
        try: return datetime.strptime(raw[:10], fmt).strftime('%d.%m.%Y')
        except ValueError: pass
    return raw


def _safe_part(value: str, fallback: str = 'документ') -> str:
    clean = re.sub(r'[^0-9A-Za-zА-Яа-яЁё()_. -]+', '_', value or '')
    return re.sub(r'\s+', ' ', clean).strip(' ._')[:96] or fallback


def _latest_passport(passports: list[dict[str, Any]]) -> dict[str, Any]:
    return max(passports, key=lambda item: (int(item.get('version') or 0), str(item.get('created_at') or ''))) if passports else {}


def _parse_passport_number(value: str) -> tuple[str, str]:
    digits = re.sub(r'\D', '', value)
    if len(digits) == 10: return digits[:4], digits[4:]
    parts = value.strip().rsplit(' ', 1)
    return (parts[0], parts[1]) if len(parts) == 2 else ('', value.strip())


def prepare_mtz_context(client: dict[str, Any], payload: Any) -> dict[str, str]:
    full_name = re.sub(r'\s+', ' ', ' '.join(str(client.get(k) or '').strip() for k in ('last_name','first_name','middle_name'))).strip()
    passport = _latest_passport(list(client.get('passports') or []))
    series, number = _parse_passport_number(str(passport.get('series_number') or ''))
    mse = str(client.get('mse_reference') or '').strip()
    if not all((full_name,passport.get('birth_date'),series,number,passport.get('issued_by'),passport.get('issue_date'),passport.get('department_code'))):
        raise ValueError('Для МТЗ необходимо заполнить ФИО, дату рождения и паспортные данные пациента')
    diagnoses = list(payload.diagnoses)
    config = mtz_designer.get_config()
    mtz_designer.validate_extras(config, getattr(payload,'extra_fields',{}) or {}, list(getattr(payload,'items',[]) or []))
    if not diagnoses or any(d not in config['manual']['diagnoses']['options'] for d in diagnoses):
        raise ValueError('Выберите один или несколько диагнозов из перечня')
    if payload.disability_group_reason not in config['manual']['disability_group_reason']['options']:
        raise ValueError('Выберите группу и причину инвалидности')
    if payload.stump_condition not in config['manual']['stump_condition']['options'] or payload.activity_level not in config['manual']['activity_level']['options']:
        raise ValueError('Проверьте состояние культи и уровень активности')
    try: weight = float(str(payload.weight_kg).strip().replace(',', '.'))
    except (TypeError,ValueError) as exc: raise ValueError('Укажите корректный вес пациента') from exc
    if not 0 < weight <= 500: raise ValueError('Вес пациента должен быть больше 0 и не превышать 500 кг')
    result = {
        'full_name':full_name, 'birth_date':_format_date(passport['birth_date']),
        'passport_series':series,'passport_number':number,
        'passport_issuer':str(passport['issued_by']).strip(),
        'passport_issue_date':_format_date(passport['issue_date']),
        'passport_department':str(passport['department_code']).strip(),
        'mse_reference':mse,'disability_group_reason':str(payload.disability_group_reason).strip(),
        'diagnosis':'; '.join(dict.fromkeys(diagnoses)),
        'stump_condition':payload.stump_condition,'activity_level':payload.activity_level,
        'weight_kg':format(weight,'g').replace('.',','),
    }
    original = dict(result)
    for field,definition in config['auto'].items():
        result[field]=original.get(definition['source'],'') or definition['default']
    if not result['mse_reference']:
        raise ValueError('Заполните справку МСЭ в карточке пациента, в разделе СНИЛС / ИПРА / МСЭ')
    for definition in config['custom_fields']:
        if definition['scope']=='shared':
            result[definition['key']] = (original.get(definition['source'],'') if definition['kind']=='auto'
                else (getattr(payload,'extra_fields',{}) or {}).get(definition['key'],''))
    return result


def _body_blocks(document):
    return list(document.element.body.iterchildren())


def _block_text(block) -> str:
    return ''.join(t.text or '' for t in block.xpath('.//w:t'))


def _make_base_without_original_conclusion(document) -> None:
    body = document.element.body
    blocks = _body_blocks(document)
    heading = next((i for i, b in enumerate(blocks) if b.tag == qn('w:p') and 'ЗАКЛЮЧЕНИЕ:' in _block_text(b)), None)
    signatures = next((i for i, b in enumerate(blocks) if b.tag == qn('w:p') and _block_text(b).strip().startswith('Врач-хирург')), None)
    if heading is None or signatures is None or signatures <= heading:
        raise ValueError('Некорректный базовый шаблон МТЗ Движения ЗЕТ')
    for block in blocks[heading + 1:signatures]:
        body.remove(block)
    # One fresh paragraph after the common conclusion heading is the insertion
    # point: the code does not need to copy an old header or a signature block.


def _paragraphs(document):
    for p in document.paragraphs: yield p
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs: yield p
    for section in document.sections:
        for p in section.header.paragraphs: yield p
        for p in section.footer.paragraphs: yield p

_TOKEN = re.compile(r'\{\{\s*([a-z][a-z0-9_]*)\s*\}\}',re.I)


def _replace_tokens_preserving_runs(paragraph, context: dict[str, str]):
    runs = list(paragraph.runs)
    if not runs: return
    whole = ''.join(r.text for r in runs)
    matches = list(_TOKEN.finditer(whole))
    for match in reversed(matches):
        key=match.group(1)
        if key not in context: raise ValueError('Неизвестное поле базового МТЗ: ' + key)
        start, end = match.span(); offset=0; left=None; right=None
        for i,run in enumerate(runs):
            n=len(run.text)
            if left is None and offset <= start < offset+n: left=(i,start-offset)
            if offset < end <= offset+n: right=(i,end-offset)
            offset+=n
        if left is None or right is None: raise ValueError('Ошибка разметки плейсхолдера МТЗ')
        li,ls=left; ri,rs=right
        if li==ri:
            runs[li].text = runs[li].text[:ls]+context[key]+runs[li].text[rs:]
        else:
            runs[li].text=runs[li].text[:ls]+context[key]
            for run in runs[li+1:ri]:run.text=''
            runs[ri].text=runs[ri].text[rs:]


def compose_mtz_document(context: dict[str,str], selected: list[tuple],
                         stump_condition: str, activity_level: str, weight_kg: str,
                         config:dict | None = None):
    """Assemble a DOCX preserving base styles, legal header and signatures."""
    config=config or mtz_designer.get_config()
    doc = Document(BASE_TEMPLATE)
    _make_base_without_original_conclusion(doc)
    for p in _paragraphs(doc):
        _replace_tokens_preserving_runs(p,context)
    body = doc.element.body
    signature_node = next(b for b in body.iterchildren() if b.tag == qn('w:p') and _block_text(b).strip().startswith('Врач-хирург'))
    pos=body.index(signature_node)
    for idx, selection in enumerate(selected,1):
        fragment_path, amputation_level = selection[:2]
        amputation_code = selection[2] if len(selection)>2 else ''
        item_extras = selection[3] if len(selection)>3 else {}
        extra_values={field['key']: context.get(field['source'],'') if field['kind']=='auto' else
            (item_extras.get(field['key'],'') if field['scope']=='per_item' else context.get(field['key'],''))
            for field in config['custom_fields']}
        head, table = mtz_conclusions.render_fragment(fragment_path,amputation_level=amputation_level,
                                 amputation_code=amputation_code,
                                 stump_condition=stump_condition, activity_level=activity_level,
                                 weight_kg=weight_kg, number=idx,
                                 activity_codes=config['codes']['activity_level'],
                                 extra_fields=extra_values)
        body.insert(pos,head);pos+=1
        body.insert(pos,table);pos+=1
        if idx == len(selected):
            # Keep the last table row with the following signature block where
            # possible; Word may otherwise strand only signatures on a new page.
            last_row = table.xpath('./w:tr')[-1]
            for paragraph in last_row.xpath('./w:tc/w:p'):
                ppr = paragraph.find(qn('w:pPr'))
                if ppr is None:
                    ppr = OxmlElement('w:pPr'); paragraph.insert(0, ppr)
                if ppr.find(qn('w:keepNext')) is None:
                    ppr.append(OxmlElement('w:keepNext'))
    if len(selected) > 1:
        # Extra empty paragraphs in the approved signature block are decorative.
        # For multi-TSR documents, remove *only* those empties so signatories
        # are not orphaned on an otherwise empty final page.
        signature_paragraphs = doc.paragraphs
        doctor = next((i for i, p in enumerate(signature_paragraphs) if p.text.strip() == 'Врач-хирург'), -1)
        director = next((i for i, p in enumerate(signature_paragraphs) if p.text.strip().startswith('Генеральный директор')), -1)
        if 0 <= doctor < director:
            for para in signature_paragraphs[doctor+1:director]:
                if not para.text.strip() and not para._element.xpath('.//w:drawing | .//w:pict | .//w:br'):
                    para._element.getparent().remove(para._element)
    if len(doc.tables) != len(selected) + 1:
        raise ValueError('Не совпадает количество таблиц МТЗ и выбранных ТСР')
    for para in _paragraphs(doc):
        if '{{' in para.text or '}}' in para.text:
            raise ValueError('Осталось незаполненное поле МТЗ: ' + para.text[:90])
    return doc


def generate_mtz(db:Session, client_id, payload):
    from app import crud, models
    client=crud.get_client(db,client_id)
    if not client:raise ValueError('Пациент не найден')
    context=prepare_mtz_context(client,payload)
    config=mtz_designer.get_config()
    selections = list(getattr(payload,'items',[]) or [])
    if not selections and getattr(payload,'template_type',None):
        # Backward compatibility for old clients, still one conclusion.
        selections=[type('LegacySelection',(),{'template_type':payload.template_type,'amputation_level':payload.amputation_level})()]
    if not selections or len(selections)>mtz_conclusions.MAX_TEMPLATE_COUNT:
        raise ValueError('Выберите от 1 до 40 заключений ТСР')
    selected=[]; metadata=[]
    for item in selections:
        level=str(item.amputation_level or '').strip()
        if not (1<=len(level)<=512):raise ValueError('Для каждого ТСР необходимо указать уровень ампутации')
        info,path=mtz_conclusions.find_template(str(item.template_type))
        code=str(getattr(item,'amputation_code',None) or '').strip()
        if code and not re.fullmatch(r'1\.1\.\d{1,3}',code):
            raise ValueError('Код уровня ампутации должен иметь вид 1.1.3')
        selected.append((path,level,code,getattr(item,'extra_fields',{}) or {}))
        metadata.append({'template_type':info['value'],'tsr_code':info['tsr_code'],
                         'title':info['label'],'amputation_level':level,
                         'amputation_code':code or None})
    doc=compose_mtz_document(context,selected,payload.stump_condition,payload.activity_level,context['weight_kg'],config=config)
    storage=Path(STORAGE_DIR);storage.mkdir(parents=True,exist_ok=True)
    patient=_safe_part(str(client.get('last_name') or context['full_name']),'пациент')
    filename=next_document_filename(db,client_id,f'МТЗ ЗЕТ_{patient}_{len(selected)} ТСР.docx')
    stored_path=storage / f'{uuid.uuid4()}_{filename}'
    try:
        doc.save(stored_path)
        document=models.Document(client_id=client_id,filename=filename,storage_path=str(stored_path),
             content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
             size=stored_path.stat().st_size,document_type='mtz_zet_thigh_mpu',document_number=None,
             contract_total=None,certificate_amount=None,certificate_id=None,
             contract_metadata={'template_type':'mtz_zet_combined','tsr_conclusions':metadata,
                                'tsr_codes':[m['tsr_code'] for m in metadata],
                                'form_config_version':config['version']})
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise
    db.add(document)
    try:db.commit();db.refresh(document);return document
    except Exception:db.rollback();stored_path.unlink(missing_ok=True);raise
