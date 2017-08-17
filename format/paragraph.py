import re
import cgi
import bisect

import tags
from inline import LINK_RE, PAGE_RE, INLINE_EXPR_RE


def forge_line(modifiers, line):
    for modifier in modifiers:
        line = modifier(line)
    return line


class Block(object):
    def __init__(self, inline):
        self.inline = inline

    def build(self, ctx):
        return ''

    def truncate_to(self, limit):
        return 0


class Section(Block):
    def __init__(self, lines, inline):
        Block.__init__(self, inline)
        self.lines = lines

    def build(self, ctx):
        return ''.join([self.head(ctx), self.body(ctx), self.tail()])

    def body(self, ctx):
        return ''

    def head(self, ctx):
        return ''

    def tail(self):
        return ''

    def truncate_to(self, limit):
        i = 0
        for i, ln in enumerate(self.lines):
            limit -= len(ln)
            if limit <= 0:
                self.lines = self.lines[:i + 1]
                return limit
        return limit


class Paragraph(Section):
    @staticmethod
    def make(lines, inline):
        lines = filter(None, lines)
        if len(lines) == 0:
            return None
        return Paragraph(lines, inline)

    def __init__(self, lines, inline):
        Section.__init__(self, lines, inline)

    def body(self, ctx):
        r = []
        for line in self.lines:
            r.extend([tags.PLINE_BEGIN, self.inline.forge(line, ctx),
                      tags.PLINE_END])
        return ''.join(r)

    def head(self, ctx):
        return tags.PARA_BEGIN

    def tail(self):
        return tags.PARA_END


class Bullets(Section):
    def __init__(self, lines, inline):
        Section.__init__(self, filter(None, [ln[2:] for ln in lines]), inline)

    def body(self, ctx):
        return ''.join(sum([
            [tags.LI_BEGIN, self.inline.forge(line, ctx), tags.LI_END]
            for line in self.lines], []))

    def head(self, ctx):
        return tags.UL_BEGIN

    def tail(self):
        return tags.UL_END


class SortedList(Bullets):
    def __init__(self, lines, inline):
        Bullets.__init__(self, lines, inline)

    def head(self, ctx):
        return tags.OL_BEGIN

    def tail(self):
        return tags.OL_END


class Table(Block):
    CELL_SPLIT = re.compile(r'(?<![\\])[\|]')

    class Cell(object):
        def __init__(self, content):
            self.content = content

    class Row(list):
        def __init__(self):
            list.__init__(self, [])

    def __init__(self, lines, render_table, inline):
        Block.__init__(self, inline)
        self.lines = lines
        self.render_table = render_table
        self.caption = ''

    def build(self, ctx):
        head_rows, body_rows = self._parse_rows(self.lines, ctx)
        return self.render_table(self.caption, head_rows, body_rows)

    def _parse_rows(self, lines, ctx):
        head_rows = []
        for line in lines:
            if line[:2] != '|!':
                break
            head_rows.append(self._parse_row(line[2:], ctx))
        return head_rows, [self._parse_row(line[1:], ctx)
                           for line in lines[len(head_rows):]]

    def _parse_row(self, line, ctx):
        spans = sorted(
            [m.span() for m in LINK_RE.finditer(line)] +
            [m.span() for m in PAGE_RE.finditer(line)] +
            [m.span() for m in INLINE_EXPR_RE.finditer(line)])
        row = Table.Row()
        begin = 0
        for c in Table.CELL_SPLIT.finditer(line):
            c_span = c.span()
            span_i = bisect.bisect_left(spans, c_span)
            if span_i == 0:
                row.append(Table.Cell(self.inline.forge(
                    line[begin: c_span[0]].strip(), ctx)))
                begin = c_span[1]
                continue
            span = spans[span_i - 1]
            if span[1] < c_span[1]:
                row.append(Table.Cell(self.inline.forge(
                    line[begin: c_span[0]].strip(), ctx)))
                begin = c_span[1]
        row.append(Table.Cell(self.inline.forge(line[begin:].strip(), ctx)))
        return row

    @staticmethod
    def _truncate_at(rows, limit):
        for i, row in enumerate(rows):
            for c in row:
                limit -= len(c.content)
            if limit <= 0:
                return rows[:i + 1], limit
        return rows, limit

    def truncate_to(self, limit):
        head_rows, body_rows = self._parse_rows(self.lines, None)
        limit -= len(self.caption)
        if limit <= 0:
            self.caption = ''
            del head_rows[:]
            del body_rows[:]
            return limit

        rows, limit = Table._truncate_at(head_rows, limit)
        if limit <= 0:
            head_rows = rows
            del self.body_rows[:]
            return limit

        rows, limit = Table._truncate_at(self.body_rows, limit)
        self.body_rows = rows
        return limit


class TableWithCaption(Table):
    def __init__(self, lines, render_table, inline):
        Table.__init__(self, lines[1:], render_table, inline)
        self.caption = lines[0][2:].strip()


class AsciiArtBase(Section):
    def __init__(self, lines, inline):
        Section.__init__(self, lines, inline)

    def head(self, ctx):
        return tags.AA_BEGIN

    def tail(self):
        return tags.AA_END

    def body(self, ctx):
        return tags.BR.join([
            cgi.escape(line, quote=True).replace(' ', tags.SPACE)
            for line in self.lines])


class AsciiArtMarkEach(AsciiArtBase):
    def __init__(self, lines, inline):
        AsciiArtBase.__init__(self, [ln[2:] for ln in lines], inline)


class OneLineBlock(Block):
    def __init__(self, text, inline):
        Block.__init__(self, inline)
        self.text = text

    def truncate_to(self, limit):
        return limit - len(self.text)


class Heading(OneLineBlock):
    def __init__(self, lines, inline):
        line = lines[0]
        space = line.find(' ')
        OneLineBlock.__init__(self, line[space:].strip(), inline)
        self.level = space + 2

    def build(self, ctx):
        r = tags.HEADING.format(
            lvl=self.level,
            text=(ctx.current_index().next_heading() +
                  self.inline.forge(self.text, ctx)),
            anchor='')
        return r


class LinePattern(object):
    def __init__(self, pattern_begin, pattern_end, ctor, start_exc, end_exc):
        self.begin = re.compile(pattern_begin)
        self.end = re.compile(pattern_end)
        self.ctor = ctor
        self.start_excluded = start_exc
        self.end_excluded = end_exc


class ParaForge(object):
    def __init__(self, render_table, inline):
        self.inline = inline

        table_cap_ctor = lambda lines, inline: TableWithCaption(
            lines, render_table, inline)
        table_ctor = lambda lines, inline: Table(lines, render_table, inline)

        self.line_patterns = (
            LinePattern('[*][ ]', '(?![*][ ])', Bullets, False, False),
            LinePattern('[#][ ]', '(?![#][ ])', SortedList, False, False),
            LinePattern(r'^\|\|', r'(?![\|])', table_cap_ctor, False, False),
            LinePattern(r'[\|]', r'(?![\|])', table_ctor, False, False),
            LinePattern(r'[=]+[ ]', '', Heading, False, False),
            LinePattern('(: |:$)', '(?!(: |:$))', AsciiArtMarkEach, False,
                        False),
            LinePattern(':::', ':::', AsciiArtBase, True, True),
            # CodeBlock is parsed when partition
        )

    def _get_para(self, pattern, lines, begin, offset):
        if pattern.start_excluded:
            offset += len(lines[begin]) + 1
            begin += 1
        end = begin + 1
        offset += len(lines[begin]) + 1
        while end < len(lines) and not pattern.end.match(lines[end]):
            offset += len(lines[end]) + 1
            end += 1
        if pattern.end_excluded:
            if end < len(lines):
                offset += len(lines[end]) + 1
            para = pattern.ctor(lines[begin: end], self.inline)
            end += 1
        else:
            para = pattern.ctor(lines[begin: end], self.inline)
        return end, para, offset

    def _normal_text_from(self, document, begin, offset):
        begin_pattern = self._match_pattern_begin(document[begin])
        if begin_pattern is not None:
            return begin_pattern, begin, None, offset
        offset += len(document[begin]) + 1
        end = begin + 1
        while end < len(document):
            begin_pattern = self._match_pattern_begin(document[end])
            if begin_pattern is not None:
                return begin_pattern, end, Paragraph.make(
                    document[begin: end], self.inline), offset
            offset += len(document[end]) + 1
                                        # +1 possible '\n' at the end of line
            end += 1
        return None, end, Paragraph.make(
            document[begin: end], self.inline), offset

    def _match_pattern_begin(self, line):
        for pattern in self.line_patterns:
            if pattern.begin.match(line):
                return pattern
        return None

    def find_paras(self, text):
        document = text.split('\n')
        text_len = len(text)
        cursor = 0
        offset = 0
        while cursor < len(document):
            pattern, cursor, section, offset = self._normal_text_from(
                document, cursor, offset)
            if section is not None:
                yield section, min(offset, text_len)
            if cursor < len(document):
                cursor, section, offset = self._get_para(pattern, document,
                                                         cursor, offset)
                yield section, min(offset, text_len)
