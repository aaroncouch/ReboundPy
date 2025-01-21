from typing import Optional

import requests
from requests import Session, Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import src.constants as constants

def fetch_url(
    url: str,
    retries: int = 3,
    backoff_factor: float = 0.3,
    status_forcelist: tuple = (500, 502, 504),
    timeout: int = 30,
    params: Optional[dict[str, str]] = None,
    additional_headers: Optional[dict[str, str]] = None,
) -> Response:
    """
    Fetches a URL using requests with retries and exception handling.

    Args:
        url                (str): The URL to fetch.
        retries            (int): The number of retry attempts (default is 3).
        backoff_factor   (float): A backoff factor to apply between attempts (default is 0.3).
        status_forcelist (tuple): A set of HTTP status codes to retry (default is (500, 502, 504)).
        timeout            (int): The timeout in seconds for the request (default is 5).

    Returns:
        Response object if the request is successful.
        None if all retries fail or an exception occurs.
    """
    if additional_headers is None:
        additional_headers = {}
    try:
        session = Session()
        retries = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        headers = {
            "User-Agent": constants.USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        } | additional_headers
        response = session.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None