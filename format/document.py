import re
import cgi

import tags
import paragraph

SECTION_SPLIT_PAT = re.compile('\n\n+')

CODE_BLOCK_BEGIN_PAT = re.compile('^```[ ]*[-!+]?[ ]*\\w*\n', re.M)
CODE_BLOCK_END_PAT = '\n```'
CODE_LINE_SPACES_PAT = re.compile('(?P<s>([ ][ ]+))')


class CodeBlock(paragraph.Section):
    def __init__(self, head, body, inline):
        paragraph.Section.__init__(self, body.split('\n'), inline)
        plus_pos = head.find('+')
        lang_start = -1
        if plus_pos != -1:
            self.inline_forge = self.inline.forge
            lang_start = plus_pos
        else:
            self.inline_forge = lambda x, ctx: cgi.escape(x, quote=True)

        self.no_number = False
        self.require_number = False

        if head.find('-') != -1:
            self.no_number = True
            lang_start = max(lang_start, head.find('-'))
        if head.find('!') != -1:
            self.require_number = True
            lang_start = max(lang_start, head.find('!'))

        if lang_start == -1:
            self.lang = head[3:].strip() or 'cpp'
        else:
            self.lang = head[lang_start + 1:].strip() or 'cpp'

    def numbered(self):
        if self.no_number:
            return False
        if self.require_number:
            return True
        return len(self.lines) > 8

    def head(self, ctx):
        r = ''
        if self.numbered():
            idx = ctx.current_index()
            r += tags.CODE_BLOCK_CAPTION.format(
                chapter=idx.chapter(),
                section=idx.section(),
                index=idx.next_code_index())
        return r + tags.CODE_BLOCK_BEGIN % self.lang

    def tail(self):
        t = ''
        if self.numbered():
            t = '<hr>'
        return tags.CODE_BLOCK_END + t

    def body(self, ctx):
        return tags.BR.join([CODE_LINE_SPACES_PAT.sub(
            lambda m: tags.SPACE * len(m.group('s')),
            self.inline_forge(line, ctx)
        ) for line in self.lines])


class Index(object):
    def __init__(self, index_1st, index_2nd):
        self.heading_indices = [index_1st, index_2nd, 0]
        self.code_index = 0

    def chapter(self):
        return self.heading_indices[0]

    def section(self):
        return self.heading_indices[1]

    def next_heading(self):
        r = '%d.%d.%d ' % tuple(self.heading_indices)
        self.heading_indices[2] += 1
        return r

    def next_code_index(self):
        r = self.code_index
        self.code_index += 1
        return r


class DocumentForge(object):
    def __init__(self, render_table, inline):
        self.para_forge = paragraph.ParaForge(render_table, inline)
        self.secs = []
        self.footnotes = []

    def set_section(self, index_first, index_second, title):
        self.secs.append({
            'index': Index(index_first, index_second),
            'title': title,
        })

    def next_footnote_index(self, footnote):
        r = len(self.footnotes)
        self.footnotes.append(footnote)
        return r

    def current_index(self):
        return self.secs[-1]['index']

    def _yield_paras(self, t):
        text = t.lstrip()
        if len(text) != 0:
            stripped = len(t) - len(text)
            start = 0
            for match in SECTION_SPLIT_PAT.finditer(text):
                for para, off in self.para_forge.find_paras(
                        text[start: match.start()]):
                    yield para, off + start + stripped
                start = match.end()
            for para, off in self.para_forge.find_paras(text[start:]):
                yield para, off + start + stripped

    def _consume_code_block(self, doc, cursor, head_start, head_end):
        for p, off in self._yield_paras(doc[cursor: head_start]):
            yield p, off + cursor
        head = doc[head_start: head_end].strip()
        body_end = doc.find(CODE_BLOCK_END_PAT, head_end)
        if -1 == body_end:
            body_end = len(doc)
        yield (CodeBlock(head, doc[head_end: body_end],
                         self.para_forge.inline),
               body_end + len(CODE_BLOCK_END_PAT) + 1)
                                        # +1 possible '\n' at the end of line

    def partition(self, doc):
        cursor = 0

        cb_match = CODE_BLOCK_BEGIN_PAT.search(doc)
        while cb_match is not None:
            head_start, head_end = cb_match.span()
            para_end = 1
            for para, para_end in self._consume_code_block(
                    doc, cursor, head_start, head_end):
                yield para, para_end
            cursor = para_end
            cb_match = CODE_BLOCK_BEGIN_PAT.search(doc, cursor)

        for p, off in self._yield_paras(doc[cursor:]):
            yield p, off + cursor

    def compile_entire(self, doc):
        return [p.build(self) for p, _ in self.partition(doc)]

    def render_footnotes(self):
        return [tags.FOOTNOTE.format(index=i, content=p)
                for i, p in enumerate(self.footnotes)]

    def compile_partial(self, doc, limit):
        def truncate(limit):
            result = []
            for para, _ in self.partition(doc):
                limit = para.truncate_to(limit)
                if limit < 0 and result:
                    return result, False
                result.append(para)
            return result, True
        paras, complete = truncate(limit)
        return ''.join([p.build() for p in paras]), complete
