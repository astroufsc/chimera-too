#!/usr/bin/env python
"""
Synopsis:
    Sample program demonstrating use of VOEvent library and Vutil.py.

    Reads a VOEvent file and produces basic HTML rendering.
    See the VOEvent specification for details 
    http://www.ivoa.net/Documents/latest/VOEvent.html
Usage:
    python format_to_html.py [options] input_event_file.xml
Options:
    -h, --help      Display this help message.
    -s, --stdout    Send output to stdout.
    -o FILENAME, --outfile=FILENAME
                    Send output to file.
    -t, --text-string
                    Capture output as a text string, then write to stdout.
    -f, --force     Force: over-write output file without asking.
Examples:
    python format_to_html.py --stdout input_event_file.xml
    python format_to_html.py --file=outfile1.html input_event_file.xml
    python format_to_html.py -s -o outfile2.html input_event_file.xml

"""

# Copyright 2010 Roy D. Williams and Dave Kuhlmann
import re

import VOEventLib.VOEvent
import VOEventLib.Vutil
from chimera_too.util.gcn_util import get_notice_types_dict

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

http_regex = re.compile('http:(.*?)\<')


def display(v, o):
    '''Generate HTML that provides a display of an event.
    '''
    print>> o, '<html>'
    print>> o, '<h2>VOEvent</h2>'
    print>> o, 'IVORN <i>%s</i><br/>' % v.get_ivorn()
    print>> o, '(role is %s)' % v.get_role()

    print>> o, '<p>Event description: %s</p>\n' % v.get_Description()

    r = v.get_Reference()
    if r:
        print>> o, 'Reference<br/>Name=%s, Type=%s, uri=%s' \
                   % (r.get_name(), r.get_type(), r.get_uri())

    print>> o, '<h3>What</h3>'
    print>> o, '<h4>Params</h4>'
    print>> o, '<table border="1"><tr>'
    print>> o, '<td>Group</td>'
    print>> o, '<td>Name</td>'
    print>> o, '<td>Description</td>'
    print>> o, '<td><b>Value</b></td>'
    print>> o, '<td>ucd</td>'
    print>> o, '<td>unit</td>'
    print>> o, '<td>dataType</td>'
    print>> o, '</tr>'
    g = None
    params = v.get_What().get_Param()
    for p in params:
        if p.name == 'Packet_Type':
            print>> o, '<tr>' + VOEventLib.Vutil.htmlParam(g, p).replace(p.value, '%s / %s' % (
                p.value, get_notice_types_dict()[int(p.value)])) + '</tr>'
        else:
            print>> o, '<tr>' + http_regex.sub('<a href="http:\\1">http:\\1<',
                                               VOEventLib.Vutil.htmlParam(g, p)) + '</tr>'

    groups = v.get_What().get_Group()
    for g in groups:
        for p in g.get_Param():
            print>> o, '<tr>' + VOEventLib.Vutil.htmlParam(g, p) + '</tr>'
    print>> o, '</table>'
    print>> o, '<h4>Tables</h4>'
    tables = v.get_What().get_Table()
    for t in tables:
        print>> o, '<table border="1">'

        print>> o, '<tr><td><i>Name</i></td>'
        for f in t.get_Field():
            print>> o, '<td>' + str(f.get_name()) + '</td>'
        print>> o, '</tr>'

        print>> o, '<tr><td><i>UCD</i></td>'
        for f in t.get_Field():
            print>> o, '<td>' + str(f.get_ucd()) + '</td>'
        print>> o, '</tr>'

        print>> o, '<tr><td><i>unit</i></td>'
        for f in t.get_Field():
            print>> o, '<td>' + str(f.get_unit()) + '</td>'
        print>> o, '</tr>'
        print>> o, '<tr><td><i>dataType</i></td>'
        for f in t.get_Field():
            print>> o, '<td>' + str(f.get_dataType()) + '</td>'
        print>> o, '</tr>'
        print>> o, '<tr><td/></tr>'
        d = t.get_Data()
        if d:
            for tr in d.get_TR():
                print>> o, '<tr><td/>'
                for td in tr.get_TD():
                    print>> o, '<td>' + td + '</td>'
                print>> o, '</tr>'
        print>> o, '</table>'
    print>> o, '<h3>WhereWhen</h3>'
    wwd = VOEventLib.Vutil.getWhereWhen(v)
    if wwd:
        print>> o, '<table border="1">'
        print>> o, '<tr><td>Observatory</td> <td>%s</td></tr>' % wwd['observatory']
        print>> o, '<tr><td>Coord system</td><td>%s</td></tr>' % wwd['coord_system']
        print>> o, '<tr><td>Time</td>                <td>%s</td></tr>' % wwd['time']
        print>> o, '<tr><td>Time error</td>  <td>%s</td></tr>' % wwd['timeError']
        print>> o, '<tr><td>RA</td>                  <td>%s</td></tr>' % wwd['longitude']
        print>> o, '<tr><td>Dec</td>                 <td>%s</td></tr>' % wwd['latitude']
        print>> o, '<tr><td>Pos error</td>       <td>%s</td></tr>' % wwd['positionalError']
        print>> o, '</table>'
    print>> o, '<h3>Why</h3>'
    w = v.get_Why()
    if w:
        if w.get_Concept():
            print>> o, "Concept: %s" % VOEventLib.Vutil.htmlList(w.get_Concept())
        if w.get_Name():
            print>> o, "Name: %s" % VOEventLib.Vutil.htmlList(w.get_Name())

        print>> o, '<h4>Inferences</h4>'
        inferences = w.get_Inference()
        for i in inferences:
            print>> o, '<table border="1">'
            print>> o, '<tr><td>probability</td><td>%s</td></tr>' % i.get_probability()
            print>> o, '<tr><td>relation</td>     <td>%s</td></tr>' % i.get_relation()
            print>> o, '<tr><td>Concept</td>      <td>%s</td></tr>' % VOEventLib.Vutil.htmlList(i.get_Concept())
            print>> o, '<tr><td>Description</td><td>%s</td></tr>' % VOEventLib.Vutil.htmlList(i.get_Description())
            print>> o, '<tr><td>Name</td>             <td>%s</td></tr>' % VOEventLib.Vutil.htmlList(i.get_Name())
            print>> o, '<tr><td>Reference</td>  <td>%s</td></tr>' % str(i.get_Reference())
            print>> o, '</table>'
    print>> o, '<h3>Citations</h3>'
    cc = v.get_Citations()
    if cc:
        for c in cc.get_EventIVORN():
            print>> o, '<ul>'
            print>> o, '<li>%s with a %s</li>' % (c.get_valueOf_(), c.get_cite())
            print>> o, '</ul>'

    print>> o, '<h3>Who</h3>'
    who = v.get_Who()
    a = who.get_Author()
    print>> o, 'Title: %s' % VOEventLib.Vutil.htmlList(a.get_title())
    print>> o, 'Name: %s' % VOEventLib.Vutil.htmlList(a.get_contactName())
    print>> o, 'Email: %s' % VOEventLib.Vutil.htmlList(a.get_contactEmail())
    print>> o, 'Phone: %s' % VOEventLib.Vutil.htmlList(a.get_contactPhone())
    print>> o, 'Contributor: %s<br/>' % VOEventLib.Vutil.htmlList(a.get_contributor())

    print>> o, '</html>'


def format_to_string(v):
    '''Format as HTML and capture in a string.  Return the string.
    '''
    outfile = StringIO()
    display(v, outfile)
    content = outfile.getvalue()
    return content


if __name__ == '__main__':
    from VOEventLib import Vutil as VOEventTools

    example_file = 'examples/SWIFT_BAT_Lightcurve_632888-389.xml'
    payload = payload = ''.join(open(example_file).readlines())
    content = format_to_string(VOEventTools.parseString(payload))
    with open('test_voevent2html.html', "w") as f:
        f.write(content)
