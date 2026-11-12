---
name: rag
version: 1.0.0
runtime: mcp
server: fabbot
tools:
  - rag_search
permissions:
  - kb.read
config_schema:
  - vector_store: 知识向量库位置 (宿主注入)
description: 对 SOP / 设备手册 / 处置经验知识库做混合检索（向量+BM25, RRF 融合），返回带来源的片段。
---

# RAG 检索 Skill

对知识库做混合检索，返回 Top-K 片段（含来源与相似度），供 Agent 生成带引用的回答。

## 工具

### rag_search(query: string, top_k: number = 6) → {hits: [{source, text, score}]}

- 混合检索: 向量（语义）+ BM25（机台号/告警码等精确词）→ RRF 融合。
- 知识来源: data/knowledge 下的 SOP/手册 + HCL Notes 导出内容。
