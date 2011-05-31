

class Text(object):
    """ Generic text for document
        Later can contain font info, etc
    """

    DEFAULT_SIZE = 10

    def __init__(self, text, italic=False, bold=False,
            size=DEFAULT_SIZE):
        self.text = text
        self.italic = italic
        self.bold = bold
        self.size = size
