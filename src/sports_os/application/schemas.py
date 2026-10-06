"""Published copies of module schemas. Module.schema() is the source of truth; these files are generated."""
import json
from pathlib import Path


def render(schema):
    return json.dumps(schema, ensure_ascii=False, indent=2) + '\n'


def drift(registry, directory):
    """Return module IDs whose published schema file is missing or differs from Module.schema()."""
    directory = Path(directory)
    stale = []
    for info in registry.list():
        key = info['module_id']
        path = directory / f'{key}.json'
        if not path.exists() or path.read_text(encoding='utf-8') != render(registry.get(key).schema()):
            stale.append(key)
    return stale


def write(registry, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for key in drift(registry, directory):
        (directory / f'{key}.json').write_text(render(registry.get(key).schema()), encoding='utf-8')
        written.append(key)
    return written


def _rows(schema, prefix=''):
    required = set(schema.get('required', []))
    for key, child in schema.get('properties', {}).items():
        name = prefix + key
        if 'const' in child:
            kind = str(child['const'])
        elif 'enum' in child:
            kind = str(child['enum'])
        else:
            kind = str(child.get('type', ''))
        yield f'|{name}|{kind}|{"是" if key in required else "否"}|'
        yield from _children(child, name)


def _children(schema, name):
    if schema.get('type') == 'object':
        yield from _rows(schema, name + '.')
        extra = schema.get('additionalProperties')
        if isinstance(extra, dict) and extra.get('type') in ('object', 'array'):
            yield from _children(extra, name + '.{key}')
    elif schema.get('type') == 'array' and isinstance(schema.get('items'), dict):
        yield from _children(schema['items'], name + '[]')


def dictionary_tables(registry):
    """Markdown field tables for docs/DATA_DICTIONARY.md, generated from Module.schema()."""
    parts = []
    for info in registry.list():
        key = info['module_id']
        rows = list(_rows(registry.get(key).schema())) or ['|（空payload）|object|—|']
        parts += [f'### {key}', '', '|字段|类型/枚举|父对象内必填|', '|---|---|---|', *rows, '']
    return '\n'.join(parts)


DICTIONARY_MARKER = '<!-- generated: module payload tables (sports_os.application.schemas) -->\n'


def dictionary_text(registry, current):
    """Replace everything after DICTIONARY_MARKER with freshly generated tables."""
    head = current.split(DICTIONARY_MARKER)[0]
    return head + DICTIONARY_MARKER + '\n' + dictionary_tables(registry)
