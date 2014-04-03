import itertools
from array import array

class FataTransactionError(Exception):
    pass


class TransactionalMemory(object):
    def __init__(self, size):
        self.mem = array('H', itertools.repeat(0, size))

        # Journal entries
        self.commit_list = []

    def __setitem__(self, location, value):
        if location < 0 or location >= len(self.mem):
            raise ValueError("Invalid location: %d" % (location,))

        if value is None:
            raise ValueError("Cannot have None as a value")

        self.commit_list.append((location, self.mem[location], value))

    def __getitem__(self, location):
        value = None
        for entry in self.commit_list:
            if location == entry[0]:
                value = entry[2]

        if value is not None:
            return value

        return self.get_committed(location)

    def get_committed(self, location):
        return self.mem[location]

    def has_updates(self):
        return len(self.commit_list) != 0

    def rollback(self):
        while True:
            try:
                for location, old_value, _ in self.commit_list:
                    self.mem[location] = old_value
                del self.commit_list[:]
                break
            except:
                pass

    def commit(self):
        try:
            for location, old_value, new_value in self.commit_list:
                if self.mem[location] != old_value:
                    raise FatalTransactionError("Memory view is corrupted")
                self.mem[location] = new_value
            del self.commit_list[:]
        except FatalTransactionError:
            raise
        except BaseException as e:
            self.rollback()
            raise e

# TODO: 
