import re
import cgi

import tags

ESCAPE_RE = re.compile(r'\\(?P<esc>.)')
BOLD_RE = re.compile(r'(?<!\\)\*\*(?! )(?P<bold>([^*]|\\[*])+)(?<![\\| ])\*\*')
ITALIC_RE = re.compile(r'(?<!\\)/(?! )(?P<italic>([^/]|\\[/])+)(?<![\\| ])/'
                       r'(?![\\a-zA-Z0-9:/])')
STROKE_RE = re.compile(r'(?<!\\)~(?! )(?P<s>([^~]|\\[~])+)(?<![\\| ])~')
MONOSPACE_RE = re.compile(r'(?<!\\)`(?! )(?P<ms>([^`]|\\[`])+)(?<![\\| ])`')

INLINE_EXPR_RE = re.compile(r'(?<!\\)\$(?P<expr>[^$]+)\$')
ANCHOR_RE = re.compile(r'(?<!\\)#(?P<a>([^#]+))#')
LINK_RE = re.compile(r'\[link (?P<uri>[^ \|\]]+)(?:\|(?P<text>[^\]]*))?]')
PAGE_RE = re.compile(r'\[p (?P<uri>[^ \|\]]+)(?:\|(?P<text>[^\]]*))?]')
IMG_RE = re.compile(r'\[img (?P<uri>[^ \|\]]+)]')
USER_RE = re.compile(r'@(?P<username>[A-Za-z]\w*)(?!\.\w)')

FOOTNOTE_RE = re.compile(r'\^\[\[(?P<fn>(.*))\]\]')


class InlineForge(object):
    def __init__(self):
        pass

    def convert_html_tags(self, text, ctx):
        def esc_back_slash(text):
            return ESCAPE_RE.sub(lambda m: m.group('esc'), text)

        def bold(text):
            return BOLD_RE.sub(lambda m: tags.BOLD % m.group('bold'), text)

        def italic(text):
            return ITALIC_RE.sub(lambda m: tags.ITALIC % m.group('italic'),
                                 text)

        def monospace(text):
            return MONOSPACE_RE.sub(lambda m: tags.MONOSPACE % m.group('ms'),
                                    text)

        def image(text):
            return IMG_RE.sub(lambda m: tags.IMAGE % m.group('uri'), text)

        def footnote(text, ctx):
            return FOOTNOTE_RE.sub(lambda m: tags.FOOTNOTE_ANCHOR.format(
                index=ctx.next_footnote_index(m.group('fn'))), text)

        return esc_back_slash(image(footnote(
            monospace(bold(cgi.escape(text, quote=True))), ctx)))

    def forge(self, text, ctx):
        return ''.join(self.convert_html_tags(text, ctx))
