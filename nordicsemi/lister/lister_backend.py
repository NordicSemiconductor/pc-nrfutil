import abc

class AbstractLister(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def enumerate(self):
        """
        Enumerate all usb devices
        """
        pass
