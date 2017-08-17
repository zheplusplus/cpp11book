def add_h1(render_func, index, title, head, body):
    body.append(render_func('h1.html', index=index, title=title))
    head.append(render_func('toc_h1.html', index=index, title=title))

def add_h2(render_func, index, sindex, title, head, body):
    body.append(render_func('h2.html', index=index, sindex=sindex, title=title))
    head.append(render_func('toc_h2.html', index=index, sindex=sindex, title=title))
