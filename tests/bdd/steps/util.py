from random import randint
import time
import sys
import math

ON_POSIX = 'posix' in sys.builtin_module_names


def process_pipe(pipe, queue):
    for line in iter(pipe.readline, b''):
        queue.put({'type': 'output', 'data': line})

    pipe.close()
    queue.put({'type': 'output_terminated'})


def kill_process(target):
    if 'proc' in target:
        target['proc'].kill()

        # Close file descriptors
        target['proc'].stdin.close()
        time.sleep(1)  # Let the application terminate before proceeding


def kill_processes(context):
    targets = context.target_registry.get_all()

    for target in targets:
        kill_process(target)


def generate_options_table_for_cucumber():
    retval = ""
    number_of_optional_options = 5
    number_of_optional_option_permutations = int(math.pow(2, number_of_optional_options))

    for x in xrange(0, number_of_optional_option_permutations):
        retval += "{0:<8}".format(" ")
        retval += "| {0:<12}| {1:<29}| {2:<29}|".format("blinky.bin", "not_set", "not_set")
        retval += " {0:<8}|".format("0x{0:02x}".format(randint(0, 255)) if x & 1 else "not_set")
        retval += " {0:<8}|".format("0x{0:02x}".format(randint(0, 255)) if x & 2 else "not_set")
        retval += " {0:<8}|".format("0x{0:02x}".format(randint(0, 255)) if x & 4 else "not_set")
        retval += " {0:<10}|".format("0.1" if x & 8 else "not_set")

        if x & 16:
            sd_reqs = []

            for i in xrange(0, randint(1, 4)):
                sd_reqs.append("0x{0:04x}".format(randint(0, 65535)))

            retval += " {0:<33}|".format(",".join(sd_reqs))
        else:
            retval += " {0:<33}|".format("not_set")

        retval += " {0:<16}|".format("100_{0:05b}.zip".format(x))
        retval += "\n"

    return retval