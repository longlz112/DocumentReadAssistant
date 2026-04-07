from langchain_core.prompts import ChatPromptTemplate
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_chroma import Chroma
from langchain_core.runnables import RunnablePassthrough

persist_dir = r"E:\毕业论文\Project\新建文件夹\back\chroma_db\paper_3"

def print_prompt(prompt):
    print(prompt)
    return prompt

prompt = ChatPromptTemplate.from_template(
    """依据参考文献，回答用户的问题，
    
    要求：只基于上下文回答
    
    参考文献1：{context1}
    
    
    用户提问：{question}
    """
)

embedding = DashScopeEmbeddings(
    model="text-embedding-v4",
)
vector_db = Chroma(persist_directory=persist_dir, embedding_function=embedding)

retriever = vector_db.as_retriever(search_kwargs={"k": 1})

question = ''

chain = (
    {"context1": retriever, "question": RunnablePassthrough()}
    | prompt
    | print_prompt
)

result = chain.invoke("作者是谁")

