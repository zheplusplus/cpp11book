import os
import re
import jinja2

from document import DocumentForge
from inline import InlineForge
import toc

SECTION_PAT = re.compile(r'^(?P<index>(\d)+)\.(?P<title>(.*))$')
TEMPLATE_DIRECTORY = 'views'

_env = jinja2.Environment(extensions=[
    'jinja2.ext.autoescape', 'jinja2.ext.loopcontrols', 'jinja2.ext.do',
], loader=jinja2.FileSystemLoader(TEMPLATE_DIRECTORY))

def render(filename, **kwargs):
    return _env.get_template(filename).render(**kwargs)

def render_table(caption, head_rows, body_rows):
    return render('table.html', caption=caption, head_rows=head_rows,
                  body_rows=body_rows)

def render_doc(sec, doc):
    with open(os.path.join('content', sec, doc)) as i:
        return forge.compile_entire(u(i.read()))

forge = DocumentForge(render_table, InlineForge())

def u(x):
    return unicode(x, 'utf-8')

head = []
segs = []

for sec in sorted(os.listdir('content')):
    if os.path.isfile(os.path.join('content', sec)):
        continue
    match = SECTION_PAT.match(sec).groupdict()
    index = int(match['index'])
    title = u(match['title'])
    toc.add_h1(render, index, title, head, segs)

    docs = []
    for doc in os.listdir(os.path.join('content', sec)):
        if not doc or '.' == doc[0]:
            continue
        if doc.startswith('0.-'):
            segs.extend(render_doc(sec, doc))
            continue

        match = SECTION_PAT.match(doc).groupdict()
        sindex = int(match['index'])
        title = os.path.splitext(u(match['title']))[0]
        docs.append((sindex, title, doc))

    for sindex, title, doc in sorted(docs, key=lambda x: x[0]):
        forge.set_section(index, sindex, title)
        toc.add_h2(render, index, sindex, title, head, segs)
        segs.extend(render_doc(sec, doc))

output = render('main.html', toc=head, body=segs,
                footnotes=forge.render_footnotes())
with open('output.html', 'w') as o:
    o.write(output.encode('utf-8'))
