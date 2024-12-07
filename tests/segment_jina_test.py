import requests

data = {
    "content": "We developed a Small Language Model (SLM) to address specific limitations we encountered with traditional segmentation techniques, particularly when handling code snippets and other complex structures like tables, lists, and formulas. In traditional approaches, which often rely on token counts or rigid structural rules, it was difficult to maintain the integrity of semantically coherent content. For instance, code snippets would frequently be segmented into multiple parts, breaking their context and making it harder for downstream systems to understand or retrieve them accurately.\nBy training a specialized SLM, we aimed to create a model that could intelligently recognize and preserve these meaningful boundaries, ensuring that related elements stayed together. This not only improves the retrieval quality in RAG systems but also enhances downstream tasks like summarization and question-answering, where maintaining coherent and contextually relevant segments is critical. The SLM approach offers a more adaptable, task-specific solution that traditional segmentation methods, with their rigid boundaries, simply cannot provide.",
    "return_tokens": True,
    "return_chunks": True,
    "max_chunk_length": 1000
}

headers = {'Content-Type': 'application/json'}

response = requests.post('https://segment.jina.ai/', json=data, headers=headers)

print(response.text)