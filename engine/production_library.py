"""Owned native drafts for a script pipeline; no editor/home-index mutation.

The marker is an inventory, not a quality verdict. All consumers inspect the
current native documents and collected bytes; formal QC belongs to the caller.
"""
from copy import deepcopy
from pathlib import Path
import os
import shutil

import jy14_headless as j
import native_fonts as fonts
from native_edit import write_owned

MARKER = 'headless-production.json'
SCHEMA = 'headless-production-library/v1'
TEXT_LAYOUT_SCHEMA = 'centered-safe-subtitles/v1'


def mirrors(root, tid):
    return [root / j.nd.TIMELINE_FILE, root / 'template-2.tmp',
            root / (j.nd.TIMELINE_FILE + '.bak'),
            root / 'Timelines' / tid / j.nd.TIMELINE_FILE,
            root / 'Timelines' / tid / 'template-2.tmp',
            root / 'Timelines' / tid / (j.nd.TIMELINE_FILE + '.bak')]


def _inventory(root, names):
    result = {}
    for name in names:
        relative = Path(name)
        j.require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe native inventory path')
        path = root / relative
        j.require(path.is_file() and not path.is_symlink(), 'Native file missing/nonregular: ' + name)
        j.require(not any(p.is_symlink() for p in path.parents if p != root.parent), 'Native symlink rejected')
        result[name] = {'sha256': j.nd.digest(path), 'size': path.stat().st_size}
    return result


def _exact(timeline, plan):
    materials = {m['id']: (bucket, m) for bucket, rows in timeline['materials'].items() for m in rows}
    for track, expected in zip(timeline['tracks'], plan['tracks']):
        j.require(track.get('name') == expected.get('name', expected['type']), 'Native track name changed')
        for actual, spec in zip(track['segments'], expected['segments']):
            j.require(actual['target_timerange'] == {'start': spec.get('start_us', 0),
                        'duration': spec['duration_us']}, 'Native target microseconds changed')
            if expected['type'] in {'video', 'audio'}:
                j.require(actual['source_timerange'] == {'start': spec.get('source_start_us', 0),
                        'duration': spec.get('source_duration_us', spec['duration_us'])},
                        'Native source microseconds changed')
                speeds = [materials[r][1] for r in actual.get('extra_material_refs', [])
                          if materials[r][0] == 'speeds']
                j.require(len(speeds) == 1 and abs(speeds[0]['speed'] - spec.get('speed', 1)) < 1e-8,
                          'Native speed material changed')
            if expected['type'] == 'video' and spec.get('brightness'):
                groups = [g for g in actual.get('common_keyframes', []) if g['property_type'] == 'KFTypeBrightness']
                j.require(actual.get('enable_color_correct_adjust') is True and len(groups) == 1
                    and len(groups[0]['keyframe_list']) == 1
                    and groups[0]['keyframe_list'][0]['values'] == [spec['brightness']]
                    and groups[0]['keyframe_list'][0]['time_offset'] == 0, 'Native brightness changed')
            if expected['type'] == 'text' and spec.get('subtitle'):
                j.require(materials[actual['material_id']][1]['type'] == 'subtitle', 'Native subtitle type changed')


def inspect(root, *, require_literal=True):
    root = Path(root).resolve(strict=True)
    marker = j.read_json(root / MARKER)
    j.require(marker.get('schema') == SCHEMA, 'Native production marker unsupported')
    record, plan = marker['record'], marker['plan']
    j.require(_inventory(root, record['files']) == record['files'], 'Native inventory changed')
    target = Path(record['target'])
    j.require(target.is_absolute() and target.name == plan['name'] == record['name'], 'Native target identity invalid')
    paths = mirrors(root, record['timeline_id'])
    j.require(len({j.nd.digest(p) for p in paths}) == 1, 'Native active mirrors disagree')
    helper = j.nd.helper()
    runtime = helper._validate_runtime_environment()
    j.require(record['blueprint_sha256'] == j.BLUEPRINT_SHA and record['runtime_manifest'] == j.nd.MANIFEST_SHA
              and runtime['runtime_profile'] == record['runtime_profile'], 'Native runtime provenance changed')
    timeline = helper._decrypt_metadata_in_memory(paths[0])
    metadata = helper._decrypt_metadata_in_memory(root / 'draft_meta_info.json')
    project = j.read_json(root / 'Timelines/project.json')
    layout = j.read_json(root / 'timeline_layout.json')
    j.require(timeline['id'] == record['timeline_id'] == project['main_timeline_id'] == layout['activeTimeline'],
              'Native active timeline identity changed')
    j.require(metadata['draft_id'] == record['draft_id'] and timeline['name'] == target.name,
              'Native draft identity changed')
    j.require(project == j.read_json(root / 'Timelines/project.json.bak')
              and [p['id'] for p in project['timelines']] == [record['timeline_id']], 'Native project mirrors changed')
    j.verify_structure(timeline, metadata, plan, record['assets'], target,
                       font_assets=record.get('font_assets', ()))
    _exact(timeline, plan)
    for asset in [*record['assets'], *record.get('font_assets', ())]:
        local = root / asset['relative']
        j.require(local.is_file() and j.nd.digest(local) == asset['sha256'], 'Native collected asset changed')
        if require_literal:
            literal = target / asset['relative']
            j.require(literal.is_file() and not literal.is_symlink()
                      and j.nd.digest(literal) == asset['sha256'], 'Native literal asset missing/changed')
    fonts.verify_assets(record.get('font_assets', ()), timeline, target, root)
    j.resources.verify_files(record.get('native_resources', []), root, plan)
    return {'timeline': timeline, 'metadata': metadata, 'marker': marker, 'reference_root': str(target)}


def build(plan_path, work, library_root):
    j.build(plan_path, work, library_root=library_root)
    work = Path(work)
    record, plan = j.read_json(work / 'build.json'), j.read_json(work / 'plan.json')
    target = Path(record['target'])
    marker = {'schema': SCHEMA, 'plan': plan, 'record': record,
              'quality_status': 'UNCERTIFIED', 'home_index_modified': False}
    j.write(work / 'draft' / MARKER, marker)
    inspect(work / 'draft', require_literal=False)
    before = j.files_manifest(work / 'draft')
    temporary = target.parent / ('.building-' + j.identifier())
    shutil.copytree(work / 'draft', temporary)
    j.require(j.files_manifest(temporary) == before, 'Native install copy changed')
    j.exclusive_rename(temporary, target)
    inspect(target)
    return {'draft_path': str(target), 'draft_id': record['draft_id'], 'timeline_id': record['timeline_id'],
            'duration_us': record['duration_us'], 'backend': 'headless', 'quality_status': 'UNCERTIFIED'}


def rebase(value, source, target):
    if isinstance(value, dict):
        return {k: rebase(v, source, target) for k, v in value.items()}
    if isinstance(value, list):
        return [rebase(v, source, target) for v in value]
    if isinstance(value, str):
        if os.path.normcase(value) == os.path.normcase(str(source)):
            return str(target)
        for separator in ('/', '\\'):
            prefix = str(source).rstrip('/\\') + separator
            if os.path.normcase(value).startswith(os.path.normcase(prefix)):
                return str(target / value[len(prefix):])
    return value


def relocate(source, staging, target):
    """Collect a NEW copy and rebind native paths, preserving every UUID and cut."""
    source, staging, target = [Path(p).resolve() for p in (source, staging, target)]
    j.require(not staging.exists(), 'Native relocation staging exists')
    j.require(not staging.is_relative_to(source) and not source.is_relative_to(staging)
              and not target.is_relative_to(source) and target != source, 'Native relocation overlap')
    before = j.files_manifest(source)
    loaded = inspect(source)
    marker = deepcopy(loaded['marker'])
    old = Path(loaded['reference_root'])
    timeline = rebase(loaded['timeline'], old, target)
    fonts.rebase_existing(timeline, old, target)
    timeline['name'] = target.name
    metadata = rebase(loaded['metadata'], old, target)
    metadata.update(draft_name=target.name, draft_fold_path=str(target), draft_root_path=str(target.parent))
    marker['plan']['name'] = target.name
    marker['record'].update(target=str(target), name=target.name)
    shutil.copytree(source, staging)
    helper = j.nd.helper()
    first = mirrors(staging, marker['record']['timeline_id'])[0]
    temporary = staging / ('.codec-' + j.identifier())
    helper._encrypt_metadata_from_memory(j.nd.packed(timeline), temporary)
    temporary.replace(first)
    for path in mirrors(staging, marker['record']['timeline_id'])[1:]:
        write_owned(path, first.read_bytes())
    helper._encrypt_metadata_from_memory(j.nd.packed(metadata), temporary)
    temporary.replace(staging / 'draft_meta_info.json')
    marker['record']['files'] = _inventory(staging, marker['record']['files'])
    write_owned(staging / MARKER, marker)
    inspect(staging, require_literal=False)
    j.require(j.files_manifest(source) == before, 'Native relocation changed source')
    return {'source_unchanged': True, 'draft_id': marker['record']['draft_id'], 'reference_root': str(target)}


def equivalent(source, candidate, target):
    """Certify an already-published copy without depending on cipher randomness."""
    original = inspect(source)
    actual = inspect(candidate, require_literal=False)
    old, target = Path(original['reference_root']), Path(target).resolve()
    j.require(Path(actual['reference_root']) == target, 'Native existing target references changed')
    timeline = rebase(original['timeline'], old, target)
    fonts.rebase_existing(timeline, old, target)
    timeline['name'] = target.name
    metadata = rebase(original['metadata'], old, target)
    metadata.update(draft_name=target.name, draft_fold_path=str(target), draft_root_path=str(target.parent))
    j.require(timeline == actual['timeline'] and metadata == actual['metadata'], 'Native existing target content conflict')
    plan = deepcopy(original['marker']['plan'])
    plan['name'] = target.name
    j.require(plan == actual['marker']['plan'], 'Native existing target plan conflict')
    changed = {str(p.relative_to(Path(source))) for p in mirrors(Path(source), timeline['id'])}
    changed |= {MARKER, 'draft_meta_info.json'}
    left, right = j.files_manifest(Path(source)), j.files_manifest(Path(candidate))
    j.require({k: v for k, v in left.items() if k not in changed} ==
              {k: v for k, v in right.items() if k not in changed}, 'Native existing collected bytes conflict')
    return True
