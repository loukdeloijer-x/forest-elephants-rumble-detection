from abc import ABC


class ModelInterface(ABC):
    def analyze(self, *args, **kwargs):
        raise NotImplementedError()


class StorageInterface(ABC):
    def save(self, *args, **kwargs):
        raise NotImplementedError()

    def load_files(self, *args, **kwargs):
        raise NotImplementedError()

    def remove_file(self, *args, **kwargs):
        raise NotImplementedError
