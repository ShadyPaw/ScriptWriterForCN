#!/usr/bin/env python3
"""Render the documented plain Fountain subset to a generic screenplay PDF.

Requires ReportLab. This is not a platform-certified template or full Fountain.
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.dont_write_bytecode = True
from script_metrics import audit


def export_pdf(source, output, title, start_episode=1, initial_scene=None,
               review=False, episode_page_break=False):
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, PageBreak
    from reportlab.platypus.doctemplate import LayoutError

    result = audit(source, start_episode=start_episode, initial_scene=initial_scene, include_elements=True)
    if result['checks']['structure'] != 'passed':
        raise ValueError('Resolve structure/unsupported-format issues before export: ' +
                         '; '.join(i['message'] for i in result['issues']))

    def text(value):
        # Built-in Courier supports WinAnsi; fail visibly rather than lose glyphs.
        try:
            value.encode('cp1252')
        except UnicodeEncodeError as exc:
            raise ValueError('PDF helper needs WinAnsi text. Use a Unicode-capable renderer for this script.') from exc
        if any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError('Unsupported control character in screenplay.')
        return escape(value).replace('\n', '<br/>')

    base = ParagraphStyle('Body', fontName='Courier', fontSize=12, leading=12,
                          spaceAfter=12, allowWidows=0, allowOrphans=0)
    def style(name, **kwargs):
        return ParagraphStyle(name, parent=base, **kwargs)
    styles = {
        'title': style('Title', alignment=TA_CENTER, fontName='Courier-Bold', spaceAfter=24),
        'episode': style('Episode', alignment=TA_CENTER, fontName='Courier-Bold', spaceBefore=12, keepWithNext=True),
        'scene': style('Scene', fontName='Courier-Bold', keepWithNext=True),
        'continuation': style('Continuation', keepWithNext=True),
        'cue': style('Cue', leftIndent=144, spaceAfter=0, keepWithNext=True),
        'dialogue': style('Dialogue', leftIndent=72, rightIndent=90, spaceAfter=0),
        'parenthetical': style('Parenthetical', leftIndent=108, rightIndent=108, spaceAfter=0),
        'transition': style('Transition', alignment=TA_RIGHT),
    }
    story = [Paragraph(text(title), styles['title'])]
    had_episode = False
    for node in result['elements']:
        kind = node['kind']
        if kind == 'metadata':
            continue  # Only the explicit title is exported, never contact/review notes.
        if kind == 'page_break':
            if story and not isinstance(story[-1], PageBreak):
                story.append(PageBreak())
        elif kind == 'episode':
            if had_episode and episode_page_break:
                if not isinstance(story[-1], PageBreak):
                    story.append(PageBreak())
            story.append(Paragraph(text(node['text']), styles['episode']))
            had_episode = True
        elif kind in ('scene', 'continuation'):
            content = node['text'] + (' (CONTINUED)' if kind == 'continuation' else '')
            if review and node.get('scene_id'):
                content += ' [' + node['scene_id'] + ']'
            story.append(Paragraph(text(content), styles[kind]))
        elif kind == 'speech':
            speech = [Paragraph(text(node['text']), styles['cue'])]
            speech.extend(Paragraph(text(part['text']), styles[part['kind']]) for part in node['parts'])
            height = sum(p.wrap(432, 648)[1] for p in speech)
            if height > 600:
                raise ValueError(f'Speech at line {node["line"]} is too long for this PDF helper; use a full screenplay renderer.')
            story.append(KeepTogether(speech + [Spacer(1, 12)]))
        else:
            story.append(Paragraph(text(node['text']), styles.get(kind, base)))
    while story and isinstance(story[-1], PageBreak):
        story.pop()

    def page_number(canvas, doc):
        canvas.setFont('Courier', 10)
        canvas.drawRightString(540, 756, str(doc.page))

    output = Path(output)
    handle, temp_name = tempfile.mkstemp(prefix='screenplay-', suffix='.pdf', dir=output.parent)
    os.close(handle)
    try:
        doc = SimpleDocTemplate(temp_name, pagesize=letter, leftMargin=108, rightMargin=72,
                                topMargin=72, bottomMargin=72, title=title, author='', allowSplitting=1)
        try:
            doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
        except LayoutError as exc:
            raise ValueError('Content cannot fit this generic PDF layout; use the project template in a full screenplay renderer.') from exc
        os.replace(temp_name, output)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--title', required=True, help='Visible title; title metadata is not auto-exported')
    parser.add_argument('--start-episode', type=int, default=1)
    parser.add_argument('--initial-scene')
    parser.add_argument('--review', action='store_true', help='Show scene IDs; default clean copy')
    parser.add_argument('--episode-page-break', action='store_true')
    parser.add_argument('--force', action='store_true', help='Replace an existing output PDF')
    args = parser.parse_args()
    if args.output.resolve() == args.manuscript.resolve():
        parser.error('Output must not overwrite the manuscript.')
    if args.output.suffix.lower() != '.pdf':
        parser.error('This helper exports PDF only.')
    if args.output.exists() and not args.force:
        parser.error('Output already exists; choose another path or use --force.')
    try:
        result = export_pdf(args.manuscript.read_text(encoding='utf-8-sig'), args.output, args.title,
                            args.start_episode, args.initial_scene, args.review, args.episode_page_break)
    except ImportError:
        parser.error('ReportLab is required for PDF export; metrics use only the standard library.')
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(f'Exported {len(result["episodes"])} episodes, {result["totals"]["total_words"]} body words to {args.output}')
    print('Render and inspect every page before delivery. Numeric budgets and creative/legal checks are separate.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
