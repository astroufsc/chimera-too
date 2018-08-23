from gcn import notice_types as n


def get_notice_types_dict():
    '''
    :return: Dictionary with gcn types and values.
    '''
    d = {}
    for k, v in n.__dict__.iteritems():
        if isinstance(v, int): d[v] = k
    return d