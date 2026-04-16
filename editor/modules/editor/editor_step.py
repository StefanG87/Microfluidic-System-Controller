"""Editor model object for a single program step."""


class Step:
    """Store the type, parameters, and active flag for one editor step."""

    def __init__(self, step_type, params=None):
        self.type = step_type
        self.params = params if params else {}
        self.active = True