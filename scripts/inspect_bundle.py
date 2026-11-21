"""Inventory question sources without modifying them. Python standard library only."""
import argparse
import csv
import io
import json
import re
from collections import Counter
from pathlib import Path

EXT = {'.md', '.txt', '.html', '.json', '.csv'}
HEADING = re.compile(r'^#{1,6}[ \t]+(.+)$', re.M)
QUESTION = re.compile(r'^(填空(?:题)?|大题)\s*([A-Za-z]?\d+)(?![\d.])')
ANSWER = re.compile(r'^\s*(?:\*\*)?(?:参考答案|答案|答|解)\s*[:：](?:\*\*)?(.*?)(?=^\s*(?:\*\*)?解析[:：]|\Z)', re.M | re.S)
CHAPTER = re.compile(r'第\s*([\d一二三四五六七八九十百零〇两]+)\s*章')
TYPES = {'填空': '填空', '填空题': '填空', 'blank': '填空', 'fill': '填空', '大题': '大题', 'essay': '大题', 'written': '大题'}


def records(path, warnings):
    text = path.read_text(encoding='utf-8-sig')
    kind = path.suffix.lower()
    if kind in {'.md', '.txt'}:
        marks = list(HEADING.finditer(text))
        fallback = CHAPTER.search(path.stem)
        chapter = fallback[1] if fallback else ''
        for i, h in enumerate(marks):
            q = QUESTION.match(h[1])
            if not q:
                ch = CHAPTER.search(h[1])
                if ch:
                    chapter = ch[1]
                continue
            body = text[h.end():marks[i+1].start() if i+1 < len(marks) else len(text)]
            a = ANSWER.search(body)
            yield chapter, TYPES[q[1]], q[2], bool(a and a[1].strip(' \t\r\n-*'))
    elif kind in {'.json', '.csv'}:
        rows = json.loads(text) if kind == '.json' else csv.DictReader(io.StringIO(text))
        if isinstance(rows, dict):
            rows = rows.get('questions', [])
        for i, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                warnings.append(f'{path.name}:{i} 不是题目对象')
                continue
            t = TYPES.get(str(row.get('type', '')).lower())
            if not t:
                warnings.append(f'{path.name}:{i} 未识别题型')
                continue
            ans = row.get('answer', row.get('a'))
            yield str(row.get('chapter', row.get('ch')) or ''), t, str(row.get('number', row.get('no')) or ''), bool(ans is not None and str(ans).strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path)
    opts = parser.parse_args()
    files = set()
    for p in opts.paths:
        if not p.exists():
            parser.error(f'找不到文件：{p}')
        for f in (p.rglob('*') if p.is_dir() else [p]):
            if f.is_file() and f.suffix.lower() in EXT:
                files.add(f.resolve())
    counts, totals, seen, warnings = {}, Counter(), {}, []
    for f in sorted(files):
        try:
            rows = list(records(f, warnings))
        except (ValueError, OSError, TypeError, csv.Error) as exc:
            warnings.append(f'{f.name}: {exc}')
            continue
        if not rows:
            warnings.append(f'{f.name}: 未识别题目，请核对格式或确认为讲义')
        for ch, typ, no, answered in rows:
            key = (ch, typ, no)
            if not ch or not no:
                warnings.append(f'{f.name}: 缺章节或题号 {key}')
            if key in seen:
                warnings.append(f'重复 {key}: {seen[key]} / {f.name}')
            if not answered:
                warnings.append(f'{f.name}: 缺答案 {key}')
            seen[key] = f.name
            counts.setdefault(ch, Counter())[typ] += 1
            totals[typ] += 1
    print(json.dumps(dict(files=len(files), chapters=counts, totals=totals, review=warnings), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
