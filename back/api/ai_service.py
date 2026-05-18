
import os
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)

_thread_local = threading.local()


class _UsageLogger(BaseCallbackHandler):
    def __init__(self, operation='unknown'):
        super().__init__()
        self.operation = operation

    def on_llm_end(self, response, **kwargs):
        try:
            # ChatTongyi stores token_usage in generation_info, not in llm_output
            usage = {}
            if response.generations:
                gen_info = getattr(response.generations[0][0], 'generation_info', None) or {}
                usage = gen_info.get('token_usage') or {}
            if not usage:
                llm_output = response.llm_output or {}
                usage = llm_output.get('token_usage') or llm_output.get('usage') or {}

            input_t = usage.get('input_tokens', 0)
            output_t = usage.get('output_tokens', 0)
            total_t = usage.get('total_tokens', input_t + output_t)
            if total_t > 0 or input_t > 0:
                from .models import LLMUsageRecord
                LLMUsageRecord.objects.create(
                    model_name='qwen-plus',
                    operation=self.operation,
                    input_tokens=input_t,
                    output_tokens=output_t,
                    total_tokens=total_t,
                )
        except Exception as e:
            logger.warning(f"Failed to log LLM usage: {e}", exc_info=True)



# 测试用，用于手动解析pdf
# from pathlib import Path
# BASE_DIR = Path(__file__).resolve().parent.parent
# CHROMA_DB_DIR = os.path.join(BASE_DIR, 'chroma_db')
# def get_vector_db_path(paper_id):
#     """获取特定论文的向量数据库存储路径"""
#     return os.path.join(CHROMA_DB_DIR, f"paper_{paper_id}")


def print_prompt(prompt):
    """测试工具，打印提示词"""
    print(prompt)
    return prompt


def get_vector_db_path(paper_id):
    """获取特定论文的向量数据库存储路径"""
    return os.path.join(settings.CHROMA_DB_DIR, f"paper_{paper_id}")


def _get_embeddings():
    return DashScopeEmbeddings(model="text-embedding-v4")


def _get_llm(operation):
    _usage_logger = _UsageLogger(operation=operation)
    return ChatTongyi(model="qwen-plus", callbacks=[_usage_logger])


def extract_paper_metadata(file_path):
    """
    从 PDF 文件中提取论文元数据（标题、作者、关键词、摘要、期刊/会议、年份）。
    使用 ChatTongyi(qwen-plus) 从 PDF 首部文本中结构化提取。
    提取失败的字段统一标记为"无"。
    """
    try:
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        # 取前3页文本，通常包含论文头部信息
        head_text = "\n".join(doc.page_content for doc in documents[:3])
        head_text = head_text[:4000]  # 截断避免超出 token 限制

        llm = _get_llm("metadata")
        prompt = ChatPromptTemplate.from_template(
            """你是学术论文信息提取助手。请从以下论文文本中提取元数据，以 JSON 格式输出，不要有其他文字。

要提取的字段：
- title: 论文标题
- authors: 作者列表（多个作者用"、"分隔）
- keywords: 关键词（多个用"、"分隔）
- abstract: 论文摘要（完整摘要内容）
- journal: 期刊或会议名称
- year: 发表年份（4位数字）

若某字段无法从文本中找到，该字段值填"无"。

输出格式示例：
{{"title": "xxx", "authors": "xxx", "keywords": "xxx", "abstract": "xxx", "journal": "xxx", "year": "xxx"}}

论文文本：
{text}"""
        )
        chain = prompt | llm
        result = chain.invoke({"text": head_text})
        raw = result.content.strip()

        # 提取 JSON 对象
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1:
            raise ValueError("LLM did not return valid JSON")
        data = json.loads(raw[start:end])

        fields = ["title", "authors", "keywords", "abstract", "journal", "year"]
        return {f: str(data.get(f, "无")).strip() or "无" for f in fields}

    except Exception as e:
        logger.error(f"Error extracting metadata from {file_path}: {str(e)}")
        return {
            "title": "无", "authors": "无", "keywords": "无",
            "abstract": "无", "journal": "无", "year": "无",
        }


def process_paper_to_vector_db(file_path, paper_id):
    """
    处理PDF文件：提取文本 -> 分块 -> 存入向量数据库
    """
    try:
        logger.info(f"Start processing paper {paper_id} at {file_path}")
        # 1. 加载PDF
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        # 2. 文本分块
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
            length_function=len,
        )
        chunks = text_splitter.split_documents(documents)

        # 3. 向量化并保存到本地Chroma
        persist_directory = get_vector_db_path(paper_id)
        embeddings = _get_embeddings()

        vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=persist_directory,
        )

        logger.info(
            f"Successfully processed paper {paper_id}, generated {len(chunks)} chunks."
        )
        return True
    except Exception as e:
        logger.error(f"Error processing paper {paper_id}: {str(e)}")
        return False


def _build_history_text(history):
    """将会话历史转为提示词文本。"""
    if not history:
        return ""
    lines = []
    for msg in history[-6:]:  # 最近3轮对话
        role = "用户" if msg.get("role") == "user" else "助手"
        lines.append(f"{role}：{msg.get('content', '')}")
    return "\n".join(lines)


def _is_abstract_query(question: str) -> bool:
    """
    使用 LLM 判断问题是否属于摘要/概述类查询。
    若是，返回 True，跳过 RAG 直接用元数据摘要回答；否则返回 False。
    """
    try:
        from langchain_core.messages import HumanMessage
        llm = ChatTongyi(model="qwen-plus")  # 不附 callback，仅做轻量意图分类
        prompt = (
            "判断下面的问题是否属于以下任意一类，只需回答 yes 或 no：\n"
            "1. 询问论文的摘要、概述、简介\n"
            "2. 询问论文研究了什么、解决了什么问题\n"
            "3. 询问论文的主要内容、核心贡献或创新点\n"
            "4. 询问论文总体讲了什么\n\n"
            f"问题：{question}\n\n"
            "回答（只能是 yes 或 no）："
        )
        result = llm.invoke([HumanMessage(content=prompt)])
        return (result.content or "").strip().lower().startswith("yes")
    except Exception as e:
        logger.warning(f"Intent detection failed, falling back to RAG: {e}")
        return False


def _build_abstract_prompt(question: str, abstract: str, history_section: str) -> str:
    return (
        "你是一个专业论文助手，请根据以下论文摘要回答用户的问题，回答要简洁清晰。\n"
        + history_section + "\n"
        + "论文摘要：\n" + abstract + "\n\n"
        + "问题：\n" + question
    )


def ask_paper_question(paper_id, question, history=None, paper_abstract=None):
    """
    针对指定论文提出问题并获取回答（支持对话历史记忆）。
    若问题属于摘要类，直接使用数据库中的元数据摘要，跳过 RAG 检索。
    """
    from langchain_core.messages import HumanMessage

    try:
        history_text = _build_history_text(history)
        history_section = f"\n历史对话（供参考）：\n{history_text}\n" if history_text else ""

        # ── 意图识别：摘要类问题走元数据，跳过 RAG ──────────────────────────
        abstract_valid = paper_abstract and paper_abstract not in ("无", "", None)
        if abstract_valid and _is_abstract_query(question):
            logger.info(f"[Intent] Abstract query detected for paper {paper_id}, skipping RAG.")
            llm = _get_llm("single")
            prompt_text = _build_abstract_prompt(question, paper_abstract, history_section)
            result = llm.invoke([HumanMessage(content=prompt_text)])
            return result.content if hasattr(result, "content") else str(result)

        # ── 普通问题走 RAG 检索 ────────────────────────────────────────────
        persist_directory = get_vector_db_path(paper_id)
        if not os.path.exists(persist_directory):
            return "该论文尚未完成解析或解析失败，请稍后重试。"

        embeddings = _get_embeddings()
        vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        llm = _get_llm("single")
        retriever = vector_db.as_retriever(search_kwargs={"k": 3})

        prompt = ChatPromptTemplate.from_template(
            """你是一个专业论文助手，请根据提供的上下文回答问题。

要求：
▪ 只基于上下文回答
▪ 如果无法从上下文得出答案，请说"未在文档中找到相关信息"
▪ 回答要简洁清晰
{history_section}
上下文：
{context}

问题：
{question}
"""
        )

        qa_chain = (
            {"context": retriever, "question": RunnablePassthrough(), "history_section": lambda _: history_section}
            | prompt
            | llm
        )

        result = qa_chain.invoke(question)
        return result.content if hasattr(result, "content") else str(result)

    except Exception as e:
        logger.error(f"Error answering question for paper {paper_id}: {str(e)}")
        return f"系统处理问答时出现错误: {str(e)}"


def ask_paper_question_stream(paper_id, question, history=None, paper_abstract=None):
    """
    流式问答：针对指定论文提出问题，以生成器方式逐块返回回答内容。
    若问题属于摘要类，直接使用数据库中的元数据摘要，跳过 RAG 检索。
    """
    from langchain_core.messages import HumanMessage

    try:
        history_text = _build_history_text(history)
        history_section = f"\n历史对话（供参考）：\n{history_text}\n" if history_text else ""

        # ── 意图识别：摘要类问题走元数据，跳过 RAG ──────────────────────────
        abstract_valid = paper_abstract and paper_abstract not in ("无", "", None)
        if abstract_valid and _is_abstract_query(question):
            logger.info(f"[Intent] Abstract query detected for paper {paper_id}, skipping RAG (stream).")
            llm = _get_llm("single")
            prompt_text = _build_abstract_prompt(question, paper_abstract, history_section)
            for chunk in llm.stream([HumanMessage(content=prompt_text)]):
                if chunk.content:
                    yield chunk.content
            return

        # ── 普通问题走 RAG 检索 ────────────────────────────────────────────
        persist_directory = get_vector_db_path(paper_id)
        if not os.path.exists(persist_directory):
            yield "该论文尚未完成解析或解析失败，请稍后重试。"
            return

        embeddings = _get_embeddings()
        vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        llm = _get_llm("single")
        retriever = vector_db.as_retriever(search_kwargs={"k": 3})

        context_docs = retriever.invoke(question)
        context = "\n\n".join(doc.page_content for doc in context_docs)

        prompt_text = (
            "你是一个专业论文助手，请根据提供的上下文回答问题。\n\n"
            "要求：\n"
            "▪ 只基于上下文回答\n"
            "▪ 如果无法从上下文得出答案，请说未在文档中找到相关信息\n"
            "▪ 回答要简洁清晰\n"
            + history_section + "\n"
            + "上下文：\n" + context + "\n\n"
            + "问题：\n" + question
        )

        for chunk in llm.stream([HumanMessage(content=prompt_text)]):
            if chunk.content:
                yield chunk.content

    except Exception as e:
        logger.error(f"Error in ask_paper_question_stream for paper {paper_id}: {str(e)}")
        yield f"系统处理问答时出现错误: {str(e)}"


def analyze_multiple_papers(paper_ids_titles, question, paper_metadata=None, history=None):
    """
    多论文对比分析：两阶段 LLM + 多向量库并行检索（支持对话历史记忆）

    paper_ids_titles: list of (paper_id, paper_title)
    question: 用户问题
    paper_metadata: dict {paper_id: {"title": ..., "abstract": ..., "keywords": ...}}
    history: list of {"role": "user"|"assistant", "content": ...}
    """
    try:
        llm = _get_llm("multi")
        embeddings = _get_embeddings()

        # ── 第一阶段：让 LLM 根据问题和论文元数据生成检索关键词 ──────────────────
        meta_context = ""
        if paper_metadata:
            for pid, title in paper_ids_titles:
                meta = paper_metadata.get(pid, {})
                meta_title = meta.get("title", "无")
                meta_abstract = meta.get("abstract", "无")
                meta_keywords = meta.get("keywords", "无")
                meta_context += (
                    f"\n论文《{title}》\n"
                    f"  标题：{meta_title}\n"
                    f"  关键词：{meta_keywords}\n"
                    f"  摘要：{meta_abstract[:300]}\n"
                )

        keyword_prompt = ChatPromptTemplate.from_template(
            """你是一个学术研究助手。用户想对多篇论文进行对比分析，请根据用户的问题以及各论文的元数据，
生成 3-5 个最适合在论文向量数据库中检索相关内容的关键短语。

要求：
• 关键短语应覆盖问题中涉及的核心概念

• 结合各论文的标题、关键词和摘要，使关键短语更贴合论文内容

• 每个短语 2-8 个字，适合作为语义检索的查询词

• 只输出 JSON 数组，格式：["关键词1", "关键词2", ...]，不要有其他文字


各论文元数据：
{meta_context}

用户问题：{question}"""
        )
        keyword_chain = keyword_prompt | llm
        keyword_result = keyword_chain.invoke({"question": question, "meta_context": meta_context})
        raw = keyword_result.content.strip()

        start = raw.find("[")
        end = raw.rfind("]") + 1
        keywords = json.loads(raw[start:end]) if start != -1 else [question]
        logger.info(f"Multi-paper analysis keywords: {keywords}")

        # ── 第二阶段：对每篇论文并行检索 ─────────────────────────────────────
        def retrieve_from_paper(paper_id, paper_title):
            persist_directory = get_vector_db_path(paper_id)
            if not os.path.exists(persist_directory):
                return paper_title, []

            vector_db = Chroma(
                persist_directory=persist_directory, embedding_function=embeddings
            )
            retriever = vector_db.as_retriever(search_kwargs={"k": 3})

            seen = set()
            chunks = []
            for kw in keywords:
                docs = retriever.invoke(kw)
                for doc in docs:
                    text = doc.page_content.strip()
                    if text not in seen:
                        seen.add(text)
                        chunks.append(text)
            return paper_title, chunks

        paper_contexts = {}
        with ThreadPoolExecutor(max_workers=len(paper_ids_titles)) as executor:
            futures = {
                executor.submit(retrieve_from_paper, pid, title): title
                for pid, title in paper_ids_titles
            }
            for future in as_completed(futures):
                title, chunks = future.result()
                paper_contexts[title] = chunks

        # ── 第三阶段：综合分析 ────────────────────────────────────────────────
        context_text = ""
        for title, chunks in paper_contexts.items():
            context_text += f"\n\n【论文：{title}】\n"
            if chunks:
                context_text += "\n---\n".join(chunks)
            else:
                context_text += "（未找到相关内容）"

        history_text = _build_history_text(history)
        history_section = f"\n历史对话（供参考）：\n{history_text}\n" if history_text else ""

        analysis_prompt = ChatPromptTemplate.from_template(
            """你是一个专业的学术分析助手，擅长对多篇论文进行对比分析。
以下是从多篇论文中检索到的相关内容片段，请基于这些内容回答用户的问题。

要求：
• 按论文逐一分析，再给出综合对比

• 指出相似点和差异点

• 结论要有依据，引用原文片段支撑

• 如某篇论文未找到相关内容，请说明
{history_section}

检索到的论文内容：
{context}

用户问题：{question}"""
        )

        analysis_chain = analysis_prompt | llm
        result = analysis_chain.invoke(
            {"context": context_text, "question": question, "history_section": history_section}
        )
        answer = result.content if hasattr(result, "content") else str(result)

        return {
            "keywords": keywords,
            "answer": answer,
        }

    except Exception as e:
        logger.error(f"Error in analyze_multiple_papers: {str(e)}")
        return {"keywords": [], "answer": f"系统处理多论文分析时出现错误: {str(e)}"}


def analyze_multiple_papers_stream(paper_ids_titles, question, paper_metadata=None, history=None):
    """
    多论文对比分析流式输出。
    先完成关键词生成和检索（非流式），再流式输出综合分析结果。
    Yield 格式：{"type": "keywords"|"content"|"done"|"error", ...}
    """
    import json as _json
    from langchain_core.messages import HumanMessage

    try:
        llm = _get_llm("multi")
        embeddings = _get_embeddings()

        # 阶段 1：关键词生成（非流式）
        meta_context = ""
        if paper_metadata:
            for pid, title in paper_ids_titles:
                meta = paper_metadata.get(pid, {})
                meta_context += (
                    f"\n论文《{title}》\n"
                    f"  标题：{meta.get('title', '无')}\n"
                    f"  关键词：{meta.get('keywords', '无')}\n"
                    f"  摘要：{meta.get('abstract', '无')[:300]}\n"
                )

        keyword_prompt = ChatPromptTemplate.from_template(
            """你是一个学术研究助手。请根据用户的问题以及各论文的元数据，
生成 3-5 个最适合在论文向量数据库中检索相关内容的关键短语。
只输出 JSON 数组，格式：["关键词1", "关键词2", ...]，不要有其他文字。

各论文元数据：
{meta_context}

用户问题：{question}"""
        )
        keyword_result = (keyword_prompt | llm).invoke({"question": question, "meta_context": meta_context})
        raw = keyword_result.content.strip()
        start, end = raw.find("["), raw.rfind("]") + 1
        keywords = _json.loads(raw[start:end]) if start != -1 else [question]
        logger.info(f"Multi-paper stream keywords: {keywords}")
        yield _json.dumps({"type": "keywords", "keywords": keywords}, ensure_ascii=False)

        # 阶段 2：并行检索（非流式）
        def retrieve_from_paper(paper_id, paper_title):
            persist_directory = get_vector_db_path(paper_id)
            if not os.path.exists(persist_directory):
                return paper_title, []
            vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
            retriever = vector_db.as_retriever(search_kwargs={"k": 3})
            seen, chunks = set(), []
            for kw in keywords:
                for doc in retriever.invoke(kw):
                    text = doc.page_content.strip()
                    if text not in seen:
                        seen.add(text)
                        chunks.append(text)
            return paper_title, chunks

        paper_contexts = {}
        with ThreadPoolExecutor(max_workers=len(paper_ids_titles)) as executor:
            futures = {executor.submit(retrieve_from_paper, pid, t): t for pid, t in paper_ids_titles}
            for future in as_completed(futures):
                title, chunks = future.result()
                paper_contexts[title] = chunks

        context_text = ""
        for title, chunks in paper_contexts.items():
            context_text += f"\n\n【论文：{title}】\n"
            context_text += "\n---\n".join(chunks) if chunks else "（未找到相关内容）"

        # 阶段 3：流式综合分析
        history_text = _build_history_text(history)
        history_section = f"\n历史对话（供参考）：\n{history_text}\n" if history_text else ""

        prompt_text = (
            "你是一个专业的学术分析助手，擅长对多篇论文进行对比分析。\n"
            "以下是从多篇论文中检索到的相关内容片段，请基于这些内容回答用户的问题。\n\n"
            "要求：\n• 按论文逐一分析，再给出综合对比\n"
            "• 指出相似点和差异点\n• 结论要有依据，引用原文片段支撑\n"
            f"• 如某篇论文未找到相关内容，请说明{history_section}\n\n"
            f"检索到的论文内容：\n{context_text}\n\n用户问题：{question}"
        )

        for chunk in llm.stream([HumanMessage(content=prompt_text)]):
            if chunk.content:
                yield _json.dumps({"type": "content", "content": chunk.content}, ensure_ascii=False)

        yield _json.dumps({"type": "done"})

    except Exception as e:
        logger.error(f"Error in analyze_multiple_papers_stream: {str(e)}")
        yield _json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)


def _get_neo4j_graph():
    """
    连接 Neo4j 图数据库。
    读取环境变量：NEO4J_URI / NEO4J_USERNAME / NEO4J_PASSWORD。
    若未配置则返回 None，调用方需判断。
    """
    from langchain_neo4j import Neo4jGraph
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "123456789")
    if not password:
        logger.warning("NEO4J_PASSWORD 未设置，跳过 Neo4j 写入")
        return None
    return Neo4jGraph(url=uri, username=username, password=password)


def _graph_documents_to_echarts(graph_documents):
    """
    将 LLMGraphTransformer 返回的 graph_documents 转换为 ECharts force 图所需的
    {nodes, links, categories} 格式。
    """
    nodes_dict = {}
    links = []
    categories_set = set()

    for graph_doc in graph_documents:
        for node in graph_doc.nodes:
            node_type = node.type or "Entity"
            categories_set.add(node_type)
            if node.id not in nodes_dict:
                nodes_dict[node.id] = {"id": node.id, "name": node.id, "category": node_type}

        for rel in graph_doc.relationships:
            src, tgt = rel.source.id, rel.target.id
            links.append({"source": src, "target": tgt, "value": rel.type})
            for nid in (src, tgt):
                if nid not in nodes_dict:
                    nodes_dict[nid] = {"id": nid, "name": nid, "category": "Entity"}
                    categories_set.add("Entity")

    # 按连接数动态调整节点大小（20~60 px）
    conn_count: dict = {}
    for link in links:
        conn_count[link["source"]] = conn_count.get(link["source"], 0) + 1
        conn_count[link["target"]] = conn_count.get(link["target"], 0) + 1

    nodes_list = []
    for node in nodes_dict.values():
        count = conn_count.get(node["id"], 0)
        node["symbolSize"] = max(20, min(60, 20 + count * 4))
        node["value"] = count
        nodes_list.append(node)

    categories = [{"name": c} for c in sorted(categories_set)]
    return {"nodes": nodes_list, "links": links, "categories": categories}


def build_knowledge_graph(file_path, paper_id):
    """
    从 PDF 构建知识图谱：
      1. 用 LLMGraphTransformer 抽取节点和关系
      2. 写入 Neo4j（若已配置）
      3. 将图谱转换为 ECharts 格式并返回，供前端可视化及 Django JSONField 持久化
    """
    try:
        from langchain_experimental.graph_transformers import LLMGraphTransformer
        from langchain_core.documents import Document

        logger.info(f"Start building knowledge graph for paper {paper_id}")

        # 1. 加载 PDF，合并全文并截断以控制 token 用量
        loader = PyPDFLoader(file_path)
        pages = loader.load()
        full_text = "\n".join(page.page_content for page in pages)
        full_text = full_text[:8000]

        # 加上paper_id，用于在neo4j中查询论文对应的知识图谱
        doc = Document(
            page_content=full_text,
            metadata={"source": file_path, "id": file_path, "paper_id": paper_id},
        )

        # 2. LLM 抽取图谱
        llm = _get_llm("build_KG")
        transformer = LLMGraphTransformer(llm=llm)
        graph_documents = transformer.convert_to_graph_documents([doc])

        # 3. 写入 Neo4j
        neo4j_graph = _get_neo4j_graph()
        if neo4j_graph is not None:
            # include_source=True：在 Neo4j 中为源文档创建节点并与实体关联
            neo4j_graph.add_graph_documents(graph_documents, include_source=True)
            logger.info(f"Knowledge graph for paper {paper_id} saved to Neo4j")
        else:
            logger.info(f"Neo4j not configured, skipping persistence for paper {paper_id}")

        # 4. 转换为 ECharts 格式返回
        echarts_data = _graph_documents_to_echarts(graph_documents)
        logger.info(
            f"Knowledge graph built for paper {paper_id}: "
            f"{len(echarts_data['nodes'])} nodes, {len(echarts_data['links'])} links"
        )
        return echarts_data

    except Exception as e:
        logger.error(f"Error building knowledge graph for paper {paper_id}: {str(e)}")
        return None