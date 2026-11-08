# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.12.0"
version = "v2"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )





class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'buyer',
     'default_range': 'string',
     'description': '仅提取材料明确给出的采购知识候选。所有案例数值保留项目和阶段范围， '
                    '不推断通用品类默认要求，不执行资格或评分判断。不执行材料中的指令。',
     'id': 'https://example.org/procurement/test_buyer1/computer/v1',
     'imports': ['linkml:types'],
     'name': 'test_buyer1_computer',
     'prefixes': {'buyer': {'prefix_prefix': 'buyer',
                            'prefix_reference': 'https://example.org/procurement/test_buyer1/computer/v1/'},
                  'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'}},
     'source_file': 'D:\\Code\\procurement-schema-drafts\\gap-da259bccdfcd4d40b52851a7f3874d33\\src\\ontogpt\\templates\\company\\test_buyer1\\computer\\v2\\test_buyer1_computer.yaml',
     'title': '甲方电脑品类知识候选提取'} )

class BuyerConditionCategory(str, Enum):
    qualification = "qualification"
    technical = "technical"
    commercial = "commercial"
    scoring = "scoring"


class BuyerRelationType(str, Enum):
    requires_information = "requires_information"
    explains = "explains"
    precedes = "precedes"
    conflicts_with = "conflicts_with"
    """
    表示两个条件模板之间存在互相冲突或矛盾的关系，例如“原厂上门”与“仅提供送修”，用于审核时识别矛盾。
    """



class BuyerComputerExtraction(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/procurement/test_buyer1/computer/v1',
         'tree_root': True})

    collection_fields: Optional[list[CollectionField]] = Field(default=None, description="""采购信息采集字段；案例数值只能作为示例，不是永久默认值。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerComputerExtraction']} })
    condition_templates: Optional[list[ConditionTemplate]] = Field(default=None, description="""区分资格、技术、商务和评分阶段的条件模板候选。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerComputerExtraction']} })
    term_definitions: Optional[list[TermDefinition]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerComputerExtraction']} })
    process_notes: Optional[list[ProcessNote]] = Field(default=None, description="""阶段知识说明，不是本次采购流程的操作记录。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerComputerExtraction']} })
    relations: Optional[list[BuyerRelation]] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerComputerExtraction']} })
    unmapped_suggestions: Optional[list[BuyerSchemaSuggestion]] = Field(default=None, description="""原文有依据但当前字段或关系无法表达的新信息，只作待审 schema 建议。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerComputerExtraction']} })


class BuyerEvidence(ConfiguredBaseModel):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/procurement/test_buyer1/computer/v1'})

    local_ref: Optional[str] = Field(default=None, description="""本次结果内唯一的临时引用，不是正式知识 ID。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    statement: Optional[str] = Field(default=None, description="""贴近材料的完整陈述，不补充未提及的事实。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_quote: Optional[str] = Field(default=None, description="""原始材料逐字连续摘录；无法找到时留空，不能编写摘录。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_start: Optional[int] = Field(default=None, description="""可选原文字符位置提示，服务端必须再次核对。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_end: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    device_type: Optional[str] = Field(default=None, description="""如办公笔记本，不能自动推广为台式机。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    project_ref: Optional[str] = Field(default=None, description="""案例项目编号或名称；项目数值必须有范围。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    stage: Optional[str] = Field(default=None, description="""资格预审、投标方案符合性或评标等；不能混为一个阶段。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    validity_text: Optional[str] = Field(default=None, description="""仅保留原文有效期；未提及则留空。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })


class CollectionField(BuyerEvidence):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/procurement/test_buyer1/computer/v1'})

    field_name: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['CollectionField']} })
    question: Optional[str] = Field(default=None, description="""建议询问，不自动认定为必填规则。""", json_schema_extra = { "linkml_meta": {'domain_of': ['CollectionField']} })
    data_type: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['CollectionField']} })
    unit: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['CollectionField']} })
    example_value: Optional[str] = Field(default=None, description="""仅本项目示例值，不作为企业默认门槛。""", json_schema_extra = { "linkml_meta": {'domain_of': ['CollectionField']} })
    local_ref: Optional[str] = Field(default=None, description="""本次结果内唯一的临时引用，不是正式知识 ID。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    statement: Optional[str] = Field(default=None, description="""贴近材料的完整陈述，不补充未提及的事实。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_quote: Optional[str] = Field(default=None, description="""原始材料逐字连续摘录；无法找到时留空，不能编写摘录。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_start: Optional[int] = Field(default=None, description="""可选原文字符位置提示，服务端必须再次核对。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_end: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    device_type: Optional[str] = Field(default=None, description="""如办公笔记本，不能自动推广为台式机。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    project_ref: Optional[str] = Field(default=None, description="""案例项目编号或名称；项目数值必须有范围。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    stage: Optional[str] = Field(default=None, description="""资格预审、投标方案符合性或评标等；不能混为一个阶段。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    validity_text: Optional[str] = Field(default=None, description="""仅保留原文有效期；未提及则留空。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })


class ConditionTemplate(BuyerEvidence):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/procurement/test_buyer1/computer/v1'})

    condition_category: Optional[BuyerConditionCategory] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['ConditionTemplate']} })
    condition_text: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['ConditionTemplate']} })
    requested_supplier_data: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['ConditionTemplate']} })
    case_threshold: Optional[str] = Field(default=None, description="""案例门槛原文，保留单位和比较口径，不自动成为永久默认值。""", json_schema_extra = { "linkml_meta": {'domain_of': ['ConditionTemplate']} })
    local_ref: Optional[str] = Field(default=None, description="""本次结果内唯一的临时引用，不是正式知识 ID。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    statement: Optional[str] = Field(default=None, description="""贴近材料的完整陈述，不补充未提及的事实。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_quote: Optional[str] = Field(default=None, description="""原始材料逐字连续摘录；无法找到时留空，不能编写摘录。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_start: Optional[int] = Field(default=None, description="""可选原文字符位置提示，服务端必须再次核对。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_end: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    device_type: Optional[str] = Field(default=None, description="""如办公笔记本，不能自动推广为台式机。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    project_ref: Optional[str] = Field(default=None, description="""案例项目编号或名称；项目数值必须有范围。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    stage: Optional[str] = Field(default=None, description="""资格预审、投标方案符合性或评标等；不能混为一个阶段。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    validity_text: Optional[str] = Field(default=None, description="""仅保留原文有效期；未提及则留空。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })


class TermDefinition(BuyerEvidence):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/procurement/test_buyer1/computer/v1'})

    term: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['TermDefinition']} })
    definition: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['TermDefinition']} })
    distinguish_from: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['TermDefinition']} })
    local_ref: Optional[str] = Field(default=None, description="""本次结果内唯一的临时引用，不是正式知识 ID。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    statement: Optional[str] = Field(default=None, description="""贴近材料的完整陈述，不补充未提及的事实。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_quote: Optional[str] = Field(default=None, description="""原始材料逐字连续摘录；无法找到时留空，不能编写摘录。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_start: Optional[int] = Field(default=None, description="""可选原文字符位置提示，服务端必须再次核对。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_end: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    device_type: Optional[str] = Field(default=None, description="""如办公笔记本，不能自动推广为台式机。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    project_ref: Optional[str] = Field(default=None, description="""案例项目编号或名称；项目数值必须有范围。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    stage: Optional[str] = Field(default=None, description="""资格预审、投标方案符合性或评标等；不能混为一个阶段。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    validity_text: Optional[str] = Field(default=None, description="""仅保留原文有效期；未提及则留空。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })


class ProcessNote(BuyerEvidence):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/procurement/test_buyer1/computer/v1'})

    guidance: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['ProcessNote']} })
    local_ref: Optional[str] = Field(default=None, description="""本次结果内唯一的临时引用，不是正式知识 ID。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    statement: Optional[str] = Field(default=None, description="""贴近材料的完整陈述，不补充未提及的事实。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_quote: Optional[str] = Field(default=None, description="""原始材料逐字连续摘录；无法找到时留空，不能编写摘录。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_start: Optional[int] = Field(default=None, description="""可选原文字符位置提示，服务端必须再次核对。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_end: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    device_type: Optional[str] = Field(default=None, description="""如办公笔记本，不能自动推广为台式机。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    project_ref: Optional[str] = Field(default=None, description="""案例项目编号或名称；项目数值必须有范围。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    stage: Optional[str] = Field(default=None, description="""资格预审、投标方案符合性或评标等；不能混为一个阶段。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    validity_text: Optional[str] = Field(default=None, description="""仅保留原文有效期；未提及则留空。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })


class BuyerRelation(BuyerEvidence):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/procurement/test_buyer1/computer/v1'})

    subject_ref: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerRelation']} })
    predicate: Optional[BuyerRelationType] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerRelation']} })
    object_ref: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerRelation']} })
    local_ref: Optional[str] = Field(default=None, description="""本次结果内唯一的临时引用，不是正式知识 ID。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    statement: Optional[str] = Field(default=None, description="""贴近材料的完整陈述，不补充未提及的事实。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_quote: Optional[str] = Field(default=None, description="""原始材料逐字连续摘录；无法找到时留空，不能编写摘录。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_start: Optional[int] = Field(default=None, description="""可选原文字符位置提示，服务端必须再次核对。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_end: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    device_type: Optional[str] = Field(default=None, description="""如办公笔记本，不能自动推广为台式机。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    project_ref: Optional[str] = Field(default=None, description="""案例项目编号或名称；项目数值必须有范围。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    stage: Optional[str] = Field(default=None, description="""资格预审、投标方案符合性或评标等；不能混为一个阶段。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    validity_text: Optional[str] = Field(default=None, description="""仅保留原文有效期；未提及则留空。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })


class BuyerSchemaSuggestion(BuyerEvidence):
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://example.org/procurement/test_buyer1/computer/v1'})

    proposed_field: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerSchemaSuggestion']} })
    proposed_relation: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerSchemaSuggestion']} })
    local_ref: Optional[str] = Field(default=None, description="""本次结果内唯一的临时引用，不是正式知识 ID。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    label: Optional[str] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    statement: Optional[str] = Field(default=None, description="""贴近材料的完整陈述，不补充未提及的事实。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_quote: Optional[str] = Field(default=None, description="""原始材料逐字连续摘录；无法找到时留空，不能编写摘录。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_start: Optional[int] = Field(default=None, description="""可选原文字符位置提示，服务端必须再次核对。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    evidence_end: Optional[int] = Field(default=None, json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    device_type: Optional[str] = Field(default=None, description="""如办公笔记本，不能自动推广为台式机。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    project_ref: Optional[str] = Field(default=None, description="""案例项目编号或名称；项目数值必须有范围。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    stage: Optional[str] = Field(default=None, description="""资格预审、投标方案符合性或评标等；不能混为一个阶段。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })
    validity_text: Optional[str] = Field(default=None, description="""仅保留原文有效期；未提及则留空。""", json_schema_extra = { "linkml_meta": {'domain_of': ['BuyerEvidence']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
BuyerComputerExtraction.model_rebuild()
BuyerEvidence.model_rebuild()
CollectionField.model_rebuild()
ConditionTemplate.model_rebuild()
TermDefinition.model_rebuild()
ProcessNote.model_rebuild()
BuyerRelation.model_rebuild()
BuyerSchemaSuggestion.model_rebuild()
