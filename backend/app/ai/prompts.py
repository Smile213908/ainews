"""Prompt 模板（独立管理，可配置可 AB）。"""

ANALYSIS_PROMPT = """你是热点内容审核助手。给定监控关键词和一条内容，判断它是否值得推送给用户。

监控关键词：{keyword}
预匹配命中变体：{prematch}

内容标题：{title}
内容正文（可能截断）：{content}
来源：{source}

请严格输出 JSON，字段：
- is_real: 内容是否为真实信息（广告/软文/钓鱼/明显谣言为 false）
- relevance: 与关键词的相关性打分 0-100（说明与关键词的关联程度，非内容质量）
- relevance_reason: 打分理由，不超过 100 字
- keyword_mentioned: 内容是否直接提及关键词本身（仅同领域沾边为 false）
- importance: 重要性 low/medium/high/urgent（urgent 仅用于重大突破/事故/官方发布）
- summary: 一句话摘要，说明内容与关键词的关联（不是内容介绍），不超过 80 字
"""

EXPAND_PROMPT = """给定监控关键词，生成检索变体以提高多源搜索召回。

关键词：{keyword}

生成 5-15 个变体，覆盖：大小写变形、连字符/空格变形、中英文互译、常见别称/缩写。
严格输出 JSON：{{"variants": ["...", "..."]}}
只输出变体数组，不要解释。
"""
