from langchain_text_splitters import RecursiveCharacterTextSplitter

def splitter(loaded_log):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 1000,
        chunk_overlap = 200,
        separators = ["\n"," "],
    )
    splits = text_splitter.split_documents([loaded_log])
    return splits
    
