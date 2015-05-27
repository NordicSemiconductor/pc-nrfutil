import logging


logging.basicConfig(format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M:%S ', level=logging.DEBUG)


def before_all(context):
    pass
