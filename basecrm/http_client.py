import requests
import json


from bunch import bunchify

from basecrm.errors import RateLimitError, RequestError, ResourceError, ServerError


class HttpClient(object):
    """
    Wrapper over :module:`requests` that understands Base CRM envelope, encoding and decoding schema.
    """

    """
    Supported REST API version prefix.
    """
    API_VERSION = '/v2'

    def __init__(self, config):
        """
        :param :class:`basecrm.Configuration` config: Base CRM client configuration.
        """

        self.config = config
        if self.config.verbose:
            self.enable_logging()

    def get(self, url, params=None, **kwargs):
        """
        Send a GET request.

        :param str url: Sub URL for the request. You MUST not specify neither base url nor api version prefix.
        :param dict params: (optional) Dictionary of query parameters.
        :param dict **kwargs: (optional) Other parameters which are directly passed to :func:`requests.request`.
        :return: Tuple of three elements: (http status code, headers, response - either parsed json or plain text)
        :rtype: tuple
        """

        return self.request('get', url, params=params, **kwargs)

    def post(self, url, body=None, **kwargs):
        """
        Send a POST request.

        :param str url: Sub URL for the request. You MUST not specify neither base url nor api version prefix.
        :param dict body: (optional) Dictionary of body attributes that will be wrapped with envelope and json encoded.
        :param dict **kwargs: (optional) Other parameters which are directly passed to :func:`requests.request`.
        :return: Tuple of three elements: (http status code, headers, response - either parsed json or plain text)
        :rtype: tuple
        """

        return self.request('post', url, body=body, **kwargs)

    def put(self, url, body=None, **kwargs):
        """
        Send a PUT request.

        :param str url: Sub URL for the request. You MUST not specify neither base url nor api version prefix.
        :param dict body: (optional) Dictionary of body attributes that will be wrapped with envelope and json encoded.
        :param dict **kwargs: (optional) Other parameters which are directly passed to :func:`requests.request`.
        :return: Tuple of three elements: (http status code, headers, response - either parsed json or plain text)
        :rtype: tuple
        """

        return self.request('put', url, body=body, **kwargs)

    def delete(self, url, params=None, **kwargs):
        """
        Send a DELETE request.

        :param str url: Sub URL for the request. You MUST not specify neither base url nor api version prefix.
        :param dict params: (optional) Dictionary of query parameters.
        :param dict **kwargs: (optional) Other parameters which are directly passed to :func:`requests.request`.
        :return: Tuple of three elements: (http status code, headers, response - either parsed json or plain text)
        :rtype: tuple
        """

        return self.request('delete', url, params=params, **kwargs)

    def request(self, method, url, params=None, body=None, **kwargs):
        """
        Send an HTTP request.

        The :param:`params` will be properly encoded, as well as :param:`body` which
        will be wrapped with envelope the API expects and json encoded.

        When you get a reponse the method will try to json decode the response,
        if the media type represents json, unwrap the envelope and bunchify what has left,
        for JavaScript like access.

        :param str url: Sub URL for the request. You MUST not specify neither base url nor api version prefix.
        :param dict params: (optional) Dictionary of query parameters.
        :param dict body: (optional) Dictionary of body attributes that will be wrapped with envelope and json encoded.
        :param dict **kwargs: (optional) Other parameters which are directly passed to :func:`requests.request`.
        :raises RequestError: if authentication failed, invalid query parameter etc.
        :raises RateLimitError: if rate limit exceeded.
        :raises ResourceError: if requests payload included invalid attributes or were missing.
        :raises ServerError: if Base CRM backend servers encounterered an unexpected condition.
        :return: Tuple of three elements: (http status code, headers, response - either parsed json or plain text)
        :rtype: tuple
        """

        url = "{base_url}{version}{resource}".format(base_url=self.config.base_url,
                                                     version=self.API_VERSION,
                                                     resource=url)
        headers = {
            'Accept': 'application/json',
            'Authorization': "Bearer {0}".format(self.config.access_token),
            'User-Agent': self.config.user_agent,
        }

        if body is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(self.wrap_envelope(body))

        resp = requests.request(method, url,
                                params=params,
                                data=body,
                                headers=headers,
                                timeout=float(self.config.timeout),
                                verify=self.config.verify_ssl)

        if not (200 <= resp.status_code < 300):
            self.handle_error_response(resp)

        if 'Content-Type' in resp.headers and 'json' in resp.headers['Content-Type']:
            resp_body = self.unwrap_envelope(resp.json())
        else:
            resp_body = resp.content

        return (resp.status_code, resp.headers, resp_body)

    def handle_error_response(self, resp):
        try:
            errors = resp.json()
        except:
            raise Exception('Unknown HTTP error response. Json expected. '
                            'HTTP response code={0}. '
                            'HTTP response body={1}'.format(resp.status_code,
                                                            resp.text))
        resp_code = resp.status_code
        if resp_code == 422:
            raise ResourceError(resp_code, errors)
        elif resp_code == 429:
            raise RateLimitError()
        elif 400 <= resp_code < 500:
            raise RequestError(resp_code, errors)
        elif 500 <= resp_code < 600:
            raise ServerError(resp_code, errors)
        else:
            raise Exception('Unknown HTTP error response')

    @staticmethod
    def wrap_envelope(body):
        return {'data': body}

    @staticmethod
    def unwrap_envelope(body):
        return [bunchify(item['data']) for item in body['items']] if 'items' in body else bunchify(body['data'])

    def enable_logging(self):
        import logging
        try:
            import http.client as http_client
        except ImportError:
            # Python 2
            import httplib as http_client
        http_client.HTTPConnection.debuglevel = 1

        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True