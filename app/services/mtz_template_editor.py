"""Safe DOCX cell editing with immutable revisions of conclusion fragments.

Approved built-ins never change. Every edit produces a complete validated DOCX
under STORAGE_DIR; a corrupted change is never made active.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from app.services import mtz_conclusions as lib
from app.services.mtz_designer import _atomic_write

VERSIONS = lib.LIBRARY / 'versions.json'


def _versions():
    if not VERSIONS.is_file():return {}
    return json.loads(VERSIONS.read_text(encoding='utf-8'))


def revision_metadata():
    return _versions()


def current_path(key: str, builtin: bool):
    original=(lib.BUILTIN_DIR if builtin else lib.LIBRARY) / lib._filename_for(key)
    history=_versions().get(key)
    if history and history.get('current'):
        edited=lib.LIBRARY / lib._filename_for(history['current'])
        if not edited.exists():raise ValueError('Не найдена версия МТЗ: ' + key)
        return edited
    return original


def _unique_cells(row):
    result=[];seen=set()
    for i,cell in enumerate(row.cells):
        ident=id(cell._tc)
        if ident not in seen:
            result.append({'col':i,'text':cell.text.strip()})
            seen.add(ident)
    return result


def get_editor(key: str):
    record,path=lib.find_template(key)
    doc=Document(path)
    heading=next((p for p in doc.paragraphs if lib.CODE_RE.search(p.text)),None)
    table=next((t for t in doc.tables if lib._table_valid(t)),None)
    if not heading or table is None:raise ValueError('Нет редактируемой таблицы')
    history=_versions().get(key,{})
    return {'value':key, 'title':heading.text.strip(), 'tsr_code':record['tsr_code'],
            'builtin':record['builtin'], 'revision':history.get('revision',0),
            'history': [{'revision':0,'label':'Исходная версия'}]+[
                {'revision':p['revision'],'label':p.get('label','Изменение')} for p in history.get('snapshots',[])],
            'rows':[{'source_index':i,'cells':_unique_cells(row)} for i,row in enumerate(table.rows)]}


def _apply_title(paragraph,text):
    # Never recreate the paragraph: keep paragraph margins, tabs, fonts and runs.
    runs=list(paragraph.runs)
    if not runs:paragraph.add_run(text);return
    runs[0].text=text
    for run in runs[1:]:run.text=''


def _apply_row(row,cell_edits,known_fields:set[str]):
    present={entry['col']:entry['text'] for entry in _unique_cells(row)}
    if (not isinstance(cell_edits,list) or len(cell_edits)!=len(present)
        or {entry.get('col') for entry in cell_edits}!=set(present)):
        raise ValueError('Изменена структура ячеек, сохранение отменено')
    for entry in cell_edits:
        text=entry['text']
        if not isinstance(text,str) or len(text)>1300 or '\x00' in text:
            raise ValueError('Недопустимая длина текста в таблице')
        # Only user-defined markers (plus supported system markers) are allowed.
        for match in re.findall(r'\{\{\s*([^{}]+?)\s*\}\}',text):
            if not (match in known_fields or match in ('amputation_level','amputation_code','stump_condition','stump_condition_code','activity_level','activity_level_code','weight_kg')):
                raise ValueError('Неизвестная метка автозаполнения: '+match)
        cell=row.cells[entry['col']]
        # Multiple paragraphs are left in place; only textual content updated.
        lib._change_cell(cell,text)


def _edited_docx(source:Path, title:str, rows:list,known_fields:set[str]):
    if not isinstance(title,str) or len(title)>310 or not lib.CODE_RE.search(title):
        raise ValueError('Укажите название с полным кодом ТСР')
    if not isinstance(rows,list) or not (2 <=len(rows)<=150):
        raise ValueError('Таблица должна содержать от 2 до 150 строк')
    doc=Document(source)
    heading=next((p for p in doc.paragraphs if lib.CODE_RE.search(p.text)),None)
    table=next((t for t in doc.tables if lib._table_valid(t)),None)
    if heading is None or table is None:raise ValueError('Некорректная таблица заключения')
    original=list(table.rows)
    original_xml=[copy.deepcopy(row._tr) for row in original]
    _apply_title(heading,title)
    parent=table._tbl
    for row in original:parent.remove(row._tr)
    used_indices=[]
    for payload in rows:
        if not isinstance(payload,dict):raise ValueError('Неверная строка МТЗ')
        index=payload.get('source_index')
        clone=payload.get('clone_from')
        if type(index)==int and 0 <= index <len(original):
            if index in used_indices:raise ValueError('Строка таблицы продублирована')
            used_indices.append(index)
            source_index=index
        elif index is None and type(clone)==int and 0 <=clone<len(original):
            source_index=clone
        else:raise ValueError('Неизвестный источник строки таблицы')
        row_xml=copy.deepcopy(original_xml[source_index])
        parent.append(row_xml)
        from docx.table import _Row
        row_obj=_Row(row_xml,table)
        _apply_row(row_obj,payload.get('cells'),known_fields)
    if not lib._table_valid(table):
        raise ValueError('Таблица должна содержать поле «Уровень ампутации»')
    # Never allow personal data in a reusable fragment.
    if any(any(s in cell.text.lower() for s in ('фио:', 'дата рождения:', 'паспорт:', 'справка мсэ')) for row in table.rows for cell in row.cells):
        raise ValueError('В шаблоне заключения обнаружены личные данные')
    return doc


def _write_version(key, source, title, rows, expected_revision, label='Изменение шаблона'):
    record,path=lib.find_template(key)
    from app.services.mtz_designer import get_config
    known_fields={f['key'] for f in get_config()['custom_fields']}
    lib.LIBRARY.mkdir(parents=True,exist_ok=True)
    with open(lib.LIBRARY/'.lock','a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        all_versions=_versions()
        old=all_versions.get(key,{'revision':0,'snapshots':[]})
        if expected_revision != old['revision']:
            raise ValueError('Шаблон был изменён другим сотрудником. Обновите редактор перед сохранением')
        edited=_edited_docx(source,title,rows,known_fields)
        new_rev=int(old['revision'])+1
        filename=f'{key}__rev_{new_rev}'
        pathout=lib.LIBRARY/lib._filename_for(filename)
        if pathout.exists():raise ValueError('Конфликт версий шаблона')
        from io import BytesIO
        buf=BytesIO();edited.save(buf)
        blob=buf.getvalue()
        lib._safe_docx(blob)
        # Re-read to validate the serialization, not just an in-memory model.
        check=Document(BytesIO(blob))
        if not any(lib._table_valid(t) for t in check.tables):
            raise ValueError('После сохранения нарушена структура таблицы')
        _atomic_write(pathout,blob)
        metadata=copy.deepcopy(old)
        metadata.update({'revision':new_rev,'current':filename, 'tsr_code':lib.CODE_RE.search(title).group(1),
                         'label':title})
        metadata['snapshots']=metadata.get('snapshots',[])+[{'revision':new_rev,'filename':filename,'label':label[:100]}]
        all_versions[key]=metadata
        try:
            _atomic_write(VERSIONS,json.dumps(all_versions,ensure_ascii=False,indent=2).encode('utf-8'))
        except Exception:
            pathout.unlink(missing_ok=True)
            raise
    return get_editor(key)


def save_template(key:str,payload:dict):
    record,path=lib.find_template(key)
    return _write_version(key,path,payload.get('title',''),payload.get('rows',[]),
                          payload.get('revision'),label='Правка полей и таблицы')


def restore_template(key:str,target_revision:int,expected_revision:int):
    record,path=lib.find_template(key)
    history=_versions().get(key,{'revision':0,'snapshots':[]})
    if target_revision==0:
        path=(lib.BUILTIN_DIR if record['builtin'] else lib.LIBRARY)/lib._filename_for(key)
    else:
        selected=next((p for p in history['snapshots'] if p['revision']==target_revision),None)
        if not selected:raise ValueError('Нет такой версии шаблона')
        path=lib.LIBRARY/lib._filename_for(selected['filename'])
    doc=Document(path)
    title=next((p.text for p in doc.paragraphs if lib.CODE_RE.search(p.text)),None)
    table=next((t for t in doc.tables if lib._table_valid(t)),None)
    if not title or table is None:raise ValueError('Повреждённая предыдущая версия')
    return _write_version(key,path,title,[{'source_index':i,'cells':_unique_cells(row)} for i,row in enumerate(table.rows)],
                          expected_revision,label=f'Восстановлена версия {target_revision}')
