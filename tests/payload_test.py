import xmltodict
try:
    import lxml.etree
    import io
    def parse_from_string(text):
        return lxml.etree.parse(io.BytesIO(text)).getroot()
    from lxml.etree import XMLSyntaxError
except ImportError:
    import xml.etree.cElementTree
    parse_from_string = xml.etree.cElementTree.fromstring
    try:
        from xml.etree.cElementTree import ParseError as XMLSyntaxError
    except ImportError: # Python 2.6 raises a different exception
        from xml.parsers.expat import ExpatError as XMLSyntaxError

with open("payload.xml") as fp:
    data = fp.read()
    root = parse_from_string(data)
    root_dict = xmltodict.parse(data)



# Use xpath!