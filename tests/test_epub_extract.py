# -*- coding: utf-8 -*-
import tempfile, os
from ebooklib import epub
from BookerNovelTool.novel_anls import extract_text_from_epub

book = epub.EpubBook()
book.set_identifier('test0001')
book.set_title('测试书')
book.set_language('zh')
c1 = epub.EpubHtml(title='第一章', file_name='c1.xhtml', lang='zh')
c1.content = '<html><body><h1>第一章</h1><p>第一行内容。</p></body></html>'
c2 = epub.EpubHtml(title='第二章', file_name='c2.xhtml', lang='zh')
c2.content = '<html><body><h2>第二章</h2><p>第二行内容。</p></body></html>'
book.add_item(c1); book.add_item(c2)
book.toc = [c1, c2]
book.spine = [c1, c2]
book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav())
f = tempfile.mktemp(suffix='.epub')
epub.write_epub(f, book)
chapters = extract_text_from_epub(f)
os.remove(f)
for c in chapters:
    print(c.index, c.title, repr(c.text[:30]))
assert len(chapters) == 2, f"expected 2, got {len(chapters)}"
assert chapters[0].title == '第一章', chapters[0].title
assert chapters[1].title == '第二章', chapters[1].title
assert '第一行内容。' in chapters[0].text
print('extract_text_from_epub OK')
