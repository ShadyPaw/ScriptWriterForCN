#!/usr/bin/env python3
"""Audit the skill's plain Fountain subset; not quality, runtime or legal review.

Exit 0: machine checks passed; 1: audit issues; 2: input error.
"""
import argparse
import json
import math
import re
import sys
import unicodedata
from decimal import Decimal
from pathlib import Path

EPISODE = re.compile(r'^#\s+Episode\s+(\d+)(?:\s*[-:–—].*)?$', re.I)
SCENE = re.compile(r'^(?:INT\./EXT\.|INT/EXT\.?|I/E\.?|INT\.?|EXT\.?|EST\.?)\s+\S', re.I)
SCENE_ID = re.compile(r'\s+#([^#]+)#\s*$')
WORD = re.compile(r"[^\W_]+(?:[’'\-][^\W_]+|[.,](?=\d)\d+)*", re.UNICODE)
TRANSITION = re.compile(r'^(?:[A-Z][A-Z \-]* TO:|FADE (?:IN:|OUT\.|TO BLACK\.)|CUT TO BLACK\.)$')
CONTINUATION = re.compile(r'^[ \t]*\[\[CONTINUE SCENE:[ \t]*([^\]\n]+)\]\][ \t]*$', re.I | re.M)


def word_count(value):
    return len(WORD.findall(value))


def positive_int(value, label):
    if type(value) is not int or value < 1:
        raise ValueError(f'{label} must be a positive integer.')


def valid_tolerance(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < 1:
        raise ValueError('Tolerance must be a finite fraction in [0, 1).')


def read_budgets(data, default_tolerance):
    if not isinstance(data, dict) or set(data) != {'scope', 'episodes'}:
        raise ValueError('Budget JSON requires exactly scope and episodes.')
    if data['scope'] not in ('batch', 'project') or not isinstance(data['episodes'], list):
        raise ValueError('Budget scope must be batch or project; episodes must be an array.')
    budgets = {}
    for row in data['episodes']:
        if not isinstance(row, dict) or set(row) - {'episode', 'target_words', 'tolerance'}:
            raise ValueError('Budget row fields: episode, target_words, optional tolerance.')
        n, target = row.get('episode'), row.get('target_words')
        positive_int(n, 'Budget episode')
        positive_int(target, 'Episode target_words')
        tolerance = row.get('tolerance', default_tolerance)
        valid_tolerance(tolerance)
        if n in budgets:
            raise ValueError(f'Duplicate budget for episode {n}.')
        budgets[n] = {'target_words': target, 'tolerance': tolerance}
    return budgets


def parse_script(text, initial_scene=None):
    """Return counted episodes, printable elements and structural issues together."""
    text = text.replace('\r\n', '\n').replace('\r', '\n').lstrip('\ufeff')
    issues, episodes, elements = [], [], []

    def issue(message, line=None):
        issues.append({'category': 'structure', 'line': line, 'message': message})

    def remove_comments(value, opening, closing):
        pattern = re.escape(opening) + r'[\s\S]*?' + re.escape(closing)
        value = re.sub(pattern, lambda m: '\n' * m[0].count('\n') or ' ', value)
        if opening in value or closing in value:
            issue(f'Unbalanced comment delimiters: {opening} {closing}')
        return value

    # Boneyards are removed first; directives inside them stay hidden.
    text = remove_comments(text, '/*', '*/')
    directives = {}
    for match in CONTINUATION.finditer(text):
        directives[text.count('\n', 0, match.start()) + 1] = match[1].strip()
    for n, line in enumerate(text.splitlines(), 1):
        if '[[continue scene:' in line.lower() and (n not in directives or not directives[n]):
            issue('Malformed continuation directive; use one standalone line with a nonempty scene ID.', n)
    text = CONTINUATION.sub(lambda m: 'CONTINUATION_DIRECTIVE', text)
    text = remove_comments(text, '[[', ']]')

    active_scene = None
    seen_scene_ids = set()
    if initial_scene is not None:
        if '\n' in initial_scene or not SCENE.match(initial_scene):
            raise ValueError('initial_scene must be a single supported scene heading.')
        sid = SCENE_ID.search(initial_scene)
        active_scene = {'heading': SCENE_ID.sub('', initial_scene), 'id': sid[1].strip() if sid else None}
        if sid:
            seen_scene_ids.add(active_scene['id'])
    current = None
    seen_episodes = set()
    body_started = False

    def element(kind, content, line, **extra):
        elements.append({'kind': kind, 'text': content, 'line': line,
                         'episode': current['episode'] if current else None, **extra})

    def enter_scene(line):
        nonlocal body_started
        if not body_started and not current['scenes'] and active_scene:
            current['continued_scene'] = active_scene.copy()
            element('continuation', active_scene['heading'], line, scene_id=active_scene['id'])
        if active_scene is None:
            issue('Body appears before the first scene heading; supply batch context if continuing.', line)
        body_started = True

    for match in re.finditer(r'\S[^\n]*(?:\n(?![ \t]*\n)[^\n]+)*', text):
        block = match[0].strip()
        lines = [s.strip() for s in block.splitlines()]
        line_no = text.count('\n', 0, match.start()) + 1
        first = lines[0]
        ep = EPISODE.fullmatch(first)
        if ep:
            if len(lines) != 1:
                issue('Episode heading must be its own block.', line_no)
            number = int(ep[1])
            if number in seen_episodes:
                issue(f'Duplicate episode {number}.', line_no)
            seen_episodes.add(number)
            current = {'episode': number, 'scenes': 0, 'scene_ids': [], 'continued_scene': None,
                       'dialogue_words': 0, 'action_words': 0, 'parenthetical_words': 0}
            episodes.append(current)
            body_started = False
            element('episode', first.lstrip('#').strip(), line_no)
            continue
        if first.lower().startswith('# episode'):
            issue('Malformed episode heading.', line_no)
            continue
        if current is None:
            metadata = r'^(Title|Credit|Author|Authors|Source|Contact|Copyright|Draft date|Notes):'
            if not re.match(metadata, first, re.I) or any(
                not re.match(metadata, s, re.I) and not re.match(r'^[ \t]+\S', raw)
                for s, raw in zip(lines[1:], match[0].splitlines()[1:])
            ):
                issue('Content before first episode is not supported title metadata.', line_no)
            else:
                element('metadata', block, line_no)
            continue
        if line_no in directives:
            if len(lines) != 1 or body_started or current['scenes']:
                issue('Continuation directive must stand alone before this episode body and any new scene.', line_no)
            if not active_scene or active_scene['id'] != directives[line_no]:
                issue('Continuation ID must match the immediately preceding active scene.', line_no)
            continue
        if SCENE.match(first):
            if len(lines) != 1:
                issue('Scene heading must be its own block.', line_no)
            current['scenes'] += 1
            sid = SCENE_ID.search(first)
            value = sid[1].strip() if sid else None
            if value:
                if value in seen_scene_ids:
                    issue(f'Duplicate scene ID {value}. Use continuation without a new heading.', line_no)
                seen_scene_ids.add(value)
                current['scene_ids'].append(value)
            active_scene = {'heading': SCENE_ID.sub('', first), 'id': value}
            element('scene', active_scene['heading'], line_no, scene_id=value)
            continue
        if any(EPISODE.match(s) or SCENE.match(s) for s in lines[1:]):
            issue('Missing blank line before episode or scene heading.', line_no)
        if first.startswith('#') or first.startswith('='):
            if len(lines) != 1:
                issue('Section/synopsis marker must be its own block.', line_no)
            if re.fullmatch(r'={3,}', first):
                element('page_break', '', line_no)
            continue
        if len(lines) == 1 and TRANSITION.fullmatch(first):
            element('transition', first, line_no)
            continue
        enter_scene(line_no)
        if any(s.startswith(('>', '~')) or re.match(r'^\.[^.\s]', s) or s.endswith('^') for s in lines):
            issue('Unsupported forced heading, centered text, lyric or dual-dialogue marker.', line_no)
        if '*' in block or '_' in block:
            issue('Inline emphasis/underscores are outside the plain-text subset; normalize a copy.', line_no)
        if any(s.startswith('@') for s in lines[1:]):
            issue('Missing blank line before character cue.', line_no)
        if 'CONTINUATION_DIRECTIVE' in block:
            issue('Continuation directive must be its own block.', line_no)
        if any(c.isalpha() and 'LATIN' not in unicodedata.name(c, '') for c in block):
            issue('Non-Latin text: manually verify the English word-count scope.', line_no)
        if first.startswith('@'):
            if not first[1:].strip():
                issue('Empty character cue.', line_no)
            parts = []
            dialogue_count = 0
            for entry in lines[1:]:
                kind = 'parenthetical' if entry.startswith('(') and entry.endswith(')') else 'dialogue'
                count = word_count(entry)
                current[kind + '_words'] += count
                if kind == 'dialogue':
                    dialogue_count += count
                parts.append({'kind': kind, 'text': entry})
            if not dialogue_count:
                issue('Character cue has no dialogue.', line_no)
            element('speech', first[1:].strip(), line_no, parts=parts)
        else:
            if not first.startswith('!') and first.isupper() and word_count(first) <= 6:
                issue('Ambiguous uppercase block: use @ for a cue or ! for action.', line_no)
            if first.startswith('(') and first.endswith(')'):
                issue('Orphan parenthetical outside a dialogue block.', line_no)
            action = block[1:] if first.startswith('!') else block
            current['action_words'] += word_count(action)
            element('action', action, line_no)

    if not episodes:
        issue('No episodes found. Use # Episode N headings.')
    for episode in episodes:
        episode['total_words'] = sum(episode[k] for k in ('dialogue_words', 'action_words', 'parenthetical_words'))
        episode['scene_segments'] = episode['scenes'] + bool(episode['continued_scene'])
        if not episode['scenes'] and not episode['continued_scene']:
            issue(f'Episode {episode["episode"]} has no scene context.')
        if not episode['total_words']:
            issue(f'Episode {episode["episode"]} has no screenplay body.')
    return {'episodes': episodes, 'elements': elements, 'issues': issues}


def audit(text, expected_episodes=None, target_words=None, tolerance=0.0, start_episode=1,
          episode_budgets=None, initial_scene=None, include_elements=False):
    positive_int(start_episode, 'Start episode')
    if expected_episodes is not None:
        positive_int(expected_episodes, 'Expected episodes')
    if target_words is not None:
        positive_int(target_words, 'Target words')
    valid_tolerance(tolerance)
    budgets = read_budgets(episode_budgets, tolerance) if episode_budgets is not None else None
    parsed = parse_script(text, initial_scene)
    episodes, issues = parsed['episodes'], parsed['issues']

    def issue(category, message):
        issues.append({'category': category, 'line': None, 'message': message})

    ids = [ep['episode'] for ep in episodes]
    count = expected_episodes if expected_episodes is not None else len(episodes)
    expected_ids = list(range(start_episode, start_episode + count))
    if ids != expected_ids:
        issue('structure', f'Episode sequence {ids} does not match {expected_ids}.')
    totals = {key: sum(ep[key] for ep in episodes) for key in
              ('dialogue_words', 'action_words', 'parenthetical_words', 'total_words', 'scenes', 'scene_segments')}

    def compare(actual, target, tol):
        fraction = Decimal(str(tol))
        lower, upper = Decimal(target) * (1 - fraction), Decimal(target) * (1 + fraction)
        return {'target_words': target, 'actual_words': actual, 'delta': actual - target,
                'tolerance': tol, 'lower': float(lower), 'upper': float(upper),
                'status': 'passed' if lower <= actual <= upper else 'failed'}

    total_check = {'status': 'not_checked'}
    if target_words is not None:
        total_check = compare(totals['total_words'], target_words, tolerance)
        if total_check['status'] == 'failed':
            issue('total_budget', f'Body word count {totals["total_words"]} is outside '
                  f'[{total_check["lower"]:g}, {total_check["upper"]:g}].')
    if budgets is not None:
        missing = sorted(set(expected_ids) - set(budgets))
        outside = sorted(set(budgets) - set(expected_ids))
        if missing:
            issue('episode_budgets', f'Missing budgets for episodes {missing}.')
        if outside and episode_budgets['scope'] == 'batch':
            issue('episode_budgets', f'Batch budgets include out-of-scope episodes {outside}.')
        selected_sum = sum(budgets[n]['target_words'] for n in expected_ids if n in budgets)
        if not missing and target_words is not None and selected_sum != target_words:
            issue('episode_budgets', f'Selected episode targets sum to {selected_sum}, not batch target {target_words}.')
        for ep in episodes:
            budget = budgets.get(ep['episode'])
            ep['budget_check'] = compare(ep['total_words'], budget['target_words'], budget['tolerance']) if budget else {'status': 'not_checked'}
            if ep['budget_check']['status'] == 'failed':
                issue('episode_budgets', f'Episode {ep["episode"]}: {ep["total_words"]} words; '
                      f'target {budget["target_words"]}, tolerance {budget["tolerance"]:g}.')
    else:
        for ep in episodes:
            ep['budget_check'] = {'status': 'not_checked'}
    checks = {
        'structure': 'failed' if any(i['category'] == 'structure' for i in issues) else 'passed',
        'total_budget': total_check,
        'episode_budgets': ('not_checked' if budgets is None else
                            'failed' if any(i['category'] == 'episode_budgets' for i in issues) else 'passed'),
        'creative_review': 'not_checked', 'human_feedback': 'not_checked',
        'release_legal_review': 'not_checked', 'render_review': 'not_checked'}
    result = {'scope': 'body = action + dialogue + parentheticals; headings/cues/notes excluded',
              'format': 'documented plain Fountain subset, not full Fountain',
              'passed_meaning': 'machine structure and supplied numeric constraints only',
              'expected_episodes': expected_episodes, 'start_episode': start_episode,
              'target_words': target_words, 'tolerance': tolerance,
              'budget_scope': episode_budgets['scope'] if budgets is not None else None,
              'episodes': episodes, 'totals': totals, 'checks': checks, 'issues': issues, 'passed': not issues}
    if include_elements:
        result['elements'] = parsed['elements']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    parser.add_argument('--expected-episodes', type=int)
    parser.add_argument('--start-episode', type=int, default=1)
    parser.add_argument('--target-words', type=int)
    parser.add_argument('--tolerance', type=float, default=0.0, help='Fraction, e.g. 0.05 = 5%%; default exact')
    parser.add_argument('--episode-budgets', type=Path, help='JSON: scope batch/project, episodes array')
    parser.add_argument('--initial-scene', help='Previous active scene heading for a continuing partial batch')
    parser.add_argument('--json', type=Path, dest='json_path')
    args = parser.parse_args()
    inputs = [p.resolve() for p in (args.manuscript, args.episode_budgets) if p]
    if args.json_path and args.json_path.resolve() in inputs:
        parser.error('JSON output must not overwrite an input file.')
    try:
        budgets = json.loads(args.episode_budgets.read_text(encoding='utf-8-sig')) if args.episode_budgets else None
        result = audit(args.manuscript.read_text(encoding='utf-8-sig'), args.expected_episodes,
                       args.target_words, args.tolerance, args.start_episode, budgets, args.initial_scene)
        output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
        if args.json_path:
            args.json_path.write_text(output, encoding='utf-8')
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(output, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
