# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.


class NordicSemiException(Exception):
    """
    Exception used as based exception for other exceptions defined in this package.
    """
    pass


class NotImplementedException(NordicSemiException):
    """
    Exception used when functionality has not been implemented yet.
    """
    pass


class InvalidArgumentException(NordicSemiException):
    """"
    Exception used when a argument is of wrong type
    """
    pass

class MissingArgumentException(NordicSemiException):
    """"
    Exception used when a argument is missing
    """
    pass


class IllegalStateException(NordicSemiException):
    """"
    Exception used when program is in an illegal state
    """
    pass
