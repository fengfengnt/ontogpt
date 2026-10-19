"""Publication precondition: exercise real authenticated Fuseki/TDB2 requests."""

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import requests


class FusekiClient:
    def __init__(self, base_url, credentials):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.auth = (credentials["username"], credentials["password"])
        self.dataset = "test_atomic_" + uuid.uuid4().hex

    def update(self, sparql):
        return self.session.post(
            f"{self.base_url}/{self.dataset}/update", data=sparql.encode("utf-8"),
            headers={"Content-Type": "application/sparql-update"}, timeout=30,
        )

    def query(self, sparql):
        response = self.session.post(
            f"{self.base_url}/{self.dataset}/query", data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"}, timeout=30,
        )
        response.raise_for_status()
        return response.json()


@pytest.fixture
def fuseki():
    base_url = os.getenv("FUSEKI_TEST_URL")
    if not base_url:
        pytest.skip("Set FUSEKI_TEST_URL to run the real TDB2 prerequisite")
    path = Path(os.getenv(
        "FUSEKI_CREDENTIALS_FILE",
        str(Path(__file__).resolve().parents[4] / "deploy/fuseki/runtime/credentials.json"),
    ))
    # Allow a connection failure to demonstrate RED before local credentials exist.
    credentials = json.loads(path.read_text()) if path.exists() else {
        "username": "not-configured", "password": "not-configured",
    }
    client = FusekiClient(base_url, credentials)
    response = client.session.post(
        f"{client.base_url}/$/datasets", data={"dbName": client.dataset, "dbType": "tdb2"},
        timeout=30,
    )
    response.raise_for_status()
    client.update("""
        INSERT DATA {
          GRAPH <urn:control> { <urn:root> <urn:current> <urn:v1> }
          GRAPH <urn:v1> { <urn:old1> a <urn:Item> . <urn:old2> a <urn:Item> }
        }
    """).raise_for_status()
    try:
        yield client
    finally:
        client.session.delete(f"{client.base_url}/$/datasets/{client.dataset}", timeout=30)
        client.session.close()


def publish_request(new_version, count):
    triples = " ".join(f"<urn:{new_version}:item{i}> a <urn:Item> ." for i in range(count))
    return f"""
        DELETE {{ GRAPH <urn:control> {{ <urn:root> <urn:current> <urn:v1> }} }}
        INSERT {{
          GRAPH <urn:control> {{ <urn:root> <urn:current> <urn:{new_version}> }}
          GRAPH <urn:{new_version}> {{ {triples} }}
        }}
        WHERE {{ GRAPH <urn:control> {{ <urn:root> <urn:current> <urn:v1> }} }}
    """


def read_version_and_count(client):
    rows = client.query("""
        SELECT ?version (COUNT(?item) AS ?count) WHERE {
          GRAPH <urn:control> { <urn:root> <urn:current> ?version }
          GRAPH ?version { ?item a <urn:Item> }
        } GROUP BY ?version
    """)["results"]["bindings"]
    assert len(rows) == 1
    return rows[0]["version"]["value"], int(rows[0]["count"]["value"])


def test_failed_update_keeps_old_pointer(fuseki):
    response = fuseki.update(publish_request("failed", 10) + """;
        LOAD <file:///procurement-ontology-rollback-missing.ttl> INTO GRAPH <urn:fault>
    """)
    assert response.status_code >= 400
    assert read_version_and_count(fuseki) == ("urn:v1", 2)
    assert fuseki.query("ASK { GRAPH <urn:failed> { ?s ?p ?o } }")["boolean"] is False


def test_concurrent_reads_see_complete_version(fuseki):
    def read_many():
        return [read_version_and_count(fuseki) for _ in range(15)]

    observed = [read_version_and_count(fuseki)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        readers = [pool.submit(read_many) for _ in range(3)]
        fuseki.update(publish_request("v2", 500)).raise_for_status()
        for reader in readers:
            observed.extend(reader.result())
    observed.append(read_version_and_count(fuseki))
    assert set(observed) == {("urn:v1", 2), ("urn:v2", 500)}
    assert fuseki.query("ASK { GRAPH <urn:v1> { <urn:old1> a <urn:Item> } }")["boolean"]


def test_compare_and_swap_allows_only_one_publisher(fuseki):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(fuseki.update, [publish_request("v2a", 20), publish_request("v2b", 20)]))
    assert all(response.status_code < 300 for response in responses)
    graphs = [fuseki.query(f"ASK {{ GRAPH <urn:{name}> {{ ?s ?p ?o }} }}")["boolean"]
              for name in ("v2a", "v2b")]
    assert sum(graphs) == 1
    assert read_version_and_count(fuseki) in {("urn:v2a", 20), ("urn:v2b", 20)}


def test_fuseki_requires_service_credentials(fuseki):
    with requests.Session() as session:
        session.trust_env = False
        response = session.get(f"{fuseki.base_url}/{fuseki.dataset}/query", params={"query": "ASK {}"}, timeout=10)
        assert response.status_code == 401
