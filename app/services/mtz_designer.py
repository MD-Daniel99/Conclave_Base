"""Versioned, validated form mappings for ZET medical-technical conclusions.

User changes live only under STORAGE_DIR; shipped templates and patient records
remain untouched. All reads and writes take the same flock as conclusion edits.
"""
from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import tempfile
from pathlib import Path

from app.services.mtz_conclusions import LIBRARY

CONFIG_FILE = LIBRARY / 'form_settings.json'
FIELD_ID = re.compile(r'^(?:custom_[a-z][a-z0-9_]{1,35})$')
SOURCE_KEYS = ('full_name','birth_date','passport_series','passport_number',
               'passport_issuer','passport_issue_date','passport_department','mse_reference')
CORE_FIELDS = ('disability_group_reason','diagnoses','stump_condition','activity_level',
               'weight_kg','amputation_level','amputation_code')
DEFAULT_REASONS = [f'{g} Группа, {cause}' for cause in ('Военная травма','Общее заболевание')
                   for g in ('I','II','III')]
DEFAULT_DIAGNOSES = [
    'Амп. Культя правого и левого плеча', 'Амп. Культя правого плеча', 'Амп. Культя левого плеча',
    'Амп. пальцев правой и левой руки', 'Амп. пальцев правой руки', 'Амп. пальцев левой руки',
    'Амп. Культя правого и левого предплечья','Амп. Культя правого предплечья','Амп. Культя левого предплечья',
    'Амп. Культя правой и левой кисти', 'Амп. Культя правой кисти', 'Амп. Культя левой кисти',
    'Амп. Культя правого и левого бедра', 'Амп. Культя правого бедра', 'Амп. Культя левого бедра',
    'Амп. Культя правой и левой голени', 'Амп. Культя правой голени', 'Амп. Культя левой голени'
]


def default_config():
    return {
        'version': 1,
        'auto': {key: {'label':label, 'source':key, 'default':''} for key,label in (
            ('full_name','ФИО'), ('birth_date','Дата рождения'),
            ('passport_series','Серия паспорта'), ('passport_number','Номер паспорта'),
            ('passport_issuer','Кем выдан паспорт'), ('passport_issue_date','Дата выдачи паспорта'),
            ('passport_department','Код подразделения'), ('mse_reference','Справка МСЭ'))},
        'manual': {
            'disability_group_reason':{'label':'Причина инвалидности', 'options':DEFAULT_REASONS},
            'diagnoses':{'label':'Диагноз', 'options':DEFAULT_DIAGNOSES},
            'stump_condition':{'label':'Состояние культи', 'options':['Функциональная','Нефункциональная']},
            'activity_level':{'label':'Уровень активности', 'options':['2-3','3-4']},
            'weight_kg':{'label':'Вес пациента (кг)', 'placeholder':'Например: 82'},
            'amputation_level':{'label':'Уровень ампутации для этого ТСР', 'placeholder':'Например: Средняя треть голени'},
            'amputation_code':{'label':'Код уровня ампутации (необязательно)', 'placeholder':'Например: 1.1.3'},
        },
        'codes': {'activity_level':{'2-3':'1.3.1','3-4':'1.3.3'}},
        'custom_fields':[],
    }


def _read_unlocked():
    if not CONFIG_FILE.is_file():
        return default_config()
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        return validate_config(data)
    except (ValueError, TypeError, OSError, KeyError) as exc:
        raise ValueError('Повреждены настройки конструктора МТЗ; обратитесь к администратору') from exc


def get_config():
    LIBRARY.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY/'.lock','a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        return _read_unlocked()


def _short(value, label, length=180):
    if not isinstance(value,str) or not (1 <= len(value.strip()) <= length):
        raise ValueError(f'Поле «{label}» должно содержать от 1 до {length} символов')
    if '{{' in value or '}}' in value:
        raise ValueError(f'В поле «{label}» нельзя использовать метки DOCX')
    return value.strip()


def _options(value, name):
    if not isinstance(value,list) or not (1 <= len(value) <= 60):
        raise ValueError(f'Укажите от 1 до 60 значений для «{name}»')
    result = [_short(x,name,160) for x in value]
    if len(set(result)) != len(result):
        raise ValueError(f'В списке «{name}» повторяются варианты')
    return result


def validate_config(value):
    if not isinstance(value,dict): raise ValueError('Неверный формат настроек МТЗ')
    base = default_config()
    version=value.get('version',1)
    if type(version)!=int or not 1<=version<=1000000000:raise ValueError('Неверная версия настроек')
    data = {'version':version, 'auto':{}, 'manual':{}, 'codes':{}, 'custom_fields':[]}
    auto = value.get('auto',{})
    manual = value.get('manual',{})
    if not isinstance(auto,dict) or not isinstance(manual,dict):raise ValueError('Ошибка полей конструктора')
    for field in SOURCE_KEYS:
        raw = auto.get(field,base['auto'][field]);
        if not isinstance(raw,dict):raise ValueError('Ошибка поля ' + field)
        source = raw.get('source',field)
        if source not in SOURCE_KEYS: raise ValueError('Неизвестный источник автозаполнения: ' + str(source))
        data['auto'][field] = {'label':_short(raw.get('label',base['auto'][field]['label']),field),
                             'source':source,'default':str(raw.get('default',''))[:250]}
    for field in CORE_FIELDS:
        raw = manual.get(field,base['manual'][field])
        if not isinstance(raw,dict):raise ValueError('Ошибка поля ' + field)
        obj={'label':_short(raw.get('label',base['manual'][field]['label']),field)}
        if 'options' in base['manual'][field]:
            obj['options']=_options(raw.get('options',base['manual'][field]['options']),field)
        else:
            obj['placeholder']=str(raw.get('placeholder',base['manual'][field].get('placeholder','')))[:180]
        data['manual'][field]=obj
    codes=value.get('codes',{})
    if not isinstance(codes,dict):raise ValueError('Ошибка кодов классификации')
    mapping=codes.get('activity_level',base['codes']['activity_level'])
    if not isinstance(mapping,dict):raise ValueError('Ошибка кодов уровня активности')
    normalized={}
    for option in data['manual']['activity_level']['options']:
        code = str(mapping.get(option,'')).strip()
        if code and not re.fullmatch(r'1\.3\.\d{1,3}',code):
            raise ValueError('Код уровня активности должен иметь вид 1.3.1')
        normalized[option]=code
    data['codes']={'activity_level':normalized}
    fields=value.get('custom_fields',[])
    if not isinstance(fields,list) or len(fields)>20:raise ValueError('Не более 20 пользовательских полей')
    ids=set()
    for field in fields:
        if not isinstance(field,dict):raise ValueError('Неверный формат пользовательского поля')
        key=field.get('key','')
        if not isinstance(key,str) or not FIELD_ID.fullmatch(key) or key in ids:
            raise ValueError('Ключ дополнительного поля должен иметь вид custom_name и быть уникальным')
        ids.add(key)
        kind=field.get('kind')
        scope=field.get('scope','shared')
        if kind not in ('text','select','auto') or scope not in ('shared','per_item'):
            raise ValueError('Недопустимый вид/область пользовательского поля')
        record={'key':key,'label':_short(field.get('label',''),key), 'kind':kind, 'scope':scope,
                'required':bool(field.get('required',False)), 'placeholder':str(field.get('placeholder',''))[:180]}
        if kind == 'select':record['options']=_options(field.get('options',[]),key)
        if kind == 'auto':
            if field.get('source') not in SOURCE_KEYS:
                raise ValueError('Неизвестный источник автоматического поля')
            record['source']=field['source']
        data['custom_fields'].append(record)
    return data


def _atomic_write(path: Path, raw: bytes):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.mtz-config-',suffix='.tmp')
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def set_config(value):
    normalized=validate_config(value)
    LIBRARY.mkdir(parents=True,exist_ok=True)
    with open(LIBRARY/'.lock','a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        active=_read_unlocked()
        if normalized['version']!=active['version']:
            raise ValueError('Поля МТЗ изменены другим сотрудником. Обновите конструктор перед сохранением')
        previous_keys={f['key'] for f in active['custom_fields']}
        remaining_keys={f['key'] for f in normalized['custom_fields']}
        removed=previous_keys-remaining_keys
        if removed:
            # Never allow a field still referenced by published DOCX blocks to
            # be removed from the constructor; this would break generation.
            from app.services import mtz_conclusions as conclusions
            from docx import Document
            for template in conclusions.list_templates():
                _,file_path=conclusions.find_template(template['value'])
                doc=Document(file_path)
                text='\n'.join(cell.text for t in doc.tables for row in t.rows for cell in row.cells)
                still_used={key for key in removed if re.search(r'\{\{\s*'+re.escape(key)+r'\s*\}\}',text)}
                if still_used:
                    raise ValueError('Нельзя удалить поле '+', '.join(sorted(still_used))+
                        ': оно используется в опубликованном заключении «'+template['label']+'»')
        normalized['version']+=1
        _atomic_write(CONFIG_FILE,json.dumps(normalized,ensure_ascii=False,indent=2).encode('utf-8'))
    return normalized


def validate_extras(config, shared:dict, selections: list):
    """Enforce controlled values; prevents arbitrary template-token injection."""
    declared={f['key']:f for f in config['custom_fields']}
    unknown=set(shared)-{k for k,f in declared.items() if f['scope']=='shared' and f['kind']!='auto'}
    if unknown:raise ValueError('Неизвестные поля МТЗ: ' + ', '.join(sorted(unknown)))
    def validate_map(values,scope):
        for key,field in declared.items():
            if field['scope']!=scope or field['kind']=='auto':continue
            raw=values.get(key,'')
            if not isinstance(raw,str) or len(raw)>500:raise ValueError('Слишком длинное значение поля ' + key)
            if field['required'] and not raw.strip():raise ValueError('Заполните поле «' + field['label'] + '»')
            if field['kind']=='select' and raw and raw not in field['options']:
                raise ValueError('Недопустимое значение поля «' + field['label']+'»')
    validate_map(shared,'shared')
    for item in selections:
        values=getattr(item,'extra_fields',{}) or {}
        if set(values)-{k for k,f in declared.items() if f['scope']=='per_item' and f['kind']!='auto'}:
            raise ValueError('Неизвестное дополнительное поле в заключении')
        validate_map(values,'per_item')
