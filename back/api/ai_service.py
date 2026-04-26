
import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.conf import settings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

logger = logging.getLogger(__name__)

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


def _get_llm():
    return ChatTongyi(model="qwen-plus")


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

        llm = _get_llm()
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


def ask_paper_question(paper_id, question):
    """
    针对指定论文提出问题并获取回答
    """
    try:
        persist_directory = get_vector_db_path(paper_id)
        if not os.path.exists(persist_directory):
            print(persist_directory)
            return "该论文尚未完成解析或解析失败，请稍后重试。"

        # 加载向量数据库
        embeddings = _get_embeddings()
        vector_db = Chroma(
            persist_directory=persist_directory, embedding_function=embeddings
        )

        # 配置大模型和检索器
        llm = _get_llm()
        retriever = vector_db.as_retriever(search_kwargs={"k": 3})  # 检索前3个相关分块

        # prompt模板
        prompt = ChatPromptTemplate.from_template(
            """你是一个专业论文助手，请根据提供的上下文回答问题。

            要求：
            ▪ 只基于上下文回答

            ▪ 如果无法从上下文得出答案，请说"未在文档中找到相关信息"

            ▪ 回答要简洁清晰


            上下文：
            {context}

            问题：
            {question}
            """
        )

        # 构建RAG链
        qa_chain = (
            {"context": retriever, "question": RunnablePassthrough()}
            | prompt
            | llm
        )

        result = qa_chain.invoke(question)
        return result.content if hasattr(result, "content") else str(result)

    except Exception as e:
        logger.error(f"Error answering question for paper {paper_id}: {str(e)}")
        return f"系统处理问答时出现错误: {str(e)}"


def analyze_multiple_papers(paper_ids_titles, question, paper_metadata=None):
    """
    多论文对比分析：两阶段 LLM + 多向量库并行检索

    paper_ids_titles: list of (paper_id, paper_title)
    question: 用户问题
    paper_metadata: dict {paper_id: {"title": ..., "abstract": ..., "keywords": ...}}
    """
    try:
        llm = _get_llm()
        embeddings = _get_embeddings()

        # ── 第一阶段：让 LLM 根据问题和论文元数据生成检索关键词 ──────────────────
        # 拼接所有论文的元数据摘要作为上下文
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

        # 提取 JSON 数组（防止模型在前后加了多余文字）
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

            # 对所有关键词检索，合并去重
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

        analysis_prompt = ChatPromptTemplate.from_template(
            """你是一个专业的学术分析助手，擅长对多篇论文进行对比分析。
以下是从多篇论文中检索到的相关内容片段，请基于这些内容回答用户的问题。

要求：
• 按论文逐一分析，再给出综合对比

• 指出相似点和差异点

• 结论要有依据，引用原文片段支撑

• 如某篇论文未找到相关内容，请说明


检索到的论文内容：
{context}

用户问题：{question}"""
        )

        analysis_chain = analysis_prompt | llm
        result = analysis_chain.invoke(
            {"context": context_text, "question": question}
        )
        answer = result.content if hasattr(result, "content") else str(result)

        return {
            "keywords": keywords,
            "answer": answer,
        }

    except Exception as e:
        logger.error(f"Error in analyze_multiple_papers: {str(e)}")
        return {"keywords": [], "answer": f"系统处理多论文分析时出现错误: {str(e)}"}