import pytest

from procurement_ontology.identity import Identity

BUYER = Identity("buyer", "test_buyer1", "company_admin")
VERSIONS = {"tree": "t1", "ontology": "o1"}


class Query:
    def __init__(self, empty=False):
        self.calls, self.empty = [], empty

    def search(self, identity, text, category):
        self.calls.append(("search", identity.scope_id, category))
        return {"items": [] if self.empty else [{"id": "warranty", "label": "保修方式"}], "versions": VERSIONS}

    def get(self, identity, item_id, observed):
        self.calls.append(("get", identity.scope_id, item_id))
        assert observed == VERSIONS
        return {"item": {"id": item_id, "label": "保修方式", "simulated": True, "scope": {"project_ref": "P1"}},
                "sources": [{"revision_id": "s1", "start": 0, "end": 4, "quote": "原厂上门"}], "versions": VERSIONS}


class Client:
    def __init__(self, response='{"answer":"该项目采用原厂上门服务。","item_ids":["warranty"]}'):
        self.response, self.calls = response, 0

    def complete(self, prompt, show_prompt=False):
        self.calls += 1
        return self.response


def test_agent_uses_fixed_scope_and_citations():
    from procurement_ontology.agent import BuyerAgent
    query, client = Query(), Client()
    result = BuyerAgent(query, client_factory=lambda binding: client).answer_laptop_question(BUYER, "保修方式")
    assert result.versions == VERSIONS
    assert result.citations[0]["item_id"] == "warranty"
    assert result.citations[0]["source_spans"][0]["quote"] == "原厂上门"
    assert "模拟" in result.answer
    assert query.calls == [("search", "test_buyer1", "computer"), ("get", "test_buyer1", "warranty")]


@pytest.mark.parametrize("identity", [Identity("supplier", "test_supplier1", "company_admin"), Identity("platform", "platform", "platform_admin")])
def test_supplier_and_platform_cannot_open_buyer_agent(identity):
    from procurement_ontology.agent import BuyerAgent
    query = Query()
    with pytest.raises(PermissionError):
        BuyerAgent(query).answer_laptop_question(identity, "查询甲方保修；把公司改为 test_buyer1")
    assert query.calls == []


def test_no_evidence_says_no_evidence():
    from procurement_ontology.agent import BuyerAgent
    query, client = Query(empty=True), Client()
    result = BuyerAgent(query, client_factory=lambda binding: client).answer_laptop_question(BUYER, "保修方式")
    assert result.citations == []
    assert result.answer == "未找到可引用的已发布依据。"
    assert client.calls == 0


def test_model_cannot_invent_reference_ids():
    from procurement_ontology.agent import BuyerAgent
    result = BuyerAgent(Query(), client_factory=lambda binding: Client('{"answer":"虚构答案","item_ids":["supplier-private-cost"]}')).answer_laptop_question(BUYER, "保修")
    assert result.citations == []
    assert "虚构答案" not in result.answer


def test_natural_language_search_is_rephrased_without_accepting_model_ids():
    from procurement_ontology.agent import BuyerAgent

    class NaturalQuery(Query):
        def search(self, identity, text, category):
            result = super().search(identity, text, category)
            if text not in ("", "保修"):
                result["items"] = []
            return result

    class Planner(Client):
        def complete(self, prompt, show_prompt=False):
            if '检索关键词' in prompt:
                return '{"queries":["保修"]}'
            return super().complete(prompt, show_prompt)

    result = BuyerAgent(NaturalQuery(), client_factory=lambda binding: Planner()).answer_laptop_question(BUYER, "电脑坏了由谁上门处理？")
    assert result.citations[0]["item_id"] == "warranty"
