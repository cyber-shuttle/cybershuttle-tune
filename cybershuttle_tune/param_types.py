class IntParamType:
    def __init__(self, name, values = []):
        self.values = values
        self.name = name
    def set_range(self, start, end, step):
        for i in range(start, end, step):
            self.values.append(i)

    def set_values(self, values):
        for i in values:
            self.values.append(i)
class StringParamType:
    def __init__(self, name, values = []):
        self.values = values
        self.name = name

    def set_values(self, values):
        for i in values:
            self.values.append(i)
class FloatParamType:
    def __init__(self, name, values = []):
        self.values = values
        self.name = name

    def set_values(self, values):
        for i in values:
            self.values.append(i)

class GenericParamType:
    def __init__(self, name, values = []):
        self.values = values
        self.name = name