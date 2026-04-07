import os
import logging
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


def get_vector_db_path(paper_id):
    """获取特定论文的向量数据库存储路径"""
    return os.path.join(settings.CHROMA_DB_DIR, f"paper_{paper_id}")


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
            length_function=len
        )
        chunks = text_splitter.split_documents(documents)

        # 3. 向量化并保存到本地Chroma
        persist_directory = get_vector_db_path(paper_id)
        embeddings = DashScopeEmbeddings(
            model="text-embedding-v4",
            # other params...
            )  # 可替换

        vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=persist_directory
        )

        logger.info(f"Successfully processed paper {paper_id}, generated {len(chunks)} chunks.")
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
        embeddings = DashScopeEmbeddings(
            model="text-embedding-v4",
            # other params...
        )  # 可替换
        vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)

        # 配置大模型和检索器
        # llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.3)
        llm = ChatTongyi(
            model="qwen-plus",
            # other params...
        )
        retriever = vector_db.as_retriever(search_kwargs={"k": 3})  # 检索前3个相关分块

        # prompt模板
        prompt = ChatPromptTemplate.from_template(
            """你是一个专业论文助手，请根据提供的上下文回答问题。

            要求：
            - 只基于上下文回答
            - 如果无法从上下文得出答案，请说“未在文档中找到相关信息”
            - 回答要简洁清晰

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


# 测试用，用于手动解析pdf
# file_path = r"E:\毕业论文\Project\新建文件夹\back\media\papers\基于大型语言模型的检索增强生成综述_刘雪颖.pdf"
# file_id = "6"
#
# if __name__ == "__main__":
#     process_paper_to_vector_db(file_path, file_id)
