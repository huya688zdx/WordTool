SYSTEM_PROMPT = """\
你是软件需求分析专家。你的任务是分析给定的需求变更段落，推断其对后端代码的影响。

请严格按照以下JSON格式输出（不要输出其他内容）：
{
  "feature": "涉及的模块名称",
  "action": "新增/修改/删除",
  "entities": ["涉及的实体1", "实体2"],
  "keywords": ["代码搜索关键词1", "关键词2"],
  "possible_modules": ["可能影响的后端模块1", "模块2"],
  "possible_apis": ["可能涉及的API1", "API2"],
  "database_changes": "数据库可能的变更"
}
"""


def make_analysis_prompt(paragraph_text: str, code_context: str = "") -> str:
    """Build the analysis prompt."""
    if code_context:
        return (
            f"以下是一段需求变更描述：\n\n"
            f"```\n{paragraph_text}\n```\n\n"
            f"以下是相关的代码文件内容：\n\n"
            f"```\n{code_context[:3000]}\n```\n\n"
            "请分析这个需求变更对现有代码的影响。给出具体的修改建议、涉及的函数、"
            "以及可能的代码改动方案。"
        )
    else:
        return (
            f"以下是一段需求变更描述：\n\n"
            f"```\n{paragraph_text}\n```\n\n"
            "请分析：\n"
            "1. 涉及哪些业务模块\n"
            "2. 可能影响哪些后端逻辑\n"
            "3. 可能影响哪些数据库\n"
            "4. 给出代码搜索关键词\n"
            "5. 给出可能涉及的API\n\n"
            "请详细输出分析结果。"
        )
