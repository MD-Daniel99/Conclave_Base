"""Validated, patient-free conclusion fragments for a single ZET-headed MTZ.

Only DOCX body paragraphs/tables between the conclusion heading and the
signatures are imported. File uploads are untrusted: no external relationships,
macros, hyperlinks or images are copied to the approved fragments.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import io
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

STORAGE = Path(os.environ.get("STORAGE_DIR", "/app/storage"))
LIBRARY = STORAGE / "mtz_conclusion_templates"
BUILTIN_DIR = Path(__file__).resolve().parents[1] / "templates" / "mtz_conclusions"
BUILTIN_INDEX = BUILTIN_DIR / "index.json"
CODE_RE = re.compile(r"(?<!\d)(8(?:\(\d{1,3}\)|\.\d{1,3})?-\d{2}-\d{2}(?:\(\d{1,3}\))?)(?!\d)")
MAX_DOCX_BYTES = 10 * 1024 * 1024
MAX_ZIP_UNPACKED = 35 * 1024 * 1024
MAX_TEMPLATES_UPLOAD = 25
MAX_TEMPLATE_COUNT = 40


def normalized_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _text(paragraph_or_cell):
    return normalized_title(paragraph_or_cell.text)


def _filename_for(tid: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{5,100}", tid):
        raise ValueError("Некорректный идентификатор шаблона")
    return tid + ".docx"


def _safe_docx(raw: bytes) -> None:
    if not raw or len(raw) > MAX_DOCX_BYTES:
        raise ValueError("DOCX должен иметь размер до 10 МБ")
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 2500 or sum(x.file_size for x in entries) > MAX_ZIP_UNPACKED:
                raise ValueError("DOCX содержит слишком много данных")
            paths = {x.filename for x in entries}
            if "word/document.xml" not in paths or "[Content_Types].xml" not in paths:
                raise ValueError("Файл не является допустимым DOCX")
            if any(x.lower().endswith((".bin", ".vba", ".exe")) or "vbaProject" in x for x in paths):
                raise ValueError("Макросы и исполняемые вложения в МТЗ запрещены")
    except BadZipFile as exc:
        raise ValueError("Повреждённый DOCX") from exc


def _blocks(document):
    for el in document.element.body.iterchildren():
        if el.tag == qn("w:p"):
            yield "p", Paragraph(el, document)
        elif el.tag == qn("w:tbl"):
            yield "t", Table(el, document)


def _table_valid(table: Table) -> bool:
    if not (2 <= len(table.rows) <= 150) or not (2 <= len(table.columns) <= 8):
        return False
    return any("Уровень ампутации" in " ".join(_text(c) for c in r.cells) for r in table.rows)


def _plain_paragraph_xml(p):
    """Rebuild plain text and controlled boldness; discard links, fields and images."""
    node = OxmlElement("w:p")
    pp = OxmlElement("w:pPr")
    keep = OxmlElement("w:keepNext")
    pp.append(keep); node.append(pp)
    r = OxmlElement("w:r")
    rp = OxmlElement("w:rPr")
    bold = OxmlElement("w:b"); rp.append(bold)
    r.append(rp)
    t = OxmlElement("w:t"); t.text = _text(p)
    r.append(t); node.append(r)
    return node


def _sanitized_table_xml(table: Table):
    el = copy.deepcopy(table._element)
    # The contents of an approved conclusion are text only. Preserve original
    # table cell merges, paragraph styles and run formatting without copying any
    # source relationship (and therefore without old Smart branding or images).
    for node in list(el.iter()):
        if node.tag in {qn('w:drawing'), qn('w:pict'), qn('w:object'), qn('w:fldSimple'), qn('w:hyperlink'), qn('w:altChunk')}:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    for node in list(el.xpath('.//w:instrText')):
        node.getparent().remove(node)
    return el


def extract_conclusions(raw: bytes) -> list[tuple[str, str, bytes]]:
    """Return (exact full TSR code, label, fragment DOCX bytes), or reject.

    One uploaded DOCX may contain multiple complete "code + table" blocks.
    Source headers, personal data, signatures, images and footers are omitted.
    """
    _safe_docx(raw)
    doc = Document(io.BytesIO(raw))
    blocks = list(_blocks(doc))
    begin = next((i for i, (kind, part) in enumerate(blocks)
                  if kind == "p" and "ЗАКЛЮЧЕНИЕ" in _text(part).upper()), None)
    if begin is None:
        # A DOCX consisting only of TSR conclusion blocks is also supported.
        begin = -1
    end = next((i for i, (kind, part) in enumerate(blocks)
                if i > begin and kind == "p" and _text(part).startswith("Врач-хирург")), len(blocks))
    results: list[tuple[str, str, bytes]] = []
    title: str | None = None
    for kind, part in blocks[begin+1:end]:
        if kind == "p":
            value = _text(part)
            match = CODE_RE.search(value)
            if match:
                # Remove only the leading sequence number (not the TSR code).
                title = re.sub(r"^\s*\d{1,3}\s*[.)]\s*(?=8(?:\(|\.|-))", "", value)
                # Counts such as "– 2 шт." in historical patient forms are
                # patient-specific, not part of the generic TSR specification.
                title = re.sub(r"\s*[–—-]\s*\d+\s*шт\.?\s*$", "", title, flags=re.I)
        elif kind == "t" and title and _table_valid(part):
            table_text = " ".join(_text(cell) for row in part.rows for cell in row.cells).lower()
            if any(token in table_text for token in ('паспорт:', 'фио:', 'дата рождения:', 'справка мсэ')):
                raise ValueError('Таблица заключения содержит персональные данные: загрузите только блок заключения ТСР')
            code = CODE_RE.search(title).group(1)
            fragment = Document()
            body = fragment.element.body
            sect = body.sectPr
            body.insert(body.index(sect), _title_xml(title))
            body.insert(body.index(sect), _sanitized_table_xml(part))
            blob = io.BytesIO(); fragment.save(blob)
            results.append((code, title, blob.getvalue()))
            title = None
    if not results:
        raise ValueError("Не удалось найти заключение: требуется заголовок с кодом ТСР и таблица с полем «Уровень ампутации»")
    if len(results) > MAX_TEMPLATES_UPLOAD:
        raise ValueError("За один раз можно загрузить не более 25 заключений")
    return results


def _title_xml(title: str):
    node = OxmlElement("w:p")
    props = OxmlElement("w:pPr")
    keep = OxmlElement("w:keepNext"); props.append(keep)
    node.append(props)
    run = OxmlElement("w:r")
    rp = OxmlElement("w:rPr")
    fonts = OxmlElement('w:rFonts')
    fonts.set(qn('w:ascii'),'Times New Roman')
    fonts.set(qn('w:hAnsi'),'Times New Roman')
    rp.append(fonts)
    bold = OxmlElement("w:b"); rp.append(bold)
    sz = OxmlElement('w:sz'); sz.set(qn('w:val'),'24'); rp.append(sz)
    run.append(rp)
    text = OxmlElement("w:t"); text.text = title
    run.append(text); node.append(run)
    return node


def _index():
    try:
        return json.loads(BUILTIN_INDEX.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def _load_custom():
    location = LIBRARY / "index.json"
    if not location.is_file():
        return []
    return json.loads(location.read_text(encoding="utf-8"))


def list_templates():
    # A published revision supersedes its source without ever mutating the
    # approved files included in the Docker image.
    from app.services.mtz_template_editor import revision_metadata
    versions = revision_metadata()
    base = [dict(entry, builtin=True) for entry in _index()] + [
        dict(entry, builtin=False) for entry in _load_custom() if not entry.get("deleted")]
    for entry in base:
        current = versions.get(entry["value"])
        entry['revision'] = current.get('revision',0) if current else 0
        if current:
            entry['label'] = current.get('label',entry['label'])
            entry['tsr_code'] = current.get('tsr_code',entry['tsr_code'])
    return base


def find_template(key: str):
    record = next((entry for entry in list_templates() if entry["value"] == key), None)
    if record is None:
        raise ValueError("Шаблон МТЗ не найден или удалён")
    from app.services.mtz_template_editor import current_path
    path = current_path(record["value"],record["builtin"])
    if not path.is_file():
        raise FileNotFoundError(f"Не найден шаблон заключения {record['value']}")
    return record, path


def _write_index(records):
    LIBRARY.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="mtz-index-", suffix=".json", dir=LIBRARY)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(records, handle, ensure_ascii=False, indent=2)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, LIBRARY / "index.json")
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def add_templates(raw: bytes) -> list[dict]:
    fragments = extract_conclusions(raw)  # validate before acquiring a write lock
    LIBRARY.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY / ".lock", "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = _load_custom()
        existing = {r.get("sha256") for r in records if not r.get("deleted")}
        created = []
        to_write = []
        for code, title, blob in fragments:
            digest = hashlib.sha256(blob).hexdigest()
            if digest in existing:
                continue
            item = {"value": "mtz_" + uuid.uuid4().hex, "label": title[:250], "tsr_code": code,
                    "sha256": digest, "deleted": False}
            created.append(item); to_write.append((item, blob)); existing.add(digest)
        try:
            for record, blob in to_write:
                (LIBRARY / _filename_for(record["value"])).write_bytes(blob)
            _write_index(records + created)
        except Exception:
            for record, _ in to_write:
                (LIBRARY / _filename_for(record["value"])).unlink(missing_ok=True)
            raise
        return created


def delete_template(key: str) -> None:
    if any(r["value"] == key for r in _index()):
        raise ValueError("Встроенный утверждённый шаблон нельзя удалить; можно удалить только загруженные")
    LIBRARY.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY / ".lock", "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = _load_custom()
        found = next((r for r in rows if r["value"] == key and not r.get("deleted")), None)
        if found is None:
            raise ValueError("Загруженный шаблон не найден")
        found["deleted"] = True
        _write_index(rows)
    # Keep the physical DOCX so existing generated documents remain immutable,
    # and a deletion never destroys historical data.


def render_fragment(path: Path, *, amputation_level: str, stump_condition: str,
                    activity_level: str, weight_kg: str, number: int,
                    amputation_code: str = '', activity_codes: dict | None = None,
                    extra_fields: dict | None = None):
    """Return safe (paragraph, table) OOXML blocks with template-aware field mapping.

    Historic specifications can contain several 1.1 rows. If staff supplies
    exactly their original semicolon-separated values, the individual source
    codes stay in place. Otherwise we collapse the old patient-specific 1.1
    rows into a single free-text row, rather than leaving contradictory levels
    and classification codes from another patient.
    """
    doc = Document(path)
    table = next((table for table in doc.tables if _table_valid(table)), None)
    if table is None:
        raise ValueError("Заключение не содержит корректной таблицы")
    heading = next((p for p in doc.paragraphs if CODE_RE.search(p.text)), None)
    if heading is None:
        raise ValueError("Отсутствует код ТСР в заключении")
    heading_el = copy.deepcopy(heading._element)
    for text_node in heading_el.xpath('.//w:t'):
        if text_node.text and CODE_RE.search(text_node.text):
            text_node.text = f"{number}. " + normalized_title(text_node.text)
            break
    # Original ZET: conclusion titles are compact Times New Roman 11 pt.
    # Historical DOCX exports sometimes inherit 14 pt from their styles.
    from docx.shared import Pt
    for run in heading_el.xpath('.//w:r'):
        rpr = run.find(qn('w:rPr'))
        if rpr is None: rpr = OxmlElement('w:rPr'); run.insert(0,rpr)
        fonts=rpr.find(qn('w:rFonts'))
        if fonts is None:fonts=OxmlElement('w:rFonts');rpr.insert(0,fonts)
        fonts.set(qn('w:ascii'),'Times New Roman');fonts.set(qn('w:hAnsi'),'Times New Roman')
        size=rpr.find(qn('w:sz'))
        if size is None:size=OxmlElement('w:sz');rpr.append(size)
        size.set(qn('w:val'),'22')
    table_el = copy.deepcopy(table._element)
    # Retain borders, merges, bold and paragraph spacing; only cap run sizes
    # that exceed the 11 pt specification of the approved ZET TSR table.
    for run in table_el.xpath('.//w:r'):
        rpr=run.find(qn('w:rPr'))
        if rpr is None:rpr=OxmlElement('w:rPr');run.insert(0,rpr)
        fonts=rpr.find(qn('w:rFonts'))
        if fonts is None:fonts=OxmlElement('w:rFonts');rpr.insert(0,fonts)
        fonts.set(qn('w:ascii'),'Times New Roman');fonts.set(qn('w:hAnsi'),'Times New Roman')
        size=rpr.find(qn('w:sz'))
        if size is None:size=OxmlElement('w:sz');rpr.append(size)
        try:
            if int(size.get(qn('w:val')) or '28')>22:size.set(qn('w:val'),'22')
        except ValueError:size.set(qn('w:val'),'22')
    render_table = Table(table_el, doc)
    level_rows = []
    for row in render_table.rows:
        cells = row.cells
        if len(cells) < 3: continue
        label = _text(cells[1] if len(cells) > 3 else cells[0]).lower()
        if 'уровень ампутации' in label:
            level_rows.append(row)
    if not level_rows:
        raise ValueError('Не найден уровень ампутации в таблице заключения')
    source_levels = [normalized_title(row.cells[-1].text) for row in level_rows]
    selected_level = normalized_title(amputation_level)
    code_override = normalized_title(amputation_code or '')
    if code_override and not re.fullmatch(r'1\.1\.\d{1,3}', code_override):
        raise ValueError('Код уровня ампутации должен иметь вид 1.1.3')
    if len(level_rows)>1:
        if selected_level.lower() != '; '.join(source_levels).lower():
            first = level_rows[0]
            _change_cell(first.cells[-1], selected_level)
            if len(first.cells) > 3: _change_cell(first.cells[-2], '')
            for row in level_rows[1:]:
                table_el.remove(row._tr)
    else:
        first = level_rows[0]
        _change_cell(first.cells[-1], selected_level)
        if len(first.cells)>3 and source_levels[0].lower()!=selected_level.lower():
            _change_cell(first.cells[-2], '')
    if code_override and len(level_rows[0].cells)>3:
        _change_cell(level_rows[0].cells[-2], code_override)
    # Rebuild row collection after removal of old, patient-specific 1.1 rows.
    for row in Table(table_el, doc).rows:
        cells = row.cells
        if len(cells) < 3: continue
        label = _text(cells[1] if len(cells) > 3 else cells[0]).lower()
        if 'состояние культи' in label:
            original = normalized_title(cells[-1].text)
            _change_cell(cells[-1], stump_condition)
            if original != stump_condition and len(cells)>3:
                _change_cell(cells[-2], '')
        elif 'уровень активности' in label:
            original = normalized_title(cells[-1].text)
            _change_cell(cells[-1], activity_level)
            if len(cells)>3:
                # Codes 2-3 => 1.3.1 and 3-4 => 1.3.3 are present in
                # approved example MTZs. They are configurable by the editor.
                code = (activity_codes or {}).get(activity_level,'')
                if code:
                    _change_cell(cells[-2],code)
                elif original != activity_level:
                    _change_cell(cells[-2],'')
        elif 'вес пациента' in label:
            _change_cell(cells[-1], weight_kg)
    substitutions=extra_fields or {}
    if substitutions:
        import re as _re
        def resolve_extra(match):
            key=match.group(1)
            if key not in substitutions:
                raise ValueError('Неизвестное дополнительное поле МТЗ: ' + key)
            return str(substitutions[key]).strip()
        for text_node in table_el.xpath('.//w:t'):
            old_text=text_node.text or ''
            text_node.text=_re.sub(r'\{\{\s*(custom_[a-z][a-z0-9_]{1,35})\s*\}\}',
                resolve_extra,old_text)
    unresolved=' '.join((node.text or '') for node in table_el.xpath('.//w:t'))
    if re.search(r'\{\{\s*custom_',unresolved):
        raise ValueError('Незаполненное дополнительное поле в заключении')
    for tr in table_el.xpath('./w:tr'):
        trpr = tr.find(qn('w:trPr'))
        if trpr is None:
            trpr = OxmlElement('w:trPr'); tr.insert(0, trpr)
        if trpr.find(qn('w:cantSplit')) is None:
            trpr.append(OxmlElement('w:cantSplit'))
    return heading_el, table_el


def _change_cell(cell, replacement: str):
    """Replace text while keeping initial run font and paragraph formatting."""
    p = cell.paragraphs[0]
    if p.runs:
        p.runs[0].text = replacement
        for r in p.runs[1:]: r.text = ""
    else:
        p.add_run(replacement)
    for extra in cell.paragraphs[1:]:
        for r in extra.runs: r.text = ""
