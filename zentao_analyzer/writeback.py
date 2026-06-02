def prepare_writeback_status():
    return {
        "supported": False,
        "status": "not_implemented",
    }


def writeback_to_zentao(*args, **kwargs):
    return {
        "supported": False,
        "status": "not_implemented",
        "message": "禅道回写未实现",
    }
