from aiohttp import ClientSession
from cqapi.predicates import dict_to_concept
from cqapi.concept_query import ConceptQuery, dict_to_concept_query
from cqapi.util import object_to_dict
import json
import csv

class CqApiError(BaseException):
    pass


class ConnectionError(CqApiError):
    def __init__(self, msg):
        self.message = msg


async def get(session, url):
    async with session.get(url) as response:
        return await response.json()


async def get_text(session, url):
    async with session.get(url) as response:
        return await response.text()


async def post(session, url, json):
    async with session.post(url, json=json) as response:
        return await response.json()


class ConqueryConnection(object):
    async def __aenter__(self, ):
        self._session = ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.close()

    def __init__(self, url, requests_timout=5):
        self._url = url.strip('/')
        self._timeout = requests_timout

    async def get_datasets(self):
        response_list = await get(self._session, f"{self._url}/api/datasets")
        return [d['id'] for d in response_list]

    async def get_concepts(self, dataset):
        response = await get(self._session, f"{self._url}/api/datasets/{dataset}/concepts")
        return response['concepts']

    async def get_concept(self, dataset, concept_id):
        response_dict = await get(self._session, f"{self._url}/api/datasets/{dataset}/concepts/{concept_id}")
        response_list = [dict(attrs, **{"ids": [c_id]}) for c_id, attrs in response_dict.items()]
        return [dict_to_concept(d) for d in response_list]

    async def get_stored_queries(self, dataset):
        response_list = await get(self._session, f"{self._url}/api/datasets/{dataset}/stored-queries")
        for d in response_list:
            d["query"] = dict_to_concept_query(d["query"])
        return response_list

    async def get_stored_query(self, dataset, query_id):
        result = await get(self._session, f"{self._url}/api/datasets/{dataset}/stored-queries/{query_id}")
        result["query"] = dict_to_concept_query(result["query"])
        return result

    async def get_query(self, dataset, query_id):
        result = await get(self._session, f"{self._url}/api/datasets/{dataset}/queries/{query_id}")
        result["query"] = dict_to_concept_query(result["query"])
        return result

    async def execute_query(self, dataset, query: ConceptQuery):
        result = await post(self._session, f"{self._url}/api/datasets/{dataset}/queries", query._to_execution_format())
        return result["id"]

    async def get_query_results(self, dataset, query_id):
        """ Returns results for given query.
        Blocks until the query is DONE.

        :param dataset:
        :param query_id:
        :return: str containing the returned csv's
        """
        response = await self.get_query(dataset, query_id)
        while not response['status'] == 'DONE':
            response = await self.get_query(dataset, query_id)

        result_string = await self._download_query_results(response["resultUrl"])
        return list(csv.reader(result_string.splitlines(), delimiter=';'))

    async def _download_query_results(self, url):
        return await get_text(self._session, url)
