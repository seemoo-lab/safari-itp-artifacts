import abc

class StorageProvider(abc.ABC):

    @abc.abstractmethod
    async def initialize(self):
        raise NotImplementedError()

    @abc.abstractmethod
    async def save_result(self, url, data):
        raise NotImplementedError()
    
    @abc.abstractmethod
    async def close(self):
        raise NotImplementedError()