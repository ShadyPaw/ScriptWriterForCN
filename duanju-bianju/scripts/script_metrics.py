"""Plan and audit Chinese short-drama manuscripts. Python 3 standard library only."""
import argparse
import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from pathlib import Path

EPISODE = re.compile(r'^##\s+第([0-9]+)集(?:\s+.*)?$')
SCENE = re.compile(r'^([0-9]+)-([0-9]+)\s+(日|夜|晨|昏|黄昏|清晨)\s+(内外|内|外)\s+(.+)$')
LATIN = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
START, END = '[正文开始]', '[正文结束]'


def units(text):
    """Han/other letters per character; contiguous Latin/digit tokens per word."""
    text = unicodedata.normalize('NFC', text)
    words = len(LATIN.findall(text))
    remainder = LATIN.sub('', text)
    return words + sum(unicodedata.category(c)[0] in 'LN' for c in remainder)


def content_line(line):
    if SCENE.fullmatch(line) or re.match(r'^人物\s*[：:]', line):
        return ''
    if re.match(r'^【闪回(?:开始|结束)】', line):
        return ''
    if line.startswith('【屏幕文字】'):
        return line[len('【屏幕文字】'):]
    if line.startswith(('△', '▲', 'Δ')):
        return line[1:]
    speaker = re.match(r'^([^：:]{1,40})[：:](.*)$', line)
    if speaker:
        directions = re.findall(r'[（(]([^）)]*)[）)]', speaker[1])
        directions = [d for d in directions if d.upper() not in ('OS', 'VO')]
        return ''.join(directions) + speaker[2]
    return line


def plan(episodes, total, weights=None):
    if episodes < 1 or total < episodes:
        raise ValueError('episodes须为正整数，total须足以为每集分配至少1字')
    values = [Decimal(v) for v in weights] if weights else [Decimal(1)] * episodes
    if len(values) != episodes or any(not v.is_finite() or v <= 0 for v in values):
        raise ValueError('weights必须有N项有限正数')
    raw = [Decimal(total) * v / sum(values) for v in values]
    amounts = [int(v.to_integral_value(rounding=ROUND_FLOOR)) for v in raw]
    order = sorted(range(episodes), key=lambda i: (-(raw[i] - amounts[i]), i))
    for i in order[:total - sum(amounts)]:
        amounts[i] += 1
    if any(v == 0 for v in amounts):
        raise ValueError('权重导致某集0字，请调整权重或总字数')
    return {'mode': 'plan', 'episodes': episodes, 'target_total': total,
            'allocated_total': sum(amounts), 'budgets': [
                {'episode': i + 1, 'weight': str(values[i]), 'target': amounts[i]}
                for i in range(episodes)]}


def audit(text, episodes, target=None, tolerance=Decimal(0), min_total=None,
          max_total=None, min_episode=None, max_episode=None):
    if episodes < 1 or not tolerance.is_finite() or not 0 <= tolerance <= 1:
        raise ValueError('episodes须为正整数，tolerance须在0到1之间')
    limits = [target, min_total, max_total, min_episode, max_episode]
    if any(v is not None and v < 0 for v in limits):
        raise ValueError('字数边界不能为负')
    for lo, hi in [(min_total, max_total), (min_episode, max_episode)]:
        if lo is not None and hi is not None and lo > hi:
            raise ValueError('下限不能大于上限')
    records, errors = [], []
    current = None
    in_body = False

    def error(number, message):
        errors.append({'line': number, 'message': message})

    def finish(number):
        if current is None:
            return
        if current['starts'] != 1 or current['ends'] != 1:
            error(number, f"第{current['episode']}集必须有且仅有一对正文标记")
        if not current['scenes']:
            error(number, f"第{current['episode']}集没有有效场头")
        if current['net_units'] == 0:
            error(number, f"第{current['episode']}集正文为空")
        if current['scenes'] != list(range(1, len(current['scenes']) + 1)):
            error(number, f"第{current['episode']}集场次应从1连续递增")
        if min_episode is not None and current['net_units'] < min_episode:
            error(number, f"第{current['episode']}集少于单集下限")
        if max_episode is not None and current['net_units'] > max_episode:
            error(number, f"第{current['episode']}集超过单集上限")

    for number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        heading = EPISODE.fullmatch(line)
        if heading:
            if in_body:
                error(number, '新集标题出现前，上一集正文未结束')
            finish(number)
            current = {'episode': int(heading[1]), 'line': number, 'starts': 0,
                       'ends': 0, 'scenes': [], 'net_units': 0,
                       'raw_non_whitespace_characters': 0}
            records.append(current)
            in_body = False
            continue
        if re.match(r'^#{1,6}\s*第.+集', line):
            error(number, '集标题请使用“## 第1集 集名”及半角阿拉伯数字')
        if line == START:
            if current is None:
                error(number, '正文开始标记之前缺少集标题')
                continue
            current['starts'] += 1
            if in_body or current['ends']:
                error(number, '正文开始标记重复或出现在结束之后')
            in_body = True
            continue
        if line == END:
            if current is None or not in_body:
                error(number, '正文结束标记没有对应的开始标记')
            if current is not None:
                current['ends'] += 1
            in_body = False
            continue
        if not in_body or not line:
            continue
        current['raw_non_whitespace_characters'] += sum(not c.isspace() for c in line)
        scene = SCENE.fullmatch(line)
        if scene:
            if int(scene[1]) != current['episode']:
                error(number, '场号的集号与所在集不一致')
            current['scenes'].append(int(scene[2]))
        elif re.match(r'^\d+[-－—]\d+', line):
            error(number, '场头格式不符：应为“1-1 日 内 地点”')
        elif not current['scenes']:
            error(number, '正文内容出现在首个场头之前')
        if re.search(r'(?:此处省略|后续略|正文待补|待补写|TODO|TBD)', line, re.I):
            error(number, '正文含疑似占位语，请人工核对')
        current['net_units'] += units(content_line(line))

    finish(len(text.splitlines()) + 1)
    ids = [r['episode'] for r in records]
    if ids != list(range(1, episodes + 1)):
        error(0, f'实际集号{ids}与约定第1至{episodes}集不符（含顺序/重复/缺集检查）')
    total = sum(r['net_units'] for r in records)
    if target is not None and abs(Decimal(total) - target) > Decimal(target) * tolerance:
        error(0, '正文净字数超出目标及约定容差')
    if min_total is not None and total < min_total:
        error(0, '正文净字数低于总下限')
    if max_total is not None and total > max_total:
        error(0, '正文净字数超过总上限')
    return {'mode': 'audit', 'ok': not errors, 'metric': 'creative-net-units-v1',
            'scope': '正文标记内动作、表演括注、台词、屏幕文字；不是Word字数',
            'expected_episodes': episodes, 'actual_episodes': len(records),
            'total_net_units': total, 'target': target, 'tolerance': str(tolerance),
            'delta': total - target if target is not None else None,
            'total_raw_non_whitespace_characters': sum(r['raw_non_whitespace_characters'] for r in records),
            'episodes': records, 'errors': errors,
            'limitations': '只检查集场编号、正文标记、计数和少量占位语；不评估剧情、原创性、完整性或法律合规。'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--episodes', type=int, required=True)
    p.add_argument('--total', type=int, required=True)
    p.add_argument('--weights', help='comma-separated positive weights, exactly N')
    p.add_argument('--out', type=Path)
    a = sub.add_parser('audit')
    a.add_argument('--script', type=Path, required=True)
    a.add_argument('--episodes', type=int, required=True)
    a.add_argument('--target', type=int)
    a.add_argument('--tolerance', type=Decimal, default=Decimal(0))
    for flag in ('min-total', 'max-total', 'min-episode', 'max-episode'):
        a.add_argument('--' + flag, type=int)
    a.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            result = plan(args.episodes, args.total, args.weights.split(',') if args.weights else None)
        else:
            result = audit(args.script.read_text(encoding='utf-8-sig'), args.episodes,
                           args.target, args.tolerance, args.min_total, args.max_total,
                           args.min_episode, args.max_episode)
        serialized = json.dumps(result, ensure_ascii=False, indent=2)
        if args.out:
            args.out.write_text(serialized + '\n', encoding='utf-8')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        print(serialized)
        return 0 if result.get('ok', True) else 1
    except (ValueError, InvalidOperation, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
