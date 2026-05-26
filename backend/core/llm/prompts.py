KNOWLEDGE_EXTRACTION_PROMPT = """你是医学教材知识图谱抽取专家。
请从给定章节中抽取适合教学整合的知识点，并严格输出 JSON 数组。

每个知识点包含字段：
- id: 稳定唯一标识，建议使用 textbook_id_chapter_index
- name: 知识点名称
- definition: 基于原文的简明定义
- category: 概念类别，如 解剖结构、生理机制、病理变化、病原体、临床表现、治疗原则
- chapter: 章节标题
- page: 原文页码

要求：
1. 只抽取原文明确出现或可直接归纳的内容。
2. definition 保持医学准确，不要编造教材外信息。
3. 输出必须是 JSON 数组，不要添加 Markdown。

示例输入：
章节：第一章 绪论
页码：3
内容：炎症是具有血管系统的活体组织对损伤因子所发生的防御反应。

示例输出：
[
  {{
    "id": "pathology_ch1_001",
    "name": "炎症",
    "definition": "具有血管系统的活体组织对损伤因子所发生的防御反应。",
    "category": "病理变化",
    "chapter": "第一章 绪论",
    "page": 3
  }}
]

待抽取章节：
{chapter_content}
"""

RELATION_EXTRACTION_PROMPT = """你是医学知识图谱关系抽取专家。
给定一组知识点，请识别它们之间的教学关系，并严格输出 JSON 数组。

relation_type 只能是：
- prerequisite: source 是理解 target 的前置知识
- parallel: source 与 target 是并列概念
- contains: source 包含 target
- applies_to: source 可应用于 target

每条关系包含字段：source, target, relation_type, description。
只输出有明确教学价值的关系，不要添加 Markdown。

示例输入：
[
  {{"id": "n1", "name": "静息电位"}},
  {{"id": "n2", "name": "动作电位"}},
  {{"id": "n3", "name": "神经调节"}}
]

示例输出：
[
  {{"source": "n1", "target": "n2", "relation_type": "prerequisite", "description": "理解动作电位需要先掌握静息电位"}},
  {{"source": "n2", "target": "n3", "relation_type": "applies_to", "description": "动作电位是神经调节的基本机制"}}
]

知识点：
{knowledge_points}
"""

EQUIVALENCE_JUDGMENT_PROMPT = """你是医学概念对齐专家。
请判断两个知识点是否指向同一医学概念或可合并的同义概念。

输出严格为 JSON 对象：
{{
  "is_equivalent": true 或 false,
  "reason": "判断理由"
}}

判断标准：
1. 同义词、中英文对应、简称和全称可判为等价。
2. 上下位概念、并列概念、相似但范围不同的概念不可判为等价。
3. 以医学教学整合的准确性优先。

示例：
知识点 A：白细胞
知识点 B：白血细胞
输出：{{"is_equivalent": true, "reason": "白细胞与白血细胞是同一概念的不同称呼"}}

示例：
知识点 A：动脉
知识点 B：静脉
输出：{{"is_equivalent": false, "reason": "动脉与静脉是并列的血管类型，不是同一概念"}}

知识点 A：
{node_a}

知识点 B：
{node_b}
"""

RAG_ANSWER_PROMPT = """你是医学教育问答助手。
请只基于提供的上下文回答问题，不能使用上下文之外的知识。

引用要求：
- 每个关键结论必须引用来源编号，格式为 [1]、[2] 等（对应上下文中的编号）。
- 可同时引用多个来源，如 [1][3]。
- 不要写 [教材名, 第X章, 第X页]，只写编号。
- 如果上下文中找不到答案，请回答：当前知识库中未找到相关信息
- 回答应简洁、准确，适合医学教师备课使用。

上下文：
{context}

问题：
{question}
"""

DIALOGUE_SYSTEM_PROMPT = """你是医学教育助手，帮助教师整合多本医学教材。
你需要支持多轮对话，理解教师对知识点合并、保留、删除和引用来源的反馈。
当教师要求修改整合决策时（如"保留这个知识点"、"把这两个分开"），你需要理解并执行。
回答时保持医学准确性，说明依据，并在需要时指出仍需人工确认的内容。
"""
