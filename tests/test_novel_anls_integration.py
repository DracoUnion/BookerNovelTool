# -*- coding: utf-8 -*-
"""Integration test for novel-anls: mock LLM calls, run two-stage pipeline."""
import os
import tempfile
from argparse import Namespace

from BookerNovelTool.novel_anls import BookAnalyzerOrchestrator
from BookerNovelTool.novel_anls_models import (
    ChapterSummary, BookMeta,
)

def make_args(**over):
    args = Namespace(
        model='fake-model', key=None, host=None, retry=1, temp=1.0,
        top_p=None, frequency_penalty=None, presence_penalty=None,
        max_tokens=None, extra_body=None, stream=False,
        user_agent='test', conn_timeout=60, read_timeout=120,
        repetition_regex='', no_think=False,
    )
    for k, v in over.items():
        setattr(args, k, v)
    return args

def test_novel_anls():
    import tempfile as _tf
    from ebooklib import epub
    book = epub.EpubBook(); book.set_identifier('t1'); book.set_title('测试书'); book.set_language('zh')
    c1 = epub.EpubHtml(title='第一章', file_name='c1.xhtml', lang='zh')
    c1.content = '<html><body><h1>第一章</h1><p>第一行内容。</p></body></html>'
    book.add_item(c1); book.spine = [c1]; book.toc = [c1]
    book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav())
    f = _tf.mktemp(suffix='.epub'); epub.write_epub(f, book)

    args = make_args(fname=f, threads=4, max_chapters=None,
                     book_title='测试书', author='作者', blurb='简介')
    orc = BookAnalyzerOrchestrator(args)
    orc.agent.scan_chapter = lambda chapter_index, chapter_title, chapter_text: ChapterSummary(
        module='章节摘要', chapter=chapter_index, title=chapter_title,
        summary='摘要', key_events=['e'], new_characters=[], character_updates=[],
        emotional_tone=5, chapter_end_hook=None, foreshadowing_planted=[],
        foreshadowing_payoff=[], conflict_level=5, word_count=10)
    orc.agent.aggregate_module = lambda module_name, summaries, book_meta: (
        type('M', (), {'model_dump': lambda self: {'module': module_name, 'x': 1}})()
    )

    output = f[:-5] + '_book_anls.json'
    orc.run()
    os.remove(f)
    assert os.path.isfile(output), output
    data = __import__('json').load(open(output, encoding='utf8'))
    assert data['total_chapters'] == 1, data['total_chapters']
    assert data['book_meta']['book_title'] == '测试书'
    print('novel-anls OK; modules:', sorted(data['modules'].keys()))

if __name__ == '__main__':
    test_novel_anls()
    print('novel-anls INTEGRATION TEST PASSED')
