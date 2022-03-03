def read_html(htmlfilename):
    txt = ""
    with open(htmlfilename, "r") as f:
        txt = f.read()
    return txt